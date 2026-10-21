import cv2
import numpy as np

from app.core.compositing.beard import barycentric_locate
from app.core.geometry.delaunay_fortune import delaunay_triangles

FLOATS_PER_SPLAT = 13
OUTER_LIPS = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185]


def _sample_color(image_bgr, xy):
    h, w = image_bgr.shape[:2]
    x = np.clip(xy[:, 0], 0, w - 1.001)
    y = np.clip(xy[:, 1], 0, h - 1.001)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    img = image_bgr.astype(np.float32)
    top = img[y0, x0] * (1 - fx) + img[y0, x0 + 1] * fx
    bottom = img[y0 + 1, x0] * (1 - fx) + img[y0 + 1, x0 + 1] * fx
    return (top * (1 - fy) + bottom * fy)[:, ::-1] / 255.0


def _frames_from_normals(normals):
    """Orthonormal frame (t1, t2, n) per splat, built from its normal."""
    n = normals / (np.linalg.norm(normals, axis=1, keepdims=True) + 1e-9)
    helper = np.where(np.abs(n[:, :1]) < 0.9, [[1.0, 0.0, 0.0]], [[0.0, 1.0, 0.0]])
    t1 = np.cross(n, helper)
    t1 /= np.linalg.norm(t1, axis=1, keepdims=True) + 1e-9
    t2 = np.cross(n, t1)
    return t1, t2, n


def _covariance(axes, scales):
    """Sigma = R S^2 R^T with R = [axes] (columns) and S = diag(scales)."""
    R = np.stack(axes, axis=2)
    S2 = scales ** 2
    return np.einsum("nij,nj,nkj->nik", R, S2, R)


def _surface_splats(mesh, triangles, image_bgr, budget, rng):
    a, b, c = (mesh[triangles[:, k]] for k in range(3))
    area3d = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    counts = np.maximum(1, np.round(budget * area3d / area3d.sum())).astype(int)
    tri = np.repeat(np.arange(len(triangles)), counts)
    starts = np.repeat(np.cumsum(counts) - counts, counts)
    rank = np.arange(len(tri)) - starts
    side = np.ceil(np.sqrt(counts[tri])).astype(int)
    u = (rank % side + rng.random(len(tri))) / side
    v = (rank // side + rng.random(len(tri))) / np.ceil(counts[tri] / side)
    v = np.clip(v, 0, 1)
    flip = u + v > 1
    u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
    pos = a[tri] + (b[tri] - a[tri]) * u[:, None] + (c[tri] - a[tri]) * v[:, None]
    normal = np.cross(b - a, c - a)
    normal[normal[:, 2] > 0] *= -1
    t1, t2, n = _frames_from_normals(normal[tri])
    spacing = np.sqrt(np.maximum(area3d[tri] / counts[tri], 0.5))
    scales = np.stack([spacing * 1.0, spacing * 1.0, spacing * 0.4], axis=1)
    cov = _covariance((t1, t2, n), scales)
    color = _sample_color(image_bgr, pos[:, :2])
    alpha = np.full(len(pos), 0.97)
    return pos, cov, color, alpha


def _backdrop_splats(image_bgr, mesh, hull_idx, z_back, face_w, step):
    """The rest of the photo as a relief: depth comes forward from z_back to
    the depth of the nearest face-outline vertex, so hair, ears and neck bulge
    towards the face instead of floating on a flat card. Near the face (hair,
    ears, neck) the grid is fine; far background and the fallback layer behind
    the face use a 3x coarser grid with bigger splats."""
    h, w = image_bgr.shape[:2]
    outline = mesh[hull_idx]
    hull = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(hull, cv2.convexHull(outline[:, :2].astype(np.float32)).astype(np.int32), 255)
    parts = []
    for grid, keep_near in ((step, True), (step * 3, False)):
        ys, xs = np.mgrid[grid // 2:h:grid, grid // 2:w:grid]
        xs, ys = xs.ravel().astype(np.float32), ys.ravel().astype(np.float32)
        d2 = (xs[:, None] - outline[None, :, 0]) ** 2 + (ys[:, None] - outline[None, :, 1]) ** 2
        nearest = d2.argmin(axis=1)
        dist = np.sqrt(d2[np.arange(len(xs)), nearest])
        inside = hull[ys.astype(int), xs.astype(int)] > 0
        near = (dist < 0.9 * face_w) & ~inside
        pick = near if keep_near else ~near
        xs, ys, dist, nearest, inside = xs[pick], ys[pick], dist[pick], nearest[pick], inside[pick]
        z = z_back + (outline[nearest, 2] - z_back) * np.exp(-dist / (0.4 * face_w))
        z = np.where(inside, z_back, z)
        parts.append((np.stack([xs, ys, z], axis=1), grid))
    pos = np.concatenate([p for p, _ in parts])
    sizes = np.concatenate([np.full(len(p), g, np.float64) for p, g in parts])
    normal = np.tile([[0.0, 0.0, -1.0]], (len(pos), 1))
    t1, t2, n = _frames_from_normals(normal)
    scales = np.stack([sizes * 0.8, sizes * 0.8, sizes * 0.1], axis=1)
    cov = _covariance((t1, t2, n), scales)
    color = _sample_color(image_bgr, pos[:, :2])
    alpha = np.full(len(pos), 0.97)
    return pos, cov, color, alpha


def _beard_splats(mesh, triangles, region, face_w, tint, style, rng, texture=None):
    lips = np.zeros(region.shape, np.uint8)
    cv2.fillPoly(lips, [mesh[OUTER_LIPS, :2].astype(np.int32)], 255)
    grow = max(3, int(face_w * 0.05))
    lips = cv2.dilate(lips, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * grow + 1, 2 * grow + 1)))
    region = cv2.subtract(region, lips)
    ys, xs = np.where(region > 0)
    if len(xs) == 0:
        return None
    count = min(len(xs) // 4, 6000 if style != "stubble" else 6000)
    pick = rng.choice(len(xs), size=count, replace=False)
    roots2d = np.stack([xs[pick], ys[pick]], axis=1).astype(np.float32)
    tri, bary, valid = barycentric_locate(roots2d, mesh[:, :2], triangles)
    tri, bary = tri[valid], bary[valid]
    corners = mesh[triangles[tri]]
    roots = (bary[:, :, None] * corners).sum(axis=1)
    a, b, c = corners[:, 0], corners[:, 1], corners[:, 2]
    normal = np.cross(b - a, c - a)
    normal[normal[:, 2] > 0] *= -1
    normal /= np.linalg.norm(normal, axis=1, keepdims=True) + 1e-9
    sideways = np.sign(roots[:, :1] - mesh[0:1, 0]) * np.array([[1.0, 0.0, 0.0]])
    direction = 0.55 * normal + np.array([0.0, 1.0, 0.0]) + rng.normal(0, 0.18, normal.shape)
    lip_top = float(mesh[OUTER_LIPS, 1].min())
    lip_bottom = float(mesh[OUTER_LIPS, 1].max())
    above = roots[:, 1] < lip_top + 0.25 * (lip_bottom - lip_top)
    direction[above] = direction[above] * 0.5 + sideways[above] * 0.9
    direction /= np.linalg.norm(direction, axis=1, keepdims=True)
    if style == "stubble":
        length = face_w * rng.uniform(0.006, 0.014, len(roots))
        segments = 1
    else:
        length = face_w * rng.uniform(0.02, 0.05, len(roots))
        length[above] *= 0.45
        segments = 3
    pos, cov, color, alpha = [], [], [], []
    tone = rng.uniform(0.7, 1.0, (len(roots), 1))
    base = _sample_color(texture, roots[:, :2]) * 0.92 if texture is not None else np.asarray(tint)[None, :]
    for k in range(segments):
        t = (k + 0.5) / segments
        center = roots + direction * (length * t)[:, None] + normal * face_w * 0.004
        helper_axis = np.cross(direction, normal)
        helper_axis /= np.linalg.norm(helper_axis, axis=1, keepdims=True) + 1e-9
        third = np.cross(direction, helper_axis)
        width = face_w * (0.0022 if style != "stubble" else 0.002)
        scales = np.stack([length / segments * 0.6, np.full(len(roots), width), np.full(len(roots), width)], axis=1)
        pos.append(center)
        cov.append(_covariance((direction, helper_axis, third), scales))
        color.append(np.clip(base * tone, 0, 1))
        alpha.append(np.full(len(roots), 0.55 - 0.25 * t))
    return np.concatenate(pos), np.concatenate(cov), np.concatenate(color), np.concatenate(alpha)


def build_head_splats(image_bgr, mesh, beard_region=None, beard_style=None, tint=(0.16, 0.13, 0.11), budget=None, seed=3):
    """3D Gaussian head from a single photo + the MediaPipe 3D face mesh.

    Face: Gaussians sampled on the Delaunay-triangulated mesh surface, flat
    discs tangent to each triangle, colored from the photo. Backdrop: the rest
    of the photo as a relief whose depth falls off from the face edge. Beard:
    3D strands made of elongated Gaussians grown along the surface normal and
    gravity. Returns float32 rows [x, y, z, cov(6), r, g, b, a] in a
    normalized, y-up, camera-facing frame.
    """
    rng = np.random.default_rng(seed)
    mesh = np.asarray(mesh, np.float64)
    triangles = np.asarray(delaunay_triangles(mesh[:, :2]))
    face_w = float(mesh[:, 0].max() - mesh[:, 0].min())
    hull_idx = cv2.convexHull(mesh[:, :2].astype(np.float32), returnPoints=False).ravel()
    z_back = float(mesh[:, 2].max() + 0.35 * face_w)

    if budget is None:
        hull_area = cv2.contourArea(mesh[hull_idx, :2].astype(np.float32))
        budget = int(np.clip(hull_area / 1.6, 30000, 90000))
    parts = [_surface_splats(mesh, triangles, image_bgr, budget, rng)]
    step = max(2, int(round(image_bgr.shape[1] / 320)))
    parts.append(_backdrop_splats(image_bgr, mesh, hull_idx, z_back, face_w, step))
    if beard_region is not None and beard_style:
        beard = _beard_splats(mesh, triangles, beard_region, face_w, tint, beard_style, rng, texture=image_bgr)
        if beard is not None:
            parts.append(beard)

    pos = np.concatenate([p[0] for p in parts])
    cov = np.concatenate([p[1] for p in parts])
    color = np.concatenate([p[2] for p in parts])
    alpha = np.concatenate([p[3] for p in parts])

    center = np.array([mesh[:, 0].mean(), mesh[:, 1].mean(), mesh[:, 2].mean()])
    A = np.diag([1.0, -1.0, -1.0]) / face_w
    pos = (pos - center) @ A.T
    cov = np.einsum("ij,njk,lk->nil", A, cov, A)
    upper = np.stack([cov[:, 0, 0], cov[:, 0, 1], cov[:, 0, 2], cov[:, 1, 1], cov[:, 1, 2], cov[:, 2, 2]], axis=1)
    rows = np.concatenate([pos, upper, color, alpha[:, None]], axis=1).astype(np.float32)
    return rows, {
        "count": int(len(rows)),
        "face": int(len(parts[0][0])),
        "backdrop": int(len(parts[1][0])),
        "beard": int(len(rows) - len(parts[0][0]) - len(parts[1][0])),
    }


SH_C0 = 0.28209479177387814


def _rotation_to_quaternion(R):
    """Batch 3x3 rotation matrices -> unit quaternions (w, x, y, z)."""
    trace = R[:, 0, 0] + R[:, 1, 1] + R[:, 2, 2]
    q = np.zeros((len(R), 4))
    w = np.sqrt(np.maximum(0.0, 1.0 + trace)) / 2
    x = np.sqrt(np.maximum(0.0, 1.0 + R[:, 0, 0] - R[:, 1, 1] - R[:, 2, 2])) / 2
    y = np.sqrt(np.maximum(0.0, 1.0 - R[:, 0, 0] + R[:, 1, 1] - R[:, 2, 2])) / 2
    z = np.sqrt(np.maximum(0.0, 1.0 - R[:, 0, 0] - R[:, 1, 1] + R[:, 2, 2])) / 2
    x = np.copysign(x, R[:, 2, 1] - R[:, 1, 2])
    y = np.copysign(y, R[:, 0, 2] - R[:, 2, 0])
    z = np.copysign(z, R[:, 1, 0] - R[:, 0, 1])
    q[:, 0], q[:, 1], q[:, 2], q[:, 3] = w, x, y, z
    return q / (np.linalg.norm(q, axis=1, keepdims=True) + 1e-12)


def to_ply(rows):
    """Standard 3D Gaussian Splatting .ply (as read by the reference viewer,
    SuperSplat and friends): log-scales and a rotation quaternion from the
    eigen-decomposition of each covariance, degree-0 spherical harmonics
    for color and logit opacity."""
    a, b, c, d, e, f = (rows[:, k].astype(np.float64) for k in range(3, 9))
    cov = np.stack([np.stack([a, b, c], -1), np.stack([b, d, e], -1), np.stack([c, e, f], -1)], -2)
    values, vectors = np.linalg.eigh(cov)
    flip = np.linalg.det(vectors) < 0
    vectors[flip, :, 0] *= -1
    quats = _rotation_to_quaternion(vectors)
    scales = np.log(np.sqrt(np.maximum(values, 1e-12)))
    sh = (rows[:, 9:12].astype(np.float64) - 0.5) / SH_C0
    alpha = np.clip(rows[:, 12].astype(np.float64), 1e-4, 1 - 1e-4)
    opacity = np.log(alpha / (1 - alpha))
    data = np.concatenate([
        rows[:, 0:3].astype(np.float64), np.zeros((len(rows), 3)), sh, opacity[:, None], scales, quats,
    ], axis=1).astype("<f4")
    names = ["x", "y", "z", "nx", "ny", "nz", "f_dc_0", "f_dc_1", "f_dc_2", "opacity",
             "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"]
    header = "ply\nformat binary_little_endian 1.0\n" + f"element vertex {len(rows)}\n"
    header += "".join(f"property float {name}\n" for name in names) + "end_header\n"
    return header.encode("ascii") + data.tobytes()
