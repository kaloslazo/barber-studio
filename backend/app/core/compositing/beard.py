import cv2
import numpy as np

from app.core.compositing.alpha import inside_feather, organic_feather
from app.core.geometry.delaunay import delaunay_triangles
from app.core.geometry.warp import warp_template

try:
    from pathlib import Path
    ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets/beards"
except ImportError:
    ASSETS_DIR = None

JAW = list(range(0, 17))
CHIN_SECTOR = list(range(3, 14))
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
        outer = _expand(pts[CHIN_SECTOR], centroid, face_w * 0.04)
        mask = _polygon_mask((h, w), outer)
        mask = cv2.subtract(mask, mouth_hole)
        mask = cv2.add(mask, _mustache_band((h, w), pts))

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


def _streak_texture(rng, h, w, dx, dy, length_px, bins=12):
    """Anisotropic noise: noise streaked along the local hair direction."""
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


def _bezier(p0, p1, p2, samples=6):
    t = np.linspace(0, 1, samples)[:, None]
    points = (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t**2 * p2
    return points.astype(np.int32)


def _strand_layer(rng, mask, dx, dy, style, face_w, density, band):
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

        color = PALETTE[int(rng.integers(0, len(PALETTE)))]
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


def apply_real_beard(
    image_bgr, points, style, strength, templates,
    base_strength=0.18, texture_strength=1.0, hair_yccrb=None,
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
    triangles = delaunay_triangles(dst_points)
    clamp = beard_mask((h, w), pts, "full")
    rows = np.where((clamp > 0).any(axis=1))[0]
    cols = np.where((clamp > 0).any(axis=0))[0]
    focus = (cols.min(), rows.min(), cols.max(), rows.max())

    warped = warp_template(best["bgra"], src_points, dst_points, triangles, (h, w), focus)
    warped_rgb = warped[..., :3]
    warped_alpha = warped[..., 3] / 255.0

    if hair_yccrb is not None:
        warped_rgb = _match_chroma(warped_rgb, warped_alpha, best["skin_ycrcb"], hair_yccrb)

    face_w = np.linalg.norm(pts[16] - pts[0])
    feather = max(6.0, min(30.0, face_w / 14.0))
    clamp_alpha = organic_feather(clamp, feather, noise_scale=1.0)
    density = float(np.clip(strength, 0.0, 1.0))

    if style == "goatee":
        warped_alpha = np.power(np.clip(warped_alpha, 0.0, 1.0), 2.0)

    clump = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), face_w / 18.0)
    clump = (clump - clump.min()) / (np.ptp(clump) + 1e-6)
    clump = np.clip((clump - 0.25) * 1.6, 0.0, 1.0)
    if style == "goatee":
        amp = 0.45
    elif style == "full":
        amp = 0.25
    else:
        amp = 0.0
    warped_alpha = warped_alpha * (1.0 - amp + amp * clump)

    texture_visible = warped_alpha > 0.5
    if texture_visible.any():
        beard_color = warped_rgb[texture_visible].mean(axis=0)
    else:
        beard_color = np.array([45.0, 37.0, 30.0], np.float32)

    shape_mask = ((warped_alpha > 0.08).astype(np.uint8)) * 255
    close_size = max(15, int(face_w / 12) | 1)
    shape_mask = cv2.morphologyEx(
        shape_mask, cv2.MORPH_CLOSE, np.ones((close_size, close_size), np.uint8)
    )
    shape_alpha = organic_feather(shape_mask, feather * 0.8, noise_scale=0.5, seed=7)

    rng = np.random.default_rng(5)
    dx, dy, _ = _direction_maps(pts, h, w)
    streak = _streak_texture(rng, h, w, dx, dy, max(5.0, face_w / 45.0))
    grain = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 1.5)
    grain = (grain - grain.min()) / (np.ptp(grain) + 1e-6)

    base_density = (base_strength if style != "stubble" else base_strength * 0.7) * density
    base_alpha = shape_alpha * (0.35 + 0.65 * streak) * base_density
    base_rgb = np.empty((h, w, 3), np.float32)
    for channel in range(3):
        base_rgb[..., channel] = beard_color[channel] * (0.85 + 0.3 * grain)

    img_float = image_bgr.astype(np.float32)
    out = _multiply_layer(img_float, base_rgb, base_alpha, floor=0.55)

    texture_alpha = warped_alpha * clamp_alpha * density * (
        0.55 if style == "stubble" else (0.8 if style == "goatee" else texture_strength)
    )
    texture_alpha = texture_alpha * (0.60 + 0.40 * streak)
    if style in ("mustache", "goatee"):
        seam_x = int(pts[33][0])
        x0 = max(0, seam_x - 8)
        seam_band = texture_alpha[:, x0:seam_x + 8]
        texture_alpha[:, x0:seam_x + 8] = cv2.GaussianBlur(seam_band, (21, 1), 4.0)
    if style == "mustache":
        band = _mustache_band((h, w), pts)
        band_alpha = inside_feather((band > 60).astype(np.uint8) * 255, feather)
        texture_alpha = texture_alpha * band_alpha
        out = _multiply_layer(out, warped_rgb, texture_alpha, floor=0.4)
        strand_rgb, strand_alpha = _strand_layer(
            rng, (band > 60).astype(np.uint8) * 255, dx, dy, style, face_w, density * 0.9, None
        )
        strand_alpha = strand_alpha * band_alpha * 0.5
        return np.clip(_multiply_layer(out, strand_rgb, strand_alpha, floor=0.5), 0, 255).astype(np.uint8)
    out = _multiply_layer(out, warped_rgb, texture_alpha, floor=0.4)
    if style in ("full", "goatee"):
        strand_rgb, strand_alpha = _strand_layer(
            rng, clamp, dx, dy, style, face_w, density * 0.9, None
        )
        strand_alpha = strand_alpha * clamp_alpha * 0.5
        out = _multiply_layer(out, strand_rgb, strand_alpha, floor=0.5)
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
