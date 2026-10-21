import time
from pathlib import Path

import cv2
import numpy as np

from app.core.compositing.beard import barycentric_locate
from app.core.detection.one_euro import OneEuroFilter
from app.core.geometry.delaunay_fortune import delaunay_triangles

MODELS_DIR = Path(__file__).resolve().parents[3] / "models"
SIDE_A, SIDE_B = 234, 454
GAUSSIAN_FLOATS = 17


class MeshTracker:
    """MediaPipe 478-point face mesh with depth: (x*w, y*h, z*w) in pixels.

    IMAGE mode for scan photos; VIDEO mode + One-Euro filter for the live avatar.
    """

    def __init__(self, live=False):
        self.live = live
        self._landmarker = None
        self._last_ms = 0
        self._filter = OneEuroFilter(min_cutoff=2.0, beta=0.2)

    def _ensure(self):
        if self._landmarker is None:
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision

            options = vision.FaceLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(MODELS_DIR / "face_landmarker.task")),
                running_mode=vision.RunningMode.VIDEO if self.live else vision.RunningMode.IMAGE,
                num_faces=1,
            )
            self._landmarker = vision.FaceLandmarker.create_from_options(options)
        return self._landmarker

    def mesh(self, image_bgr):
        import mediapipe as mp

        landmarker = self._ensure()
        frame = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
        if self.live:
            now = max(self._last_ms + 1, int(time.monotonic() * 1000))
            self._last_ms = now
            result = landmarker.detect_for_video(frame, now)
        else:
            result = landmarker.detect(frame)
        if not result.face_landmarks:
            if self.live:
                self._filter.reset()
            return None
        h, w = image_bgr.shape[:2]
        mesh = np.array([[p.x * w, p.y * h, p.z * w] for p in result.face_landmarks[0]], np.float32)
        if self.live:
            mesh = self._filter(mesh, self._last_ms / 1000.0)
        return mesh


def face_width(mesh):
    return float(np.linalg.norm(mesh[SIDE_A] - mesh[SIDE_B]))


def oriented_triangles(mesh):
    """Delaunay on the reference view, with every triangle wound so that its
    normal points to the camera (negative z in MediaPipe space). The fixed
    winding lets any later frame rebuild a consistent triangle frame."""
    tris = np.asarray(delaunay_triangles(mesh[:, :2]))
    a, b, c = (mesh[tris[:, k]] for k in range(3))
    normal_z = np.cross(b - a, c - a)[:, 2]
    flip = normal_z > 0
    tris[flip] = tris[flip][:, [0, 2, 1]]
    return tris


def triangle_frames(mesh, tris):
    """Per-triangle orthonormal frame R = [e1 e2 n] (columns)."""
    a, b, c = (mesh[tris[:, k]].astype(np.float64) for k in range(3))
    e1 = b - a
    e1 /= np.linalg.norm(e1, axis=1, keepdims=True) + 1e-9
    n = np.cross(b - a, c - a)
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-9
    e2 = np.cross(n, e1)
    return np.stack([e1, e2, n], axis=2), n


def _sample(image_bgr, xy):
    h, w = image_bgr.shape[:2]
    x = np.clip(xy[:, 0], 0, w - 1.001)
    y = np.clip(xy[:, 1], 0, h - 1.001)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    img = image_bgr.astype(np.float32)
    top = img[y0, x0] * (1 - fx) + img[y0, x0 + 1] * fx
    bottom = img[y0 + 1, x0] * (1 - fx) + img[y0 + 1, x0 + 1] * fx
    return (top * (1 - fy) + bottom * fy)[:, ::-1] / 255.0


class AnchoredHead:
    """Gaussians glued to the face mesh.

    Every Gaussian stores: its triangle, barycentric weights, an offset and a
    covariance expressed in the triangle's local frame (in units of the
    reference face width), a color and an opacity. Given ANY mesh of the same
    topology (another scan view, or a live webcam frame), its world position is
    sum(bary * vertices) + R_t @ offset * scale and its covariance is
    R_t @ cov_local @ R_t^T * scale^2. That single representation powers both
    multi-view color fusion (B) and the live avatar (D).
    """

    def __init__(self, ref_mesh, tris):
        self.ref_mesh = ref_mesh.astype(np.float64)
        self.tris = tris
        self.fw = face_width(ref_mesh)
        self.tri = np.zeros(0, int)
        self.bary = np.zeros((0, 3))
        self.offset = np.zeros((0, 3))
        self.cov = np.zeros((0, 3, 3))
        self.color = np.zeros((0, 3))
        self.alpha = np.zeros(0)
        self.is_beard = np.zeros(0, bool)

    def add(self, tri, bary, offset, cov, color, alpha, beard=False):
        self.tri = np.concatenate([self.tri, tri])
        self.bary = np.concatenate([self.bary, bary])
        self.offset = np.concatenate([self.offset, offset])
        self.cov = np.concatenate([self.cov, cov])
        self.color = np.concatenate([self.color, color])
        self.alpha = np.concatenate([self.alpha, alpha])
        self.is_beard = np.concatenate([self.is_beard, np.full(len(tri), beard)])

    def place(self, mesh):
        """World positions, covariances and facing (n_z) of every Gaussian for a mesh."""
        mesh = mesh.astype(np.float64)
        frames, normals = triangle_frames(mesh, self.tris)
        scale = face_width(mesh) / self.fw
        corners = mesh[self.tris[self.tri]]
        R = frames[self.tri]
        pos = (self.bary[:, :, None] * corners).sum(axis=1) + np.einsum("nij,nj->ni", R, self.offset) * self.fw * scale
        cov = np.einsum("nij,njk,nlk->nil", R, self.cov, R) * (self.fw * scale) ** 2
        return pos, cov, normals[self.tri][:, 2]

    def pack(self):
        cov = self.cov
        upper = np.stack([cov[:, 0, 0], cov[:, 0, 1], cov[:, 0, 2], cov[:, 1, 1], cov[:, 1, 2], cov[:, 2, 2]], axis=1)
        rows = np.concatenate([
            self.tri[:, None].astype(np.float64), self.bary, self.offset, upper, self.color, self.alpha[:, None],
        ], axis=1)
        return rows.astype(np.float32)


def _surface(head, rng, budget):
    mesh, tris = head.ref_mesh, head.tris
    a, b, c = (mesh[tris[:, k]] for k in range(3))
    area3d = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    counts = np.maximum(1, np.round(budget * area3d / area3d.sum())).astype(int)
    tri = np.repeat(np.arange(len(tris)), counts)
    starts = np.repeat(np.cumsum(counts) - counts, counts)
    rank = np.arange(len(tri)) - starts
    side = np.ceil(np.sqrt(counts[tri])).astype(int)
    u = (rank % side + rng.random(len(tri))) / side
    v = np.clip((rank // side + rng.random(len(tri))) / np.ceil(counts[tri] / side), 0, 1)
    flip = u + v > 1
    u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
    bary = np.stack([1 - u - v, u, v], axis=1)
    spacing = np.sqrt(np.maximum(area3d[tri] / counts[tri], 0.25)) / head.fw
    cov = np.zeros((len(tri), 3, 3))
    cov[:, 0, 0] = cov[:, 1, 1] = spacing ** 2
    cov[:, 2, 2] = (0.4 * spacing) ** 2
    head.add(tri, bary, np.zeros((len(tri), 3)), cov, np.zeros((len(tri), 3)), np.full(len(tri), 0.97))


def _beard(head, region, texture, style, rng):
    ys, xs = np.where(region > 0)
    if len(xs) == 0:
        return
    count = min(len(xs) // 4, 6000)
    pick = rng.choice(len(xs), size=count, replace=False)
    roots2d = np.stack([xs[pick], ys[pick]], axis=1).astype(np.float32)
    mesh = head.ref_mesh
    tri, bary, valid = barycentric_locate(roots2d, mesh[:, :2], head.tris)
    tri, bary, roots2d = tri[valid], bary[valid], roots2d[valid]
    frames, normals = triangle_frames(mesh, head.tris)
    R = frames[tri]
    toward = normals[tri]
    direction = 0.55 * toward + np.array([0.0, 1.0, 0.0]) + rng.normal(0, 0.18, toward.shape)
    direction /= np.linalg.norm(direction, axis=1, keepdims=True)
    fw = head.fw
    stubble = style == "stubble"
    length = rng.uniform(0.006, 0.014, len(tri)) if stubble else rng.uniform(0.02, 0.05, len(tri))
    segments = 1 if stubble else 3
    width = 0.002 if stubble else 0.0022
    base = _sample(texture, roots2d) * 0.92
    tone = rng.uniform(0.7, 1.0, (len(tri), 1))
    side = np.cross(direction, toward)
    side /= np.linalg.norm(side, axis=1, keepdims=True) + 1e-9
    third = np.cross(direction, side)
    strand = np.stack([direction, side, third], axis=2)
    for k in range(segments):
        t = (k + 0.5) / segments
        world_offset = direction * (length * t)[:, None] + toward * 0.004
        local_offset = np.einsum("nji,nj->ni", R, world_offset)
        scales = np.stack([length / segments * 0.6, np.full(len(tri), width), np.full(len(tri), width)], axis=1)
        world_cov = np.einsum("nij,nj,nkj->nik", strand, scales ** 2, strand)
        local_cov = np.einsum("nji,njk,nkl->nil", R, world_cov, R)
        head.add(tri, bary, local_offset, local_cov, np.clip(base * tone, 0, 1), np.full(len(tri), 0.55 - 0.25 * t), beard=True)


def _project(head, mesh, scale):
    pos, cov, facing = head.place(mesh)
    pos2 = pos[:, :2] * scale
    cov2 = cov[:, :2, :2] * scale * scale + np.eye(2) * 0.25
    return pos2, cov2, facing


def _splat_weights(pos2, cov2, facing, shape, radius=3):
    """Normalized-blend footprints of every Gaussian in a view (for fusion/optimization)."""
    h, w = shape
    inv = np.linalg.inv(cov2)
    span = np.arange(-radius, radius + 1, dtype=np.float64)
    oy, ox = np.meshgrid(span, span, indexing="ij")
    px = np.floor(pos2[:, 0])[:, None] + ox.ravel()[None]
    py = np.floor(pos2[:, 1])[:, None] + oy.ravel()[None]
    dx = px + 0.5 - pos2[:, 0][:, None]
    dy = py + 0.5 - pos2[:, 1][:, None]
    q = inv[:, 0, 0][:, None] * dx * dx + 2 * inv[:, 0, 1][:, None] * dx * dy + inv[:, 1, 1][:, None] * dy * dy
    visible = np.clip(-facing, 0, 1) ** 2
    g = np.exp(-0.5 * q) * visible[:, None]
    g = g * ((px >= 0) & (px < w) & (py >= 0) & (py < h))
    flat = (np.clip(py, 0, h - 1) * w + np.clip(px, 0, w - 1)).astype(np.int64)
    return g, flat


def _render(color, g, flat, size):
    weight = np.bincount(flat.ravel(), weights=g.ravel(), minlength=size)
    rgb = np.stack([np.bincount(flat.ravel(), weights=(g * color[:, ch][:, None]).ravel(), minlength=size) for ch in range(3)], 1)
    return rgb / np.maximum(weight, 1e-6)[:, None], weight


def _psnr(a, b, mask):
    mse = float(((a - b) ** 2)[mask].mean()) if mask.any() else 1.0
    return 10 * np.log10(1.0 / max(mse, 1e-10))


def build_scanned_head(views_bgr, meshes, beard_texture=None, beard_region=None, beard_style=None,
                       budget=40000, iterations=30, holdout=True, seed=5):
    """B: build an anchored head from several views and fuse + optimize its colors.

    1. Reference = the most frontal view (smallest nose offset from the face center).
    2. Anchored face Gaussians on its Delaunay mesh (+ optional 3D beard strands).
    3. Multi-view color fusion: each Gaussian is placed in every view through that
       view's own mesh; colors are averaged with weight = facing^2 (front-facing
       surfaces in that view count more).
    4. Photometric optimization: per-Gaussian colors refined with Adam so the
       normalized splat render matches every training view (face pixels only).
    One non-reference view is held out to measure generalization.
    """
    rng = np.random.default_rng(seed)
    yaw = [abs(float((m[1, 0] - 0.5 * (m[SIDE_A, 0] + m[SIDE_B, 0])) / max(face_width(m), 1.0))) for m in meshes]
    ref = int(np.argmin(yaw))
    tris = oriented_triangles(meshes[ref])
    head = AnchoredHead(meshes[ref], tris)
    _surface(head, rng, budget)
    if beard_region is not None and beard_style:
        _beard(head, beard_region, beard_texture, beard_style, rng)
    face = ~head.is_beard

    order = sorted(range(len(views_bgr)), key=lambda i: -yaw[i])
    held = order[0] if holdout and len(views_bgr) >= 3 and order[0] != ref else None
    train = [i for i in range(len(views_bgr)) if i != held]

    target_px = 220.0
    data = []
    for i, (img, mesh) in enumerate(zip(views_bgr, meshes)):
        scale = target_px / max(face_width(mesh), 1.0)
        small = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        pos2, cov2, facing = _project(head, mesh, scale)
        g, flat = _splat_weights(pos2[face], cov2[face], facing[face], small.shape[:2])
        hull = np.zeros(small.shape[:2], np.uint8)
        cv2.fillConvexPoly(hull, cv2.convexHull((mesh[:, :2] * scale).astype(np.float32)).astype(np.int32), 255)
        hull = cv2.erode(hull, np.ones((5, 5), np.uint8)) > 0
        target = small[..., ::-1].reshape(-1, 3).astype(np.float64) / 255.0
        sample = _sample(img, pos2[face] / scale)
        data.append(dict(g=g, flat=flat, target=target, mask=hull.ravel(), size=small.shape[0] * small.shape[1],
                         sample=sample, facing=np.clip(-facing[face], 0, 1) ** 2))

    ref_colors = data[ref]["sample"]
    num = sum(data[i]["sample"] * data[i]["facing"][:, None] * (1.5 if i == ref else 1.0) for i in train)
    den = sum(data[i]["facing"] * (1.5 if i == ref else 1.0) for i in train)[:, None]
    fused = num / np.maximum(den, 1e-6)

    def score(colors, idx):
        d = data[idx]
        img, weight = _render(colors, d["g"], d["flat"], d["size"])
        mask = d["mask"] & (weight > 1e-3)
        return _psnr(img, d["target"], mask)

    colors = fused.copy()
    m = np.zeros_like(colors)
    v = np.zeros_like(colors)
    for step in range(1, iterations + 1):
        grad = np.zeros_like(colors)
        for i in train:
            d = data[i]
            img, weight = _render(colors, d["g"], d["flat"], d["size"])
            mask = d["mask"] & (weight > 1e-3)
            err = np.where(mask[:, None], img - d["target"], 0.0)
            norm_err = err / np.maximum(weight, 1e-6)[:, None]
            per_pixel = norm_err[d["flat"]]
            grad += (per_pixel * d["g"][..., None]).sum(axis=1) * 2.0 / max(int(mask.sum()), 1)
        m = 0.9 * m + 0.1 * grad
        v = 0.999 * v + 0.001 * grad * grad
        colors -= 0.01 * (m / (1 - 0.9 ** step)) / (np.sqrt(v / (1 - 0.999 ** step)) + 1e-8)
        colors = np.clip(colors, 0, 1)

    metrics = {
        "views": len(views_bgr),
        "reference": int(ref),
        "held_out": None if held is None else int(held),
        "train_psnr": {
            "single_view": round(float(np.mean([score(ref_colors, i) for i in train])), 2),
            "fused": round(float(np.mean([score(fused, i) for i in train])), 2),
            "optimized": round(float(np.mean([score(colors, i) for i in train])), 2),
        },
    }
    if held is not None:
        metrics["held_out_psnr"] = {
            "single_view": round(float(score(ref_colors, held)), 2),
            "fused": round(float(score(fused, held)), 2),
            "optimized": round(float(score(colors, held)), 2),
        }
    if beard_region is not None and beard_style and beard_texture is not None:
        ref_mesh = meshes[ref]
        pos, _, _ = head.place(ref_mesh)
        inside = beard_region[np.clip(pos[face, 1].astype(int), 0, beard_region.shape[0] - 1),
                              np.clip(pos[face, 0].astype(int), 0, beard_region.shape[1] - 1)] > 0
        textured = _sample(beard_texture, pos[face, :2])
        colors[inside] = textured[inside]
    head.color[face] = colors

    return head, metrics
