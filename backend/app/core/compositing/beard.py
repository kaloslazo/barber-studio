import cv2
import numpy as np

from app.core.compositing.alpha import inside_feather, organic_feather
#from app.core.geometry.delaunay import delaunay_triangles
from app.core.geometry.delaunay_fortune import delaunay_triangles
from app.core.geometry.warp import warp_template

try:
    from pathlib import Path
    ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets/beards"
except ImportError:
    ASSETS_DIR = None

JAW = list(range(0, 17))
CHIN_SECTOR = list(range(3, 14))
GOATEE_JAW = list(range(5, 12))
MOUTH_OUTER = list(range(48, 60))

PALETTE = [
    (28, 23, 20),
    (45, 37, 29),
    (60, 49, 38),
    (78, 67, 54),
    (100, 92, 80),
    (22, 19, 17),
]

STYLES = {
    "full": {"region": "full", "density": 0.95, "min_contrast": 15},
    "goatee": {"region": "goatee", "density": 0.95, "min_contrast": 12},
    "mustache": {"region": "mustache", "density": 0.95, "min_contrast": 12},
    "stubble": {"region": "full", "density": 0.55, "min_contrast": 5},
}


def _polygon_mask(shape, points):
    mask = np.zeros(shape, np.uint8)
    cv2.fillPoly(mask, [np.asarray(points, np.int32)], 255)
    return mask


def _ellipse_mask(shape, center, axes):
    mask = np.zeros(shape, np.uint8)
    cv2.ellipse(
        mask,
        (int(center[0]), int(center[1])),
        (max(1, int(axes[0])), max(1, int(axes[1]))),
        0, 0, 360, 255, -1,
    )
    return mask


def _expand(points, centroid, px):
    pts = np.asarray(points, np.float32)
    direction = pts - centroid
    norm = np.linalg.norm(direction, axis=1, keepdims=True) + 1e-6
    return pts + (direction / norm) * px


def _mustache_ellipse(shape, pts):
    center = pts[33] * 0.55 + pts[51] * 0.45
    half_w = np.linalg.norm(pts[48] - pts[54]) * 0.46
    return _ellipse_mask(shape, center, (half_w, max(2.0, half_w * 0.24)))


def _mustache_band(shape, pts):
    """Arched band: comisura -> subnasal -> comisura, thickest at the center."""
    mask = np.zeros(shape, np.uint8)
    left, top, right = pts[48], pts[33], pts[54]
    lip_h = np.linalg.norm(pts[51] - pts[57])
    t = np.linspace(0, 1, 32)[:, None]
    curve = (1 - t) ** 2 * left + 2 * (1 - t) * t * top + t**2 * right
    for i, (cx, cy) in enumerate(curve):
        arch = np.sin(np.pi * i / 31)
        radius = lip_h * (0.35 + 0.45 * arch)
        cv2.circle(mask, (int(cx), int(cy)), max(2, int(radius)), 255, -1)
    return cv2.GaussianBlur(mask, (0, 0), 2.0)


def beard_mask(image_shape, points, style):
    h, w = image_shape[:2]
    pts = np.asarray(points, np.float32)
    centroid = pts.mean(axis=0)
    face_w = np.linalg.norm(pts[16] - pts[0])

    mouth = pts[MOUTH_OUTER]
    mouth_center = mouth.mean(axis=0)
    mouth_half_w = np.linalg.norm(pts[48] - pts[54]) * 0.55
    mouth_half_h = np.linalg.norm(pts[51] - pts[57]) * 0.65
    mouth_hole = _ellipse_mask((h, w), mouth_center, (mouth_half_w, mouth_half_h))
    mustache = _mustache_ellipse((h, w), pts)

    region = STYLES[style]["region"]
    if region == "mustache":
        mask = _mustache_band((h, w), pts)
    elif region == "full":
        jaw = _expand(pts[JAW], centroid, face_w * 0.04)
        upper_line = np.array([
            0.35 * jaw[16] + 0.65 * pts[54],
            (pts[33] + pts[54]) / 2,
            pts[33],
            (pts[33] + pts[48]) / 2,
            0.35 * jaw[0] + 0.65 * pts[48],
        ])
        mask = _polygon_mask((h, w), np.vstack([jaw, upper_line]))
        mask = cv2.subtract(mask, mouth_hole)
    else:
        chin = _expand(pts[GOATEE_JAW], centroid, face_w * 0.03)
        mouth_width = np.linalg.norm(pts[54] - pts[48]) + 1e-6
        along = (pts[54] - pts[48]) / mouth_width
        left = pts[48] - along * mouth_width * 0.18
        right = pts[54] + along * mouth_width * 0.18
        mask = _polygon_mask((h, w), np.vstack([left, chin, right]))
        mask = cv2.subtract(mask, mouth_hole)
        mask = cv2.add(mask, _mustache_band((h, w), pts))

    if region != "full":
        lips = _polygon_mask((h, w), pts[MOUTH_OUTER])
        lips = cv2.dilate(lips, np.ones((5, 5), np.uint8))
        mask = cv2.subtract(mask, lips)

    kernel = np.ones((5, 5), np.uint8)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def _direction_maps(pts, h, w):
    """Per-pixel hair direction: down at the jaw, outward at the cheeks,
    horizontal under the nose (mustache band)."""
    cx, cy = pts.mean(axis=0)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    ox = xs - cx
    oy = ys - cy
    norm = np.sqrt(ox * ox + oy * oy) + 1e-6
    dx = 0.6 * ox / norm
    dy = 0.75 + 0.6 * oy / norm
    dn = np.sqrt(dx * dx + dy * dy) + 1e-6
    dx, dy = dx / dn, dy / dn

    nose_y = float(pts[33][1])
    lip_y = float(pts[51][1])
    mid_y = (nose_y + lip_y) / 2
    band_h = max(4.0, (lip_y - nose_y) * 0.75)
    half_w = np.linalg.norm(pts[48] - pts[54]) * 0.46
    band = (np.abs(ys - mid_y) < band_h) & (np.abs(xs - float(pts[33][0])) < half_w)
    side = np.sign(xs - float(pts[33][0]))
    dx = np.where(band, side * 0.95 + dx * 0.05, dx)
    dy = np.where(band, 0.22, dy)
    dn = np.sqrt(dx * dx + dy * dy) + 1e-6
    return (dx / dn).astype(np.float32), (dy / dn).astype(np.float32), band


def _streak_texture(rng, h, w, dx, dy, length_px, bins=12, noise=None):
    """Anisotropic noise: noise streaked along the local hair direction."""
    if noise is None:
        noise = rng.random((h, w)).astype(np.float32)
    angle_map = (np.arctan2(dy, dx) + np.pi) % np.pi
    out = np.zeros((h, w), np.float32)
    step = np.pi / bins
    for i in range(bins):
        a = i * step
        kx = max(1, int(length_px * abs(np.cos(a))))
        ky = max(1, int(length_px * abs(np.sin(a))))
        kernel = np.zeros((ky * 2 + 1, kx * 2 + 1), np.float32)
        cv2.line(
            kernel,
            (kx - int(kx * np.cos(a)), ky - int(ky * np.sin(a))),
            (kx + int(kx * np.cos(a)), ky + int(ky * np.sin(a))),
            1.0,
            1,
        )
        total = kernel.sum()
        if total <= 0:
            continue
        kernel /= total
        blurred = cv2.filter2D(noise, -1, kernel)
        angle_diff = np.minimum(np.abs(angle_map - a), np.pi - np.abs(angle_map - a))
        weight = np.clip(1.0 - angle_diff / step, 0.0, 1.0)
        out += blurred * weight
    out -= out.min()
    out /= out.max() + 1e-6
    return out


def _bezier_float(p0, p1, p2, samples=6):
    t = np.linspace(0, 1, samples)[:, None]
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t**2 * p2


def _bezier(p0, p1, p2, samples=6):
    return _bezier_float(p0, p1, p2, samples).astype(np.int32)


def _strand_layer(rng, mask, dx, dy, style, face_w, density, band, tint=None):
    h, w = mask.shape
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return np.zeros((h, w, 3), np.float32), np.zeros((h, w), np.float32)

    count = int(len(xs) * (0.06 if style != "stubble" else 0.02) * density)
    count = min(count, 9000)
    chosen = rng.choice(len(xs), size=count, replace=False)

    canvas = np.zeros((h, w, 4), np.uint8)
    for i in chosen:
        x0, y0 = float(xs[i]), float(ys[i])
        iy, ix = int(y0), int(x0)
        ux, uy = float(dx[iy, ix]), float(dy[iy, ix])

        if style == "stubble":
            length = face_w * rng.uniform(0.012, 0.025)
        else:
            length = face_w * rng.uniform(0.045, 0.10)
        curl = rng.uniform(-0.7, 0.7)
        p0 = np.array([x0, y0], np.float32)
        p1 = p0 + np.array([ux, uy]) * length * 0.5 + np.array([curl * length * 0.2, 0.0])
        p2 = p0 + np.array([ux, uy]) * length + np.array(
            [curl * length * 0.7, -abs(ux) * length * 0.12]
        )

        if tint is None:
            color = PALETTE[int(rng.integers(0, len(PALETTE)))]
        else:
            jitter = float(rng.uniform(0.72, 1.08))
            color = (float(tint[0]) * jitter, float(tint[1]) * jitter, float(tint[2]) * jitter)
        alpha = int(rng.integers(150, 235))
        thickness = 1 if style == "stubble" else int(rng.choice([1, 1, 2], p=[0.5, 0.32, 0.18]))
        cv2.polylines(
            canvas,
            [_bezier(p0, p1, p2)],
            False,
            (color[0], color[1], color[2], alpha),
            thickness,
            cv2.LINE_AA,
        )

    canvas = cv2.GaussianBlur(canvas, (3, 3), 0)
    return canvas[..., :3].astype(np.float32), canvas[..., 3].astype(np.float32) / 255.0


def _template_asymmetry(template):
    alpha = template["bgra"][..., 3]
    center_x = int(template["points"][33][0])
    left = (alpha[:, :center_x] > 40).sum()
    right = (alpha[:, center_x:] > 40).sum()
    return abs(left - right) / max(left + right, 1)


def load_templates():
    templates = []
    if ASSETS_DIR is None:
        return templates
    for path in sorted(ASSETS_DIR.glob("*.npz")):
        data = np.load(path)
        parts = path.stem.split("_")
        category = parts[1] if len(parts) >= 2 else "full"
        template = {
            "name": path.stem,
            "category": category,
            "bgra": data["bgra"],
            "points": data["points"],
            "skin_ycrcb": data["skin_ycrcb"],
        }
        if _template_asymmetry(template) > 0.25:
            continue
        templates.append(template)
    return templates


def _target_skin_ycrcb(image_bgr, pts):
    nose_len = np.linalg.norm(pts[30] - pts[27])
    radius = max(3, int(nose_len * 0.22))
    ycrcb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2YCrCb).astype(np.float32)
    samples = [pts[29], pts[28], (pts[29] + pts[33]) / 2]
    values = []
    for center in samples:
        x, y = int(center[0]), int(center[1])
        patch = ycrcb[max(0, y - radius):y + radius, max(0, x - radius):x + radius]
        if patch.size:
            values.append(patch.reshape(-1, 3).mean(axis=0))
    skin = np.median(np.asarray(values), axis=0)
    if skin[0] < 25 or skin[0] > 245:
        hull = cv2.convexHull(pts.astype(np.float32)).astype(np.int32)
        face_mask = np.zeros(image_bgr.shape[:2], np.uint8)
        cv2.fillPoly(face_mask, [hull], 255)
        pixels = ycrcb[face_mask > 0]
        skin = np.median(pixels, axis=0)
    return skin


def _match_chroma(region_bgr, alpha, template_skin, target_skin):
    visible = alpha > 0.05
    if not visible.any():
        return region_bgr
    delta = (target_skin - template_skin) * np.array([0.0, 0.4, 0.4])
    ycrcb = cv2.cvtColor(
        np.clip(region_bgr, 0, 255).astype(np.uint8), cv2.COLOR_BGR2YCrCb
    ).astype(np.float32)
    ycrcb[..., 1] += delta[1]
    ycrcb[..., 2] += delta[2]
    corrected = cv2.cvtColor(np.clip(ycrcb, 0, 255).astype(np.uint8), cv2.COLOR_YCrCb2BGR)
    out = region_bgr.copy()
    out[visible] = corrected[visible].astype(np.float32)
    return out


def _recolor_beard(region_bgr, alpha, target_ycrcb, y_scale=0.88):
    """Recolour the warped beard to the person's own hair tone.

    The templates are dark-bearded photos, so a blond subject would get a black
    beard. We shift the whole beard cloud onto a target tone derived from the
    hair (luminance *and* chroma). A constant shift keeps the beard's internal
    variation, so the strand detail survives. Returns the recoloured region and
    the resulting mean beard colour (BGR) for the base/strand layers.
    """
    visible = alpha > 0.05
    if not visible.any():
        return region_bgr, None

    ycrcb = cv2.cvtColor(
        np.clip(region_bgr, 0, 255).astype(np.uint8), cv2.COLOR_BGR2YCrCb
    ).astype(np.float32)

    current_mean = ycrcb[visible].mean(axis=0)
    target = np.array(target_ycrcb, np.float32).copy()
    target[0] *= y_scale  # a beard reads slightly darker than scalp hair

    shift = target - current_mean
    ycrcb += shift

    corrected = cv2.cvtColor(np.clip(ycrcb, 0, 255).astype(np.uint8), cv2.COLOR_YCrCb2BGR)
    out = region_bgr.copy()
    out[visible] = corrected[visible].astype(np.float32)
    beard_color = out[visible].mean(axis=0)
    return out, beard_color


def _extended_points(pts):
    """68 landmarks + 15 virtual points below the jaw so the warp mesh covers
    the under-jaw beard band (the convex hull of the 68 ends at the jaw line)."""
    p = np.asarray(pts, np.float32)
    face_h = np.linalg.norm(p[8] - (p[19] + p[24]) / 2)
    drop = np.array([0.0, face_h * 0.18], np.float32)
    virtual = p[1:16] + drop
    return np.vstack([p, virtual])


def _multiply_layer(base, layer_rgb, alpha, floor=0.45):
    """Alpha compositing with multiply blend: the skin's own shading shows
    through the beard, giving volume instead of a flat sticker."""
    mult = floor + (1.0 - floor) * (layer_rgb / 255.0)
    darkened = base * mult
    return base * (1.0 - alpha[..., None]) + darkened * alpha[..., None]


def _gradient_detail(texture_rgb, face_w):
    """High-frequency content of the real beard texture = the individual hairs.

    Gradient-domain transfer: we keep only the detail (texture minus its own
    low-pass) so the crisp hair strands can be re-injected onto the face,
    without dragging along the template's flat colour/brightness.
    """
    sigma = max(1.0, face_w / 70.0)
    low = cv2.GaussianBlur(texture_rgb, (0, 0), sigma)
    return texture_rgb - low


def _inject_detail(out, texture_rgb, weight, face_w, gain):
    detail = _gradient_detail(texture_rgb, face_w)
    return out + detail * weight[..., None] * gain


ANCHOR_IDX = [0, 16, 27, 28, 29, 30, 31, 35] + list(range(36, 48))


def barycentric_locate(points, ref_points, triangles):
    """Find, for each point, the reference triangle that contains it and its
    barycentric weights (l1, l2, l3) with p = l1*A + l2*B + l3*C."""
    origins = np.asarray(points, np.float64)
    A = ref_points[triangles[:, 0]].astype(np.float64)
    B = ref_points[triangles[:, 1]].astype(np.float64)
    C = ref_points[triangles[:, 2]].astype(np.float64)
    v0, v1 = B - A, C - A
    d00 = (v0 * v0).sum(-1)
    d01 = (v0 * v1).sum(-1)
    d11 = (v1 * v1).sum(-1)
    denom = d00 * d11 - d01 * d01
    denom = np.where(np.abs(denom) < 1e-9, np.nan, denom)
    v2 = origins[:, None, :] - A[None]
    d20 = (v2 * v0[None]).sum(-1)
    d21 = (v2 * v1[None]).sum(-1)
    with np.errstate(invalid="ignore"):
        v = (d11 * d20 - d01 * d21) / denom
        wt = (d00 * d21 - d01 * d20) / denom
        u = 1.0 - v - wt
        inside = (u >= -1e-6) & (v >= -1e-6) & (wt >= -1e-6)
    first = inside.argmax(axis=1)
    rows = np.arange(len(origins))
    bary = np.stack([u[rows, first], v[rows, first], wt[rows, first]], axis=1)
    return first, bary, inside.any(axis=1)


def barycentric_map(origins, tri, bary, valid, triangles, current_points, similarity):
    """Move reference points onto the current mesh; points outside the mesh
    fall back to the global similarity transform."""
    corners = current_points[triangles[tri]]
    pos = (bary[:, :, None] * corners).sum(axis=1)
    fallback = ~valid
    if fallback.any():
        pos[fallback] = cv2.transform(
            np.asarray(origins, np.float32)[fallback].reshape(-1, 1, 2), similarity,
        ).reshape(-1, 2)
    return pos.astype(np.float32)


class LiveAnchor:
    def __init__(self, pts, shape, style):
        h, w = shape
        self.shape = shape
        self.style = style
        self.ref = np.asarray(pts, np.float32).copy()
        self.M = np.array([[1, 0, 0], [0, 1, 0]], np.float32)
        self.stale = False
        self.strands = None
        self.triangles = None
        rng = np.random.default_rng(5)
        self.streak_noise = rng.random((h, w)).astype(np.float32)
        grain = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 1.5)
        self.grain = (grain - grain.min()) / (np.ptp(grain) + 1e-6)
        edge = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 2.0)
        self.edge_noise = (edge - edge.min()) / (np.ptp(edge) + 1e-6) - 0.5
        fine = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 0.45)
        self.fine_noise = (fine - fine.mean()) / (fine.std() + 1e-6)

    def update(self, pts):
        M, _ = cv2.estimateAffinePartial2D(
            self.ref[ANCHOR_IDX].reshape(-1, 1, 2),
            np.asarray(pts, np.float32)[ANCHOR_IDX].reshape(-1, 1, 2),
            method=cv2.LMEDS,
        )
        if M is not None:
            self.M = M.astype(np.float32)
            scale = float(np.hypot(M[0, 0], M[1, 0]))
            self.stale = not 0.6 < scale < 1.7

    def compute(self, dst_ext, focus):
        h, w = self.shape
        if getattr(self, "packed", None) is None:
            self.ensure_mesh()
            self.packed = np.stack(
                [self.streak_noise - 0.5, self.grain - 0.5, self.edge_noise, self.fine_noise],
                axis=-1,
            ).astype(np.float32)
        self.cur_ext = np.asarray(dst_ext, np.float32)
        tri = warp_template(self.packed, self.ref_ext, self.cur_ext, self.triangles, (h, w), focus)
        covered = np.abs(tri).sum(axis=2) > 0
        sim = cv2.warpAffine(
            self.packed, self.M, (w, h), flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )
        out = np.where(covered[..., None], tri, sim)
        x0, y0, x1, y1 = (int(v) for v in focus)
        window = out[max(0, y0):y1 + 1, max(0, x0):x1 + 1].reshape(-1, 4)
        if len(window) > 16:
            spread = window.std(axis=0) + 1e-6
            if getattr(self, "packed_std", None) is None:
                self.packed_std = self.packed.reshape(-1, 4).std(axis=0)
            target = self.packed_std
            center = window.mean(axis=0)
            out = center + (out - center) * (target / spread)
        self.t_streak = out[..., 0] + 0.5
        self.t_grain = out[..., 1] + 0.5
        self.t_edge = out[..., 2]
        self.t_fine = out[..., 3]

    def ensure_mesh(self):
        if self.triangles is None:
            self.ref_ext = _extended_points(self.ref)
            self.triangles = np.asarray(delaunay_triangles(self.ref_ext))

    def locate_origins(self):
        self.ensure_mesh()
        self.strand_tri, self.strand_bary, self.strand_valid = barycentric_locate(
            self.strands["origins"], self.ref_ext, self.triangles,
        )

    def map_origins(self, count):
        return barycentric_map(
            self.strands["origins"][:count], self.strand_tri[:count], self.strand_bary[:count],
            self.strand_valid[:count], self.triangles, self.cur_ext, self.M,
        )

    def warp(self, image):
        h, w = self.shape
        return cv2.warpAffine(
            image, self.M, (w, h), flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )

    def build_strands(self, region, style):
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
        area = cv2.dilate((region > 0).astype(np.uint8), kernel)
        ys, xs = np.where(area > 0)
        rng = np.random.default_rng(7)
        fraction = {"stubble": 0.04, "full": 0.06, "mustache": 0.06}.get(style, 0.10)
        count = min(int(len(xs) * fraction), 9000)
        chosen = rng.choice(len(xs), size=count, replace=False)
        stubble = style == "stubble"
        self.strands = {
            "origins": np.stack([xs[chosen], ys[chosen]], axis=1).astype(np.float32),
            "length": rng.uniform(0.012, 0.025, count) if stubble else rng.uniform(0.045, 0.10, count),
            "curl": rng.uniform(-0.7, 0.7, count),
            "jitter": rng.uniform(0.6, 1.0, count) if style in ("stubble", "goatee") else rng.uniform(0.72, 1.08, count),
            "alpha": rng.integers(150, 235, count),
            "thickness": np.ones(count, int) if stubble else rng.choice([1, 1, 2], size=count, p=[0.5, 0.32, 0.18]),
        }
        self.locate_origins()


def _anchored_strand_layer(anchor, region, dx, dy, style, face_w, density, tint):
    """Same strands as _strand_layer, but anchored to the mesh and drawn in
    batches: strands are grouped by (tone, opacity, thickness) so each group is
    a single cv2.polylines call instead of one call per strand."""
    h, w = region.shape
    if anchor.strands is None:
        anchor.build_strands(region, style)
    data = anchor.strands
    count = int(len(data["origins"]) * density)
    canvas = np.zeros((h, w, 4), np.uint8)
    if count == 0:
        return np.zeros((h, w, 3), np.float32), np.zeros((h, w), np.float32)
    pos = anchor.map_origins(count)
    ix = np.floor(pos[:, 0]).astype(int)
    iy = np.floor(pos[:, 1]).astype(int)
    inside = (ix >= 0) & (ix < w) & (iy >= 0) & (iy < h)
    inside[inside] = region[iy[inside], ix[inside]] > 0
    keep = np.where(inside)[0]
    if len(keep) == 0:
        return np.zeros((h, w, 3), np.float32), np.zeros((h, w), np.float32)
    p0 = pos[keep].astype(np.float32)
    ux = dx[iy[keep], ix[keep]][:, None]
    uy = dy[iy[keep], ix[keep]][:, None]
    unit = np.concatenate([ux, uy], axis=1)
    length = (face_w * data["length"][keep])[:, None]
    curl = data["curl"][keep][:, None]
    p1 = p0 + unit * length * 0.5 + np.concatenate([curl * length * 0.2, np.zeros_like(curl)], axis=1)
    p2 = p0 + unit * length + np.concatenate([curl * length * 0.7, -np.abs(ux) * length * 0.12], axis=1)
    t = np.linspace(0, 1, 6)[None, :, None]
    curves = (1 - t) ** 2 * p0[:, None] + 2 * (1 - t) * t * p1[:, None] + t ** 2 * p2[:, None]
    curves = np.round(curves * 16).astype(np.int32)
    jitter = data["jitter"][keep]
    alpha = data["alpha"][keep]
    thick = data["thickness"][keep]
    tones = np.linspace(jitter.min(), jitter.max() + 1e-6, 7)
    tone_bin = np.clip(np.digitize(jitter, tones) - 1, 0, 5)
    alpha_bin = np.clip(((alpha - 150) / 85 * 3).astype(int), 0, 2)
    tint = np.asarray(tint, np.float32)
    for tb in range(6):
        factor = 0.5 * (tones[tb] + tones[tb + 1])
        for ab in range(3):
            for th in (1, 2):
                pick = (tone_bin == tb) & (alpha_bin == ab) & (thick == th)
                if not pick.any():
                    continue
                color = tuple(float(c) for c in tint * factor) + (165.0 + 28.0 * ab,)
                cv2.polylines(canvas, list(curves[pick]), False, color, th, cv2.LINE_AA, shift=4)
    canvas = cv2.GaussianBlur(canvas, (3, 3), 0)
    return canvas[..., :3].astype(np.float32), canvas[..., 3].astype(np.float32) / 255.0


def apply_real_beard(
    image_bgr, points, style, strength, templates,
    base_strength=0.26, texture_strength=1.0, hair_yccrb=None, anchor=None, live_detail=True,
):
    h, w = image_bgr.shape[:2]
    pts = np.asarray(points, np.float32)

    pool = [t for t in templates if t["category"] == style]
    if not pool:
        return None

    target_skin = _target_skin_ycrcb(image_bgr, pts)
    best = min(
        pool,
        key=lambda t: (t["skin_ycrcb"][1] - target_skin[1]) ** 2
        + (t["skin_ycrcb"][2] - target_skin[2]) ** 2,
    )

    src_points = _extended_points(best["points"])
    dst_points = _extended_points(pts)
    clamp = beard_mask((h, w), pts, "full")
    rows = np.where((clamp > 0).any(axis=1))[0]
    cols = np.where((clamp > 0).any(axis=0))[0]
    focus = (cols.min(), rows.min(), cols.max(), rows.max())

    hair_tint = None
    if anchor is not None and not live_detail:
        warped_rgb = np.zeros((h, w, 3), np.float32)
        warped_alpha = np.zeros((h, w), np.float32)
        if hair_yccrb is not None:
            target = np.array(hair_yccrb, np.float32).copy()
            target[0] *= 0.88
            hair_tint = cv2.cvtColor(
                np.clip(target, 0, 255).astype(np.uint8).reshape(1, 1, 3), cv2.COLOR_YCrCb2BGR,
            )[0, 0].astype(np.float32)
    else:
        triangles = delaunay_triangles(dst_points)
        warped = warp_template(best["bgra"], src_points, dst_points, triangles, (h, w), focus)
        warped_rgb = warped[..., :3]
        warped_alpha = warped[..., 3] / 255.0
        if hair_yccrb is not None:
            warped_rgb, hair_tint = _recolor_beard(warped_rgb, warped_alpha, hair_yccrb)

    face_w = np.linalg.norm(pts[16] - pts[0])
    feather = max(6.0, min(30.0, face_w / 14.0))
    density = float(np.clip(strength, 0.0, 1.0))
    rng = np.random.default_rng(5)
    if anchor is not None:
        anchor.update(pts)
    lighting = None
    detail_scale = 1.0
    density_field = None
    refined = anchor is not None and style in ("stubble", "goatee")
    if anchor is not None:
        anchor.compute(dst_points, focus)
    if refined:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        light = cv2.GaussianBlur(gray, (0, 0), max(2.0, face_w / 12.0))
        lighting = light
        yaw = float((pts[30, 0] - (pts[0, 0] + pts[16, 0]) / 2) / max(face_w, 1.0))
        detail_scale = float(np.clip(1.0 - (abs(yaw) - 0.12) / 0.25, 0.0, 1.0))

    # Coverage comes from the anatomical beard region for THIS style (even and
    # symmetric), not from the template's own patchy alpha. The warped template
    # is used only for bonus texture/detail further below. This is what removes
    # the holes, the left/right asymmetry and the stubble "clumps".
    region = beard_mask((h, w), pts, style)
    if style != "full":
        face_hull = np.zeros((h, w), np.uint8)
        cv2.fillConvexPoly(face_hull, cv2.convexHull(pts).astype(np.int32), 255)
        grow = max(1, int(face_w * 0.03))
        face_hull = cv2.dilate(face_hull, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * grow + 1, 2 * grow + 1)))
        region = cv2.bitwise_and(region, face_hull)
    if refined:
        nose = np.zeros((h, w), np.uint8)
        cv2.fillConvexPoly(nose, cv2.convexHull(pts[27:36]).astype(np.int32), 255)
        grow = max(2, int(face_w * 0.05))
        nose = cv2.dilate(nose, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * grow + 1, 2 * grow + 1)))
        region = cv2.subtract(region, nose)
        if style in ("full", "stubble"):
            jaw_line = np.zeros((h, w), np.uint8)
            cv2.polylines(jaw_line, [pts[:17].astype(np.int32)], False, 255, 1)
            jaw_dist = cv2.distanceTransform(255 - jaw_line, cv2.DIST_L2, 5)
            density_field = np.clip(1.15 - 0.85 * jaw_dist / (0.30 * face_w), 0.30, 1.0)
    region_alpha = organic_feather(
        region, feather, noise_scale=0.6,
        noise=anchor.t_edge if anchor is not None else None,
    )
    if density_field is not None:
        region_alpha = region_alpha * density_field.astype(np.float32)

    tex_visible = warped_alpha > 0.3
    if tex_visible.any():
        beard_color = warped_rgb[tex_visible].mean(axis=0)
    elif hair_tint is not None:
        beard_color = np.asarray(hair_tint, np.float32)
    else:
        beard_color = np.array([45.0, 37.0, 30.0], np.float32)

    dx, dy, _ = _direction_maps(pts, h, w)
    if anchor is not None:
        streak = _streak_texture(
            rng, h, w, dx, dy, max(5.0, face_w / 45.0),
            noise=anchor.t_streak,
        )
        grain = anchor.t_grain
    else:
        streak = _streak_texture(rng, h, w, dx, dy, max(5.0, face_w / 45.0))
        grain = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 1.5)
        grain = (grain - grain.min()) / (np.ptp(grain) + 1e-6)

    # 1) Even body: uniform darkening across the whole region, only mild
    #    streak/grain variation so the density reads the same everywhere.
    body_strength = {"full": 0.55, "goatee": 0.55, "mustache": 0.50, "stubble": 0.20}[style]
    body_alpha = region_alpha * (0.78 + 0.22 * streak) * body_strength * density
    body_rgb = np.empty((h, w, 3), np.float32)
    for channel in range(3):
        body_rgb[..., channel] = beard_color[channel] * (0.90 + 0.20 * grain)
    out = _multiply_layer(image_bgr.astype(np.float32), body_rgb, body_alpha, floor=0.35)

    if lighting is not None:
        reference = float(lighting[region > 0].mean()) if (region > 0).any() else 1.0
        light_ratio = np.clip(lighting / max(reference, 1.0), 0.75, 1.25).astype(np.float32)
    else:
        light_ratio = None

    if style == "stubble":
        if anchor is not None:
            fine = anchor.t_fine
        else:
            raw = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 0.45)
            fine = (raw - raw.mean()) / (raw.std() + 1e-6)
        low = cv2.GaussianBlur(region_alpha, (0, 0), max(2.0, face_w / 25.0))
        threshold = 0.95 - 1.2 * density - 0.25 * (low - 0.5)
        dots = np.clip((fine - threshold) * 1.1, 0.0, 1.0)
        dot_alpha = (region_alpha * dots * 0.5)[..., None]
        dot_rgb = np.asarray(beard_color, np.float32).reshape(1, 1, 3) * 0.85
        if light_ratio is not None:
            dot_rgb = dot_rgb * light_ratio[..., None]
        out = out * (1.0 - dot_alpha) + dot_rgb * dot_alpha
        return np.clip(out, 0, 255).astype(np.uint8)

    # 2) Drawn strands over the whole region -> crisp, evenly distributed hair.
    if anchor is not None:
        strand_rgb, strand_alpha = _anchored_strand_layer(
            anchor, region, dx, dy, style, face_w, density, beard_color,
        )
    else:
        strand_rgb, strand_alpha = _strand_layer(
            rng, region, dx, dy, style, face_w, density, None, tint=beard_color,
        )
    if anchor is not None and style in ("goatee", "stubble"):
        strand_gain = 0.8 if style != "stubble" else 0.65
    else:
        strand_gain = 0.55 if style != "stubble" else 0.45
    if light_ratio is not None:
        strand_rgb = strand_rgb * light_ratio[..., None]
    strand_alpha = strand_alpha * region_alpha * strand_gain
    out = out * (1.0 - strand_alpha[..., None]) + strand_rgb * strand_alpha[..., None]

    # 3) Bonus real-hair detail where the warped template actually provides it.
    if anchor is not None and not live_detail:
        detail_scale = 0.0
    if detail_scale > 0:
        detail_w = region_alpha * np.clip(warped_alpha, 0.0, 1.0) * density * detail_scale
        detail_gain = 1.0 if style == "stubble" else 1.3
        out = _inject_detail(out, warped_rgb, detail_w, face_w, detail_gain)

    return np.clip(out, 0, 255).astype(np.uint8)


def apply_beard(image_bgr, points, style, strength):
    h, w = image_bgr.shape[:2]
    pts = np.asarray(points, np.float32)
    mask = beard_mask((h, w), pts, style)
    density = STYLES[style]["density"] * float(np.clip(strength, 0.0, 1.0))
    face_w = np.linalg.norm(pts[16] - pts[0])

    rng = np.random.default_rng(11)
    dx, dy, band = _direction_maps(pts, h, w)
    streak = _streak_texture(rng, h, w, dx, dy, max(5.0, face_w / 45.0))
    grain = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 1.5)
    grain = (grain - grain.min()) / (np.ptp(grain) + 1e-6)

    feather = max(3.0, min(14.0, face_w / 26.0))
    region_alpha = inside_feather(mask, feather)

    base_alpha = region_alpha * (0.30 + 0.55 * streak) * (0.75 * density)
    base_color = np.empty((h, w, 3), np.float32)
    for channel in range(3):
        base_color[..., channel] = PALETTE[1][channel] * (0.7 + 0.6 * grain)

    out = image_bgr.astype(np.float32) * (1.0 - base_alpha[..., None]) + base_color * base_alpha[..., None]

    strand_rgb, strand_alpha = _strand_layer(rng, mask, dx, dy, style, face_w, density, band)
    strand_alpha = strand_alpha * region_alpha * (0.85 if style != "stubble" else 0.6)
    out = out * (1.0 - strand_alpha[..., None]) + strand_rgb * strand_alpha[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)
