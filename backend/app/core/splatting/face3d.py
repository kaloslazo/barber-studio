import cv2
import numpy as np

from app.core.lab.avatar import build_scanned_head
from app.core.splatting.head3d import _sample_color
from app.core.splatting.hair3d import SKULL_AXES, SKULL_CENTER, _covariance, _frame, _mannequin

EYES = [33, 246, 161, 133, 160, 159, 263, 466, 388, 362, 385, 373]
NEAR_EAR, FAR_EAR = 127, 356


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


def _view_colors(views, reference, pos, normal, power=8, favour=1.0):
    """Colour of canonical points seen through every capture, weighted by
    how squarely each capture faces them."""
    color = np.zeros((len(pos), 3))
    weight = np.zeros(len(pos))
    for view in views:
        origin, width, M = head_frame(view)
        pixels = pos @ M * width + origin
        toward = M @ np.array([0.0, 0.0, -1.0])
        share = np.clip(normal @ toward, 0, 1) ** power * (favour if view is reference else 1.0) + (1e-4 if view is reference else 0.0)
        color += _sample_color(view.image, pixels[:, :2]) * share[:, None]
        weight += share
    return color / weight[:, None]


def _hairline(reference, canon_points):
    """Index of the first point (walking up) that the frontal capture sees
    as hair, or None."""
    if reference.hair is None:
        return None
    origin, width, M = head_frame(reference)
    pixels = canon_points @ M * width + origin
    h, w = reference.hair.shape
    x = np.clip(pixels[:, 0].astype(int), 0, w - 1)
    y = np.clip(pixels[:, 1].astype(int), 0, h - 1)
    hits = np.flatnonzero(reference.hair[y, x] > 0.5)
    return int(hits[0]) if len(hits) else None


def _forehead(views, reference, canon, axes, step=0.006):
    """The forehead from the top of the face mesh up to the real hairline.

    MediaPipe's mesh stops half-way up the forehead. Each column of the
    forehead keeps the slope it has at the top of the mesh, bending slightly
    backwards, until the frontal capture sees hair; only above that hairline
    does the surface ease onto the skull. Colours come from the captures."""
    bins = np.arange(-0.44, 0.44 + 1e-9, step)
    top_y = np.full(len(bins), np.nan)
    top_z = np.full(len(bins), np.nan)
    slope = np.full(len(bins), np.nan)
    for index, x in enumerate(bins):
        column = canon[np.abs(canon[:, 0] - x) < 0.025]
        if not len(column):
            continue
        top = column[np.argmin(column[:, 1])]
        top_y[index], top_z[index] = top[1], top[2]
        upper = column[column[:, 1] < top[1] + 0.2]
        if len(upper) >= 3 and np.ptp(upper[:, 1]) > 0.03:
            slope[index] = np.polyfit(upper[:, 1], upper[:, 2], 1)[0]
    found = ~np.isnan(top_y)
    slope = np.where(np.isnan(slope), np.nanmedian(slope) if np.isfinite(slope).any() else 0.5, slope)
    slope = np.clip(slope, 0.0, 1.5)
    for values in (top_y, top_z, slope):
        values[found] = cv2.GaussianBlur(values[found].reshape(1, -1), (0, 0), sigmaX=4, borderType=cv2.BORDER_REPLICATE).ravel()
    forehead_columns = np.flatnonzero(found & (top_y < -0.2))
    if not len(forehead_columns):
        return None
    columns = np.zeros(len(bins), bool)
    columns[forehead_columns[0]:forehead_columns[-1] + 1] = True
    columns &= found

    def profile(y, index):
        rise = y - top_y[index]
        return top_z[index] + slope[index] * rise - 0.8 * np.minimum(rise, 0) ** 2

    climb = np.arange(0, 0.32, step)
    hairline = np.full(len(bins), np.nan)
    for index in np.flatnonzero(columns):
        ys = top_y[index] - climb
        points = np.stack([np.full(len(ys), bins[index]), ys, profile(ys, index)], axis=1)
        hit = _hairline(reference, points)
        hairline[index] = ys[hit] if hit is not None else top_y[index] - 0.12
    hairline[columns] = cv2.GaussianBlur(hairline[columns].reshape(1, -1), (0, 0), sigmaX=6, borderType=cv2.BORDER_REPLICATE).ravel()

    picked = np.flatnonzero(columns)
    ys = np.arange(-axes[1], 0.2, step)
    grid_x = np.broadcast_to(bins[picked][None, :], (len(ys), len(picked)))
    grid_y = np.broadcast_to(ys[:, None], grid_x.shape)
    forehead = profile(grid_y, picked[None, :])
    line = hairline[picked][None, :]
    at_line = profile(np.broadcast_to(line, grid_x.shape), picked[None, :])
    rest = 1 - (grid_x / axes[0]) ** 2 - ((grid_y - SKULL_CENTER[1]) / axes[1]) ** 2
    skull_z = SKULL_CENTER[2] + axes[2] * np.sqrt(np.maximum(rest, 0))
    eased = skull_z + (at_line - skull_z) * np.exp(-np.maximum(line - grid_y, 0) / 0.08)
    grid_z = np.maximum(np.where(grid_y >= line, forehead, eased), skull_z)
    keep = (grid_y < top_y[picked][None, :] + 0.08) & (rest > 0.02)
    dz_dy, dz_dx = np.gradient(cv2.GaussianBlur(grid_z.astype(np.float32), (0, 0), 3), step, step)
    normal = np.stack([-dz_dx, -dz_dy, np.ones_like(grid_z)], axis=-1)[keep]
    normal /= np.linalg.norm(normal, axis=1, keepdims=True)
    pos = np.stack([grid_x[keep], grid_y[keep], grid_z[keep]], axis=1)
    color = _view_colors(views, reference, pos, normal, favour=4.0)
    t1, t2, n = _frame(np.cross(normal, [[1.0, 0.0, 0.0]]) + 1e-3, normal)
    cov = _covariance((t1, t2, n), np.tile([step * 1.2, step * 1.2, step * 0.3], (len(pos), 1)))
    return pos, cov, color, np.full(len(pos), 0.97)


def scan_face(views):
    """The slow, peluca-independent part: the 3D Mirror (beta) scanned head,
    Gaussians anchored to the face mesh of the most frontal capture and
    coloured by multi-view fusion and photometric optimization over every
    capture, placed on the reference mesh in the peluca's head frame."""
    scanned, _ = build_scanned_head([view.image for view in views], [view.mesh for view in views], holdout=False)
    reference = min(views, key=lambda view: abs(view.yaw))
    origin, width, M = head_frame(reference)
    pos, cov, _ = scanned.place(reference.mesh)
    return {
        "views": views,
        "reference": reference,
        "pos": (pos - origin) @ M.T / width,
        "cov": np.einsum("ij,njk,lk->nil", M, cov, M) / width ** 2,
        "color": scanned.color,
        "alpha": scanned.alpha,
    }


def face_splats(scan, axes=SKULL_AXES, head=9000, seed=11):
    """The person's own head in Gaussians around a skull of the given axes:
    the scanned face, the forehead up to the hairline, and the mannequin
    skull and neck painted in the person's skin tone. Returns (pos, cov,
    color, alpha) before the viewer transform."""
    rng = np.random.default_rng(seed)
    views, reference = scan["views"], scan["reference"]
    pos, cov, color, alpha = scan["pos"], scan["cov"], scan["color"], scan["alpha"]
    canon = canonical_mesh(reference)
    band = _forehead(views, reference, canon, axes)
    band = band if band is not None else tuple(np.zeros((0,) + shape) for shape in ((3,), (3, 3), (3,), ()))
    cheeks = pos[:, 2] > np.percentile(pos[:, 2], 60)
    skin = np.median(color[cheeks], axis=0)
    h_pos, h_cov, h_color, h_alpha = _mannequin(head, rng, axes)
    hull = cv2.convexHull(canon[:, :2].astype(np.float32)).reshape(-1, 2)
    keep = ~((h_pos[:, 2] > 0) & _inside(h_pos[:, :2], hull))
    h_color = skin[None, :] * (h_color[:, :1] / 0.80)
    parts = [(pos, cov, color, alpha), band, (h_pos[keep], h_cov[keep], h_color[keep], h_alpha[keep])]
    return tuple(np.concatenate([part[k] for part in parts]) for k in range(4))
