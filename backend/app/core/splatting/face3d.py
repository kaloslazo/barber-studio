import cv2
import numpy as np

from app.core.lab.avatar import build_scanned_head, oriented_triangles
from app.core.splatting.hair3d import SKULL_AXES, SKULL_CENTER, _mannequin

EYES = [33, 246, 161, 133, 160, 159, 263, 466, 388, 362, 385, 373]
NEAR_EAR, FAR_EAR = 127, 356
FOREHEAD_RING = [54, 103, 67, 109, 10, 338, 297, 332, 284]
FOREHEAD_TOP, FOREHEAD_ROWS = -0.68, 12


class FaceView:
    def __init__(self, image_bgr, mesh, hair=None):
        self.image = image_bgr
        self.hair = hair
        self.mesh = np.asarray(mesh, np.float64)
        near, far = self.mesh[NEAR_EAR], self.mesh[FAR_EAR]
        self.yaw = float(np.degrees(np.arctan2(far[2] - near[2], far[0] - near[0])))


def head_frame(view):
    """Pixel -> peluca head frame for a view: origin between the ears at eye
    level, ear-to-ear width as unit, z towards the camera and the head turn
    undone. Returns (origin, width, M) with canonical = M @ (p - origin) / width."""
    mesh = view.mesh
    near, far = mesh[NEAR_EAR], mesh[FAR_EAR]
    width = float(np.linalg.norm(far - near))
    origin = np.array([(near[0] + far[0]) / 2, mesh[EYES, 1].mean(), (near[2] + far[2]) / 2])
    yaw = np.radians(view.yaw)
    cos, sin = np.cos(yaw), np.sin(yaw)
    turn = np.array([[cos, 0.0, -sin], [0.0, 1.0, 0.0], [sin, 0.0, cos]])
    return origin, width, turn @ np.diag([1.0, 1.0, -1.0])


def canonical_mesh(view):
    origin, width, M = head_frame(view)
    return (view.mesh - origin) @ M.T / width


def _inside(points, polygon):
    scaled = np.round(polygon * 1000).astype(np.int32)
    return np.array([cv2.pointPolygonTest(scaled, (float(x) * 1000, float(y) * 1000), False) >= 0 for x, y in points])


def _forehead_shell(canon, top=FOREHEAD_TOP, rows=FOREHEAD_ROWS):
    """Canonical vertices continuing the face mesh from its upper edge to the
    hairline height. MediaPipe's mesh stops half-way up the forehead; the
    rest follows an ellipsoid around the mannequin's skull centre whose width
    and depth are fitted to the scanned forehead, walked up its meridians so
    the columns close in like a real head. Returns (rows, len(ring), 3)."""
    upper = canon[canon[:, 1] < -0.2] - SKULL_CENTER
    rhs = 1 - (upper[:, 1] / SKULL_AXES[1]) ** 2
    coef = np.linalg.lstsq(upper[:, [0, 2]] ** 2, rhs, rcond=None)[0]
    axes = SKULL_AXES.copy()
    if (coef > 0).all():
        axes[[0, 2]] = 1 / np.sqrt(coef)
    q = (canon[FOREHEAD_RING] - SKULL_CENTER) / axes
    radius = np.linalg.norm(q, axis=1)
    q /= radius[:, None]
    start = np.arccos(np.clip(-q[:, 1], -1, 1))
    phi = np.arctan2(q[:, 2], q[:, 0])
    end = np.minimum(np.arccos(np.clip((SKULL_CENTER[1] - top) / axes[1], -1, 1)), start * 0.9)
    k = (np.arange(1, rows + 1) / rows)[:, None]
    t = start + (end - start) * k
    scale = 1 + (radius - 1) * (1 - k)
    unit = np.stack([np.sin(t) * np.cos(phi), -np.cos(t), np.sin(t) * np.sin(phi)], axis=-1)
    return SKULL_CENTER + unit * scale[..., None] * axes


def _strip_triangles(base, columns, rows):
    """Quads between the ring vertices (row 0) and the shell rows above."""
    index = np.vstack([np.asarray(FOREHEAD_RING)[None, :], base + np.arange(rows * columns).reshape(rows, columns)])
    a, b = index[:-1, :-1].ravel(), index[:-1, 1:].ravel()
    c, d = index[1:, :-1].ravel(), index[1:, 1:].ravel()
    return np.concatenate([np.stack([a, b, c], 1), np.stack([b, d, c], 1)])


def _similarity(src, dst):
    """Scaled rotation + translation mapping src points onto dst (Umeyama)."""
    mu_s, mu_d = src.mean(axis=0), dst.mean(axis=0)
    a, b = src - mu_s, dst - mu_d
    U, S, Vt = np.linalg.svd(b.T @ a)
    D = np.diag([1.0, 1.0, np.sign(np.linalg.det(U @ Vt))])
    R = U @ D @ Vt
    scale = np.trace(np.diag(S) @ D) / (a ** 2).sum()
    return lambda points: (points - mu_s) @ R.T * scale + mu_d


def _skin_fill(reference, mesh, forehead):
    """Smooth forehead skin colour at every pixel of the reference, spread
    from the skin the capture does see (normalized convolution), for the
    part of the forehead hidden under the person's own hair."""
    image = reference.image.astype(np.float32) / 255.0
    region = np.zeros(image.shape[:2], np.float32)
    cv2.fillConvexPoly(region, cv2.convexHull(mesh[forehead, :2].astype(np.float32)).astype(np.int32), 1.0)
    weight = region * (1 - np.clip((reference.hair - 0.3) / 0.4, 0, 1))
    width = float(np.linalg.norm(mesh[FAR_EAR] - mesh[NEAR_EAR]))
    fill = np.zeros_like(image)
    missing = np.ones(image.shape[:2], bool)
    for sigma in (0.08, 0.2, 0.5):
        total = cv2.GaussianBlur(weight, (0, 0), sigma * width)
        spread = cv2.GaussianBlur(image * weight[..., None], (0, 0), sigma * width) / np.maximum(total, 1e-6)[..., None]
        use = missing & (total > 0.05)
        fill[use] = spread[use]
        missing &= ~use
    if missing.any():
        fill[missing] = np.median(image[weight > 0.5], axis=0) if (weight > 0.5).any() else 0.75
    return fill[..., ::-1]


def scan_face(views):
    """The slow, peluca-independent part: the 3D Mirror (beta) scanned head,
    Gaussians anchored to the face mesh of the most frontal capture and
    coloured by multi-view fusion and photometric optimization over every
    capture, placed on the reference mesh in the peluca's head frame. The
    mesh is first extended up the whole forehead so it is scanned like the
    rest of the face; forehead hidden under the person's hair gets their
    skin tone instead of hair."""
    reference = min(views, key=lambda view: abs(view.yaw))
    canon = canonical_mesh(reference)
    shell = _forehead_shell(canon).reshape(-1, 3)
    origin, width, M = head_frame(reference)
    shell_pixels = shell @ M * width + origin
    rigid = canon[:, 1] < 0.05
    meshes = []
    for view in views:
        place = _similarity(reference.mesh[rigid], view.mesh[rigid])
        meshes.append(np.vstack([view.mesh, place(shell_pixels)]))
    ref_mesh = meshes[views.index(reference)]
    base = oriented_triangles(reference.mesh)
    strip = _strip_triangles(len(reference.mesh), len(FOREHEAD_RING), FOREHEAD_ROWS)
    tris = oriented_triangles(ref_mesh, np.vstack([base, strip]))
    scanned, _ = build_scanned_head([view.image for view in views], meshes, holdout=False, tris=tris)
    pos, cov, _ = scanned.place(ref_mesh)
    color = scanned.color.copy()
    forehead = scanned.tri >= len(base)
    if reference.hair is not None and forehead.any():
        upper = np.flatnonzero(canonical_mesh(FaceView(reference.image, ref_mesh))[:, 1] < -0.2)
        fill = _skin_fill(reference, ref_mesh, upper)
        h, w = reference.hair.shape
        x = np.clip(pos[forehead, 0].astype(int), 0, w - 1)
        y = np.clip(pos[forehead, 1].astype(int), 0, h - 1)
        hair = cv2.GaussianBlur(reference.hair, (0, 0), 0.02 * width)
        blend = np.clip((hair[y, x] - 0.3) / 0.4, 0, 1)[:, None]
        color[forehead] = color[forehead] * (1 - blend) + fill[y, x] * blend
    return {
        "views": views,
        "reference": reference,
        "mesh": (ref_mesh - origin) @ M.T / width,
        "forehead": forehead,
        "pos": (pos - origin) @ M.T / width,
        "cov": np.einsum("ij,njk,lk->nil", M, cov, M) / width ** 2,
        "color": color,
        "alpha": scanned.alpha,
    }


def face_scan_debug_image(scan):
    """Return the reference image with the mesh and detected hairline."""
    reference = scan["reference"]
    image = reference.image.copy()
    origin, width, _ = head_frame(reference)
    canon = canonical_mesh(reference)
    x0 = int(round(origin[0] - SKULL_AXES[0] * width))
    x1 = int(round(origin[0] + SKULL_AXES[0] * width))
    mesh_y = int(round(origin[1] + canon[:, 1].min() * width))
    height, image_width = image.shape[:2]
    x0, x1 = max(0, x0), min(image_width - 1, x1)
    mesh_y = int(np.clip(mesh_y, 0, height - 1))
    cv2.line(image, (x0, mesh_y), (x1, mesh_y), (255, 255, 0), 3)
    cv2.putText(image, "face mesh top", (x0 + 8, max(24, mesh_y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 0), 2, cv2.LINE_AA)
    if reference.hair is not None:
        hair = reference.hair > 0.5
        columns = np.linspace(x0, x1, 25).astype(int)
        hairline = []
        for x in columns:
            rows = np.flatnonzero(hair[:, x] & (np.arange(height) <= mesh_y))
            if len(rows):
                hairline.append((x, int(rows.max())))
        if len(hairline) >= 2:
            cv2.polylines(image, [np.asarray(hairline, np.int32)], False, (0, 0, 255), 3)
            label_x, label_y = hairline[len(hairline) // 2]
            cv2.putText(image, "detected hairline", (label_x + 8, max(24, label_y - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2, cv2.LINE_AA)
    return image


def face_splats(scan, axes=SKULL_AXES, head=9000, seed=11):
    """The person's own head in Gaussians around a skull of the given axes:
    the scanned face and forehead, and the mannequin skull and neck painted
    in the person's skin tone. Returns (pos, cov, color, alpha) before the
    viewer transform."""
    rng = np.random.default_rng(seed)
    pos, cov, color, alpha = scan["pos"], scan["cov"], scan["color"], scan["alpha"]
    keep = ~scan["forehead"] | (pos[:, 1] >= SKULL_CENTER[1] - 0.83 * axes[1])
    pos, cov, color, alpha = pos[keep], cov[keep], color[keep], alpha[keep]
    cheeks = pos[:, 2] > np.percentile(pos[:, 2], 60)
    skin = np.median(color[cheeks], axis=0)
    h_pos, h_cov, h_color, h_alpha = _mannequin(head, rng, axes)
    hull = cv2.convexHull(scan["mesh"][:, :2].astype(np.float32)).reshape(-1, 2)
    keep = ~((h_pos[:, 2] > 0) & _inside(h_pos[:, :2], hull))
    h_color = skin[None, :] * (h_color[:, :1] / 0.80)
    parts = [(pos, cov, color, alpha), (h_pos[keep], h_cov[keep], h_color[keep], h_alpha[keep])]
    return tuple(np.concatenate([part[k] for part in parts]) for k in range(4))
