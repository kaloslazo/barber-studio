import cv2
import numpy as np

from app.core.splatting.head3d import _covariance, _sample_color


FIT_RADIUS = 0.62
SKULL_CENTER = np.array([0.0, 0.0, -0.16])
SKULL_AXES = np.array([0.47, 0.82, 0.58])
NECK_CENTER_Z = -0.24
NECK_AXES = np.array([0.24, 0.27])
NECK_RANGE = (0.55, 1.2)


class HairView:
    def __init__(self, image_bgr, alpha, face_mask, geometry, yaw, tracked=True):
        self.image = image_bgr
        self.alpha = alpha.astype(np.float32)
        self.face_mask = face_mask
        self.geometry = geometry
        self.yaw = float(yaw)
        self.tracked = tracked


def _body_mask(view):
    body = np.where((view.alpha > 0.3) | (view.face_mask > 0), 255, 0).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(body, connectivity=8)
    if count <= 1:
        return body
    touching = np.unique(labels[(view.face_mask > 0) & (body > 0)])
    touching = touching[touching > 0]
    if len(touching) == 0:
        touching = [1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))]
    return np.where(np.isin(labels, touching), 255, 0).astype(np.uint8)


def _smooth_rows(values, valid, sigma):
    rows = np.arange(len(values))
    if valid.sum() < 2:
        return values
    filled = np.interp(rows, rows[valid], values[valid])
    return cv2.GaussianBlur(filled.reshape(-1, 1).astype(np.float32), (1, 0), sigma).ravel()


def _lathe(view, body, eye_y, scale):
    """Depth of the hair body seen from this view: every image row is an
    elliptic cross-section spanning the silhouette, round on the skull and
    flatter where long hair hangs below the chin."""
    h, w = body.shape
    filled = body > 0
    valid = filled.any(axis=1)
    left = np.where(valid, filled.argmax(axis=1), 0).astype(np.float32)
    right = np.where(valid, w - 1 - filled[:, ::-1].argmax(axis=1), 0).astype(np.float32)
    sigma = max(1.0, scale * 0.04)
    left, right = _smooth_rows(left, valid, sigma), _smooth_rows(right, valid, sigma)
    middle = (left + right) / 2
    radius = np.maximum((right - left) / 2 + 1, 1.0)
    level = (np.arange(h) - eye_y) / scale
    roundness = np.interp(level, [0.6, 1.15, 2.5], [1.0, 0.45, 0.3]).astype(np.float32)
    xs = np.arange(w, dtype=np.float32)[None, :]
    offset = xs - middle[:, None]
    inside = np.maximum(radius[:, None] ** 2 - offset ** 2, 0.0)
    root = np.sqrt(inside)
    depth = roundness[:, None] * root / scale
    slope_x = -roundness[:, None] * offset / np.maximum(root, 0.15 * radius[:, None])
    slope_y = np.gradient(depth, axis=0) * scale
    return depth.astype(np.float32), np.clip(slope_x, -4, 4), np.clip(slope_y, -4, 4)


def _strand_field(image_bgr, sigma):
    """Hair flow from the structure tensor: strands run perpendicular to the
    dominant gradient; flat areas fall back to gravity (straight down)."""
    gray = cv2.GaussianBlur(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 1.0)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    jxx = cv2.GaussianBlur(gx * gx, (0, 0), sigma)
    jyy = cv2.GaussianBlur(gy * gy, (0, 0), sigma)
    jxy = cv2.GaussianBlur(gx * gy, (0, 0), sigma)
    angle = 0.5 * np.arctan2(2 * jxy, jxx - jyy)
    coherence = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / (jxx + jyy + 1e-3)
    dx, dy = -np.sin(angle), np.cos(angle)
    flip = dy < 0
    dx[flip], dy[flip] = -dx[flip], -dy[flip]
    weight = np.clip(coherence, 0, 1)
    dx = weight * dx
    dy = weight * dy + (1 - weight)
    norm = np.sqrt(dx * dx + dy * dy) + 1e-6
    return dx / norm, dy / norm


def _to_canonical(vectors, yaw):
    """Camera frame of a view turned by `yaw` back to the head frame."""
    cos, sin = np.cos(yaw), np.sin(yaw)
    x, y, z = vectors[:, 0], vectors[:, 1], vectors[:, 2]
    return np.stack([x * cos - z * sin, y, x * sin + z * cos], axis=1)


def _frame(tangent, normal):
    normal = normal / (np.linalg.norm(normal, axis=1, keepdims=True) + 1e-9)
    tangent = tangent - (tangent * normal).sum(axis=1, keepdims=True) * normal
    tangent /= np.linalg.norm(tangent, axis=1, keepdims=True) + 1e-9
    binormal = np.cross(normal, tangent)
    return tangent, binormal, normal


def _view_samples(view, body, center_x, eye_y, scale, step, rng, back=False):
    h, w = body.shape
    depth, slope_x, slope_y = _lathe(view, body, eye_y, scale)
    ys, xs = np.mgrid[step / 2:h:step, step / 2:w:step]
    xs = (xs + rng.uniform(-0.5, 0.5, xs.shape) * step).ravel()
    ys = (ys + rng.uniform(-0.5, 0.5, ys.shape) * step).ravel()
    xi = np.clip(xs.astype(int), 0, w - 1)
    yi = np.clip(ys.astype(int), 0, h - 1)
    if back:
        hair_rows = (view.alpha > 0.4).any(axis=1)
        keep = (depth[yi, xi] > 0) & hair_rows[yi]
        texture = _back_texture(view, body, scale)
        alpha = np.full(keep.sum(), 0.92)
    else:
        keep = view.alpha[yi, xi] > 0.35
        texture = view.image
        alpha = np.clip(view.alpha[yi, xi][keep] * 1.05, 0, 0.95)
    xs, ys, xi, yi = xs[keep], ys[keep], xi[keep], yi[keep]
    if len(xs) == 0:
        return None
    side = -1.0 if back else 1.0
    pos = np.stack([(xs - center_x) / scale, (ys - eye_y) / scale, side * depth[yi, xi]], axis=1)
    normal = np.stack([-side * slope_x[yi, xi], -side * slope_y[yi, xi], np.full(len(xs), side)], axis=1)
    if back:
        dx, dy = np.zeros(len(xs)), np.ones(len(xs))
    else:
        flow_x, flow_y = _strand_field(view.image, max(2.0, scale * 0.03))
        dx, dy = flow_x[yi, xi], flow_y[yi, xi]
    tangent = np.stack([dx, dy, side * (slope_x[yi, xi] * dx + slope_y[yi, xi] * dy)], axis=1)
    color = _sample_color(texture, np.stack([xs, ys], axis=1))
    if back:
        color *= 0.78
    facing = np.abs(normal[:, 2]) / (np.linalg.norm(normal, axis=1) + 1e-9)
    if back:
        facing *= 0.05
    yaw = np.radians(view.yaw)
    return {
        "pos": _to_canonical(pos, yaw),
        "tangent": _to_canonical(tangent, yaw),
        "normal": _to_canonical(normal, yaw),
        "color": color,
        "alpha": alpha,
        "facing": facing,
        "stretch": np.clip(np.linalg.norm(normal, axis=1) / np.abs(normal[:, 2]), 1.0, 5.0),
    }


def _back_texture(view, body, scale):
    """The back of the head is never seen: it gets the colors of the nearest
    hair (normalized convolution over hair pixels only), so skin from the
    face never leaks into it, with vertical streaks to keep a hair texture."""
    hair = (view.alpha > 0.5).astype(np.float32)
    if hair.sum() < 50:
        return view.image
    sigma = max(3.0, scale * 0.12)
    weight = cv2.GaussianBlur(hair, (0, 0), sigma)
    spread = cv2.GaussianBlur(view.image.astype(np.float32) * hair[..., None], (0, 0), sigma)
    smooth = spread / np.maximum(weight[..., None], 1e-4)
    far = weight < 0.02
    if far.any():
        smooth[far] = np.median(view.image[hair > 0], axis=0)
    rng = np.random.default_rng(11)
    noise = rng.normal(0.0, 1.0, view.alpha.shape).astype(np.float32)
    streaks = cv2.GaussianBlur(noise, (0, 0), sigmaX=0.8, sigmaY=max(2.0, scale * 0.15))
    streaks = 1.0 + 0.12 * streaks / (streaks.std() + 1e-6)
    hole = hair < 1
    texture = view.image.astype(np.float32)
    texture[hole] = smooth[hole] * streaks[hole][:, None]
    return np.clip(texture, 0, 255).astype(np.uint8)


def _head_center_x(body, eye_y, scale, fallback):
    h, w = body.shape
    top, bottom = int(max(0, eye_y - 0.9 * scale)), int(min(h, eye_y))
    band = body[top:bottom] > 0
    rows = band.any(axis=1)
    if rows.sum() < 3:
        return fallback
    left = band[rows].argmax(axis=1)
    right = w - 1 - band[rows][:, ::-1].argmax(axis=1)
    return float(np.median((left + right) / 2))


def _row_extents(body, scale):
    filled = body > 0
    valid = filled.any(axis=1)
    w = body.shape[1]
    left = np.where(valid, filled.argmax(axis=1), 0).astype(np.float32)
    right = np.where(valid, w - 1 - filled[:, ::-1].argmax(axis=1), 0).astype(np.float32)
    sigma = max(1.0, scale * 0.02)
    return _smooth_rows(left, valid, sigma), _smooth_rows(right, valid, sigma), valid


def _skull_radius(level, directions, axes=SKULL_AXES):
    """Distance from the head axis to the mannequin skull along each
    horizontal direction, at height `level` (0 outside the skull)."""
    height = 1.0 - (level / axes[1]) ** 2
    if height <= 0:
        return np.zeros(len(directions))
    ax, az = axes[0] * np.sqrt(height), axes[2] * np.sqrt(height)
    c, s = directions[:, 0], directions[:, 1]
    oz = -SKULL_CENTER[2]
    a = (c / ax) ** 2 + (s / az) ** 2
    b = 2 * s * oz / az ** 2
    k = (oz / az) ** 2 - 1
    return (-b + np.sqrt(np.maximum(b * b - 4 * a * k, 0))) / (2 * a)


def _shape_prior(extent, placement, levels, directions, scale):
    """Cross-sections nobody captured (far sides, back) follow a head-like
    shape: as wide as the most frontal view, never in front of the face, and
    deep behind it, round on the skull and flatter where long hair hangs."""
    left, right, valid = extent
    center_x, eye_y, _ = placement
    image_rows = np.clip(np.round(eye_y + scale * levels).astype(int), 0, len(valid) - 1)
    lo = (left[image_rows] - center_x) / scale
    hi = (right[image_rows] - center_x) / scale
    middle = (lo + hi) / 2
    half = np.maximum((hi - lo) / 2, 0.05)
    depth = half * np.interp(levels, [0.6, 1.15, 2.5], [1.0, 0.55, 0.4])
    front = np.minimum(depth, np.interp(levels, [-0.6, 0.0, 0.8, 1.4], [0.35, 0.45, 0.4, 0.25]))
    c, s = directions[:, 0][None, :], directions[:, 1][None, :]
    m, a = middle[:, None], half[:, None]
    b = np.where(s > 0, front[:, None], depth[:, None])
    qa = (c / a) ** 2 + (s / b) ** 2
    qb = -2 * m * c / a ** 2
    qc = (m / a) ** 2 - 1
    return (-qb + np.sqrt(np.maximum(qb * qb - 4 * qa * qc, 0))) / (2 * qa) * 1.08


def _back_edge_colors(view, scale):
    """Hair color along the back edge of a profile capture, row by row: the
    last hair the camera saw before the back of the head turned away."""
    hair = view.alpha > 0.4
    h, w = hair.shape
    band = max(3, int(scale * 0.18))
    columns = np.arange(w)[None, :]
    if view.yaw < 0:
        edge = np.where(hair.any(axis=1), w - 1 - hair[:, ::-1].argmax(axis=1), -1)
        near = (columns <= edge[:, None]) & (columns > edge[:, None] - band)
    else:
        edge = np.where(hair.any(axis=1), hair.argmax(axis=1), -1)
        near = (columns >= edge[:, None]) & (columns < edge[:, None] + band)
    near &= hair & (edge[:, None] >= 0)
    weight = near.astype(np.float32)
    total = weight.sum(axis=1)
    colors = (view.image.astype(np.float32) * weight[..., None]).sum(axis=1)
    sigma = max(1.0, scale * 0.05)
    smooth_total = cv2.GaussianBlur(total.reshape(-1, 1), (1, 0), sigma).ravel()
    smooth_colors = cv2.GaussianBlur(colors.reshape(-1, 1, 3), (1, 0), sigma).reshape(-1, 3)
    valid = smooth_total > band * 0.15
    rgb = (smooth_colors / np.maximum(smooth_total, 1e-6)[:, None])[:, ::-1] / 255.0
    return rgb, valid


def _synthesize_back(pos, views, placements, scale, rng):
    """Back of the head, which no capture sees: at every height the color
    runs around the nape from the back edge of one profile to the other,
    with vertical strand streaks. Returns colors and which points have
    hair on at least one side at that height."""
    sides = {}
    for view, (_, eye_y, _) in zip(views, placements):
        if abs(view.yaw) < 50:
            continue
        key = "plus" if view.yaw < 0 else "minus"
        if key not in sides or abs(view.yaw) > abs(sides[key][0].yaw):
            sides[key] = (view, eye_y, _back_edge_colors(view, scale))
    if not sides:
        return None, None
    count = len(pos)
    radius = np.linalg.norm(pos[:, [0, 2]], axis=1) + 1e-6
    toward_plus = np.clip((1 + pos[:, 0] / radius) / 2, 0, 1)
    color = np.zeros((count, 3))
    weight = np.zeros(count)
    for key, (view, eye_y, (rgb, valid)) in sides.items():
        rows = np.clip(np.round(eye_y + scale * pos[:, 1]).astype(int), 0, len(valid) - 1)
        share = toward_plus if key == "plus" else 1 - toward_plus
        share = np.where(valid[rows], share + 1e-3, 0.0)
        color += rgb[rows] * share[:, None]
        weight += share
    found = weight > 0
    color[found] /= weight[found, None]
    angle = np.arctan2(pos[:, 2], pos[:, 0])
    noise = rng.normal(0.0, 1.0, (512, 360)).astype(np.float32)
    streaks = cv2.GaussianBlur(noise, (0, 0), sigmaX=1.0, sigmaY=12.0)
    streaks /= streaks.std() + 1e-6
    column = ((angle + np.pi) / (2 * np.pi) * 359).astype(int)
    row = np.clip(((pos[:, 1] + 2.0) / 5.0 * 511).astype(int), 0, 511)
    color *= (1.0 + 0.14 * streaks[row, column])[:, None] * 0.9
    return np.clip(color, 0, 1), found


def _hull_samples(views, bodies, placements, scale, budget, rng, axes=SKULL_AXES):
    """Multi-view peluca as one closed surface.

    At every height each capture says where the hair starts and ends seen
    from its angle; intersecting those strips gives the real cross-section
    (the visual hull, slice by slice). Each surface point is then textured
    from the captures that face it best, blended by how frontally they see
    it, so neighbouring angles join without seams. Points that the most
    frontal capture sees as face are left open for the mannequin's face."""
    yaws = np.radians([view.yaw for view in views])
    extents = [_row_extents(body, scale) for body in bodies]
    reference = int(np.argmin(np.abs(yaws)))
    ref_center, ref_eye, _ = placements[reference]
    ref_valid = extents[reference][2]
    rows = np.flatnonzero(ref_valid)
    levels = np.arange((rows.min() - ref_eye) / scale, (rows.max() - ref_eye) / scale, 0.01)
    phis = np.linspace(0, 2 * np.pi, 360, endpoint=False)
    directions = np.stack([np.cos(phis), np.sin(phis)], axis=1)
    bounds = []
    votes = np.zeros(len(levels))
    for (left, right, valid), (center_x, eye_y, _), yaw in zip(extents, placements, yaws):
        image_rows = np.round(eye_y + scale * levels).astype(int)
        inside = (image_rows >= 0) & (image_rows < len(valid))
        ok = np.zeros(len(levels), bool)
        ok[inside] = valid[image_rows[inside]]
        lo = (left[np.clip(image_rows, 0, len(valid) - 1)] - center_x) / scale
        hi = (right[np.clip(image_rows, 0, len(valid) - 1)] - center_x) / scale
        along = directions[:, 0] * np.cos(yaw) + directions[:, 1] * np.sin(yaw)
        with np.errstate(divide="ignore", invalid="ignore"):
            bound = np.where(along[None, :] > 1e-3, hi[:, None] / along[None, :],
                             np.where(along[None, :] < -1e-3, lo[:, None] / along[None, :], np.inf))
        bound[~ok] = np.inf
        bounds.append(bound)
        votes += ok
    bounds = np.sort(np.stack(bounds), axis=0)
    trim = max(1 if len(views) >= 4 else 0, int(round(0.1 * len(views))))
    radius = bounds[min(trim, len(views) - 1)]
    radius = np.minimum(radius, _shape_prior(extents[reference], placements[reference], levels, directions, scale))
    apex = levels[0]
    keep = votes >= max(1, int(np.ceil(len(views) / 2)))
    levels, radius = levels[keep], radius[keep]
    if len(levels) < 3:
        raise ValueError("The hair silhouettes do not overlap between captures")
    axes = _fit_skull(axes, -apex)
    radius = np.clip(np.where(np.isfinite(radius), radius, 0.02), 0.02, 3.0)
    wrapped = np.hstack([radius[:, -20:], radius, radius[:, :20]]).astype(np.float32)
    radius = cv2.GaussianBlur(wrapped, (0, 0), sigmaX=5, sigmaY=2)[:, 20:-20]
    for index, level in enumerate(levels):
        radius[index] = np.maximum(radius[index], _skull_radius(level, directions, axes) * 1.05)

    ring = radius[:, :, None] * directions[None, :, :]
    perimeter = np.linalg.norm(np.roll(ring, -1, axis=1) - ring, axis=2).sum(axis=1)
    spacing = float(np.sqrt(perimeter.sum() * 0.01 / budget))
    sample_levels = np.arange(levels[0], levels[-1], spacing) + rng.uniform(0, spacing)
    sample_levels = sample_levels[sample_levels < levels[-1]]
    points, normals = [], []
    slope = np.gradient(radius, levels, axis=0)
    for level in sample_levels:
        index = int(np.clip(np.searchsorted(levels, level), 0, len(levels) - 1))
        row = radius[index]
        loop = np.append(row, row[0])
        xy = loop[:, None] * np.vstack([directions, directions[:1]])
        arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))])
        targets = np.arange(rng.uniform(0, spacing), arc[-1], spacing)
        angle = np.interp(targets, arc, np.append(phis, 2 * np.pi))
        r = np.interp(angle, np.append(phis, 2 * np.pi), loop)
        dr = np.gradient(loop, np.append(phis, 2 * np.pi))
        dr_phi = np.interp(angle, np.append(phis, 2 * np.pi), dr)
        dr_level = np.interp(angle, np.append(phis, 2 * np.pi), np.append(slope[index], slope[index][0]))
        c, s = np.cos(angle), np.sin(angle)
        points.append(np.stack([r * c, np.full(len(r), level), r * s], axis=1))
        along_phi = np.stack([dr_phi * c - r * s, np.zeros(len(r)), dr_phi * s + r * c], axis=1)
        along_level = np.stack([dr_level * c, np.ones(len(r)), dr_level * s], axis=1)
        normal = np.cross(along_phi, along_level)
        normal *= np.sign((normal[:, 0] * c + normal[:, 2] * s))[:, None]
        normals.append(normal)
    pos = np.concatenate(points)
    normal = np.concatenate(normals)
    normal /= np.linalg.norm(normal, axis=1, keepdims=True) + 1e-9

    count = len(pos)
    weight_sum = np.zeros(count)
    color = np.zeros((count, 3))
    alpha = np.zeros(count)
    best = np.full(count, -1.0)
    best_hair = np.zeros(count)
    face_votes = np.zeros(count)
    skin_votes = np.zeros(count)
    hair_votes = np.zeros(count)
    tangent = np.tile([[0.0, 1.0, 0.0]], (count, 1))
    front_hair = np.zeros(count, bool)
    for index, (view, (center_x, eye_y, _), yaw) in enumerate(zip(views, placements, yaws)):
        h, w = view.alpha.shape
        facing = normal[:, 0] * -np.sin(yaw) + normal[:, 2] * np.cos(yaw)
        u = center_x + scale * (pos[:, 0] * np.cos(yaw) + pos[:, 2] * np.sin(yaw))
        v = eye_y + scale * pos[:, 1]
        seen = (facing > 0.15) & (u >= 0) & (u < w - 1) & (v >= 0) & (v < h - 1)
        ui, vi = u[seen].astype(int), v[seen].astype(int)
        hair = np.zeros(count, bool)
        hair[seen] = view.alpha[vi, ui] > 0.35
        better = seen & (facing > best)
        face = np.zeros(count, bool)
        face[seen] = view.face_mask[vi, ui] > 0
        best[better] = facing[better]
        frontal = seen & (facing > 0.45)
        face_votes += frontal & (face | (view.alpha[np.clip(v, 0, h - 1).astype(int), np.clip(u, 0, w - 1).astype(int)] < 0.1))
        skin_votes += frontal & face
        hair_votes += frontal & hair
        if index == reference:
            front_hair = hair & (facing > 0.6)
        best_hair = np.maximum(best_hair, np.where(hair, facing, 0.0))
        weight = np.where(hair, facing ** 6, 0.0)
        if not hair.any():
            continue
        flow_x, flow_y = _strand_field(view.image, max(2.0, scale * 0.03))
        sample = _sample_color(view.image, np.stack([u[hair], v[hair]], axis=1))
        color[hair] += sample * weight[hair, None]
        alpha[hair] += view.alpha[vi[hair[seen]], ui[hair[seen]]] * weight[hair]
        weight_sum += weight
        dominant = hair & better
        if dominant.any():
            dx = flow_x[v[dominant].astype(int), u[dominant].astype(int)]
            dy = flow_y[v[dominant].astype(int), u[dominant].astype(int)]
            tangent[dominant] = np.stack([dx * np.cos(yaw), dy, dx * np.sin(yaw)], axis=1)

    textured = weight_sum > 1e-6
    color[textured] /= weight_sum[textured, None]
    alpha[textured] /= weight_sum[textured]
    front = pos[:, 2] >= 0.0
    not_hair = np.where(front, (face_votes > 0) & (face_votes >= hair_votes), (skin_votes > 0) & (skin_votes >= hair_votes))
    not_hair &= ~front_hair
    keep = textured & ~not_hair
    behind = (pos[:, 2] < 0.2) & ~not_hair
    synthetic, found = _synthesize_back(pos, views, placements, scale, rng)
    ref = views[reference]
    hair_rows = (ref.alpha > 0.4).any(axis=1)
    v_ref = np.clip((ref_eye + scale * pos[:, 1]).astype(int), 0, ref.alpha.shape[0] - 1)
    if synthetic is not None:
        missing = behind & ~found & hair_rows[v_ref]
        if missing.any():
            texture = _back_texture(ref, bodies[reference], scale)
            u_ref = ref_center + scale * pos[missing, 0]
            synthetic[missing] = _sample_color(texture, np.stack([u_ref, ref_eye + scale * pos[missing, 1]], axis=1)) * 0.8
            found = found | missing
        trust = np.clip(best_hair / 0.35, 0, 1)
        fill = behind & found & (trust < 1)
        mix = trust[fill, None]
        color[fill] = np.where(textured[fill, None], color[fill] * mix + synthetic[fill] * (1 - mix), synthetic[fill])
        alpha[fill] = np.where(textured[fill], alpha[fill] * trust[fill] + 0.92 * (1 - trust[fill]), 0.92)
        tangent[fill & ~textured] = [0.0, 1.0, 0.0]
        keep |= fill
    else:
        back = (best < 0.15) & hair_rows[v_ref]
        if back.any():
            texture = _back_texture(ref, bodies[reference], scale)
            u_ref = ref_center + scale * pos[back, 0]
            color[back] = _sample_color(texture, np.stack([u_ref, ref_eye + scale * pos[back, 1]], axis=1)) * 0.8
            alpha[back] = 0.92
        keep |= back
    samples = {
        "pos": pos[keep],
        "tangent": tangent[keep],
        "normal": normal[keep],
        "color": color[keep],
        "alpha": np.clip(alpha[keep] * 1.05, 0, 0.95),
        "stretch": np.ones(int(keep.sum())),
    }
    crown = _crown(radius[0], levels[0], apex, samples, spacing, rng)
    if crown is not None:
        samples = {key: np.concatenate([samples[key], crown[key]]) for key in samples}
    return samples, spacing, axes


def _crown(ring, level, apex, samples, spacing, rng):
    """The hull is stacked rings, so its topmost ring is left open and the
    mannequin shows through. A round dome closes it, rising from that ring
    exactly up to `apex`, the top of the hair in the frontal capture, and
    coloured like the hair nearest to it."""
    near = samples["pos"][:, 1] < level + 0.06
    if near.sum() < 10:
        return None
    reach = float(ring.mean())
    count = int(np.pi * reach * reach / (spacing * spacing))
    t = np.sqrt(rng.uniform(0, 1, count))
    phi = rng.uniform(0, 2 * np.pi, count)
    r = t * np.interp(phi, np.linspace(0, 2 * np.pi, len(ring), endpoint=False), ring, period=2 * np.pi)
    height = max(level - apex, 0.0) * (1 - t * t)
    pos = np.stack([r * np.cos(phi), level - height, r * np.sin(phi)], axis=1)
    normal = np.stack([pos[:, 0], -np.full(count, reach), pos[:, 2]], axis=1)
    normal /= np.linalg.norm(normal, axis=1, keepdims=True)
    edge = samples["pos"][near]
    nearest = np.argmin(((pos[:, None, [0, 2]] - edge[None, :, [0, 2]]) ** 2).sum(axis=2), axis=1) if count * len(edge) < 4e7 else np.zeros(count, int)
    color = samples["color"][near][nearest] * 0.92
    tangent = np.stack([-pos[:, 0], np.zeros(count), -pos[:, 2]], axis=1) + 1e-3
    return {
        "pos": pos, "tangent": tangent, "normal": normal, "color": color,
        "alpha": np.full(count, 0.92), "stretch": np.ones(count),
    }


def _outside_skull(pos, axes=SKULL_AXES, margin=1.06):
    """Hair lies on top of the scalp and around the neck: anything that ended
    up inside the mannequin is pushed out radially to just above its surface."""
    local = (pos - SKULL_CENTER) / axes
    radius = np.linalg.norm(local, axis=1)
    inside = (radius < margin) & (radius > 1e-6) & (pos[:, 1] < 0.55)
    pos = pos.copy()
    pos[inside] = SKULL_CENTER + local[inside] / radius[inside, None] * margin * axes
    neck = np.stack([pos[:, 0], pos[:, 2] - NECK_CENTER_Z], axis=1) / NECK_AXES
    reach = np.linalg.norm(neck, axis=1)
    around = (pos[:, 1] >= NECK_RANGE[0]) & (pos[:, 1] <= NECK_RANGE[1] + 0.1) & (reach < margin) & (reach > 1e-6)
    pushed = neck[around] / reach[around, None] * margin * NECK_AXES
    pos[around, 0] = pushed[:, 0]
    pos[around, 2] = pushed[:, 1] + NECK_CENTER_Z
    return pos


def _clear_neck(pos):
    """Hair never crosses in front of the throat: the visual hull closes the
    strands that hang behind both shoulders with a front strip under the
    chin, which is dropped."""
    return ~((pos[:, 1] > 0.7) & (pos[:, 1] < 1.05) & (np.abs(pos[:, 0]) < NECK_AXES[0] * 0.85) & (pos[:, 2] > NECK_CENTER_Z))


def _crown_row(view):
    """Image row of the top of the hair, or None when the hair touches the
    top of the frame. The crown is the highest point of the head from every
    angle, so it lines up the captures vertically even when the head moved
    up or down between them or its eyes were not found in a profile."""
    rows = np.flatnonzero((view.alpha > 0.35).any(axis=1))
    if not len(rows) or rows.min() <= 1:
        return None
    return float(rows.min())


def _fit_skull(axes, top):
    """Mannequin skull sized to the scan: hair inside the skull is pushed out
    to 1.06x its surface, so the crown is kept low enough that even pushed
    hair never rises above `top`, the highest hair actually reconstructed."""
    axes = axes.copy()
    axes[1] = float(np.clip(top / 1.06 - 0.01, 0.5, axes[1]))
    return axes


def skull_axes(view, eye_y, scale):
    rows = np.flatnonzero((view.alpha > 0.35).any(axis=1))
    if not len(rows):
        return SKULL_AXES.copy()
    return _fit_skull(SKULL_AXES, (eye_y - rows.min()) / scale)


def _mannequin(count, rng, axes=SKULL_AXES):
    """Neutral head and neck so the peluca can be seen as worn."""
    head = int(count * 0.8)
    theta = np.arccos(rng.uniform(-1, 1, head))
    phi = rng.uniform(0, 2 * np.pi, head)
    unit = np.stack([np.sin(theta) * np.cos(phi), np.cos(theta), np.sin(theta) * np.sin(phi)], axis=1)
    head_pos = unit * axes + SKULL_CENTER
    head_normal = unit / axes
    neck = count - head
    angle = rng.uniform(0, 2 * np.pi, neck)
    height = rng.uniform(NECK_RANGE[0], NECK_RANGE[1], neck)
    neck_unit = np.stack([np.cos(angle), np.zeros(neck), np.sin(angle)], axis=1)
    neck_pos = neck_unit * np.array([NECK_AXES[0], 0.0, NECK_AXES[1]]) + np.stack([np.zeros(neck), height, np.full(neck, NECK_CENTER_Z)], axis=1)
    pos = np.concatenate([head_pos, neck_pos])
    normal = np.concatenate([head_normal, neck_unit])
    tangent = np.cross(normal, np.array([[0.0, 1.0, 0.0]]) + 1e-3)
    t1, t2, n = _frame(tangent, normal)
    spacing = np.sqrt(4 * np.pi * 0.6 * 0.6 / max(head, 1)) * 1.1
    scales = np.tile([spacing, spacing, spacing * 0.3], (len(pos), 1))
    light = np.clip(n @ np.array([0.35, -0.55, 0.75]) / np.linalg.norm([0.35, -0.55, 0.75]), 0, 1)
    color = np.array([[0.80, 0.76, 0.72]]) * (0.55 + 0.45 * light[:, None])
    return pos, _covariance((t1, t2, n), scales), color, np.full(len(pos), 0.98)


def build_hair_splats(views, budget=70000, mannequin=9000, seed=5, head=None):
    """3D Gaussian peluca from one or more hair captures.

    One photo is lifted onto a lathe surface built from its silhouette; several
    captures are fused into one visual-hull surface textured from the views
    that face it best. Splats are thin Gaussians stretched along the local
    strand flow. The unseen back of the head is closed with the hair texture
    of the most frontal capture. Returns float32 rows
    [x, y, z, cov(6), r, g, b, a] (hair first, then mannequin) in the same
    y-up, camera-facing frame as the 3D Mirror head. `head(axes)` replaces the
    mannequin with (pos, cov, color, alpha) in the same head frame, built
    around a skull of the given axes."""
    rng = np.random.default_rng(seed)
    reference = min(range(len(views)), key=lambda index: abs(views[index].yaw))
    ref = views[reference]
    scale = float(ref.geometry["face_w"])
    bodies = [_body_mask(view) for view in views]
    placements = []
    crown = _crown_row(ref)
    for view, body in zip(views, bodies):
        eye_y = float(view.geometry["center"][1]) if view.tracked else float(ref.geometry["center"][1])
        top = _crown_row(view)
        if crown is not None and top is not None:
            eye_y = top + (float(ref.geometry["center"][1]) - crown)
        center_x = _head_center_x(body, eye_y, scale, float(view.geometry["center"][0]))
        placements.append((center_x, eye_y, scale))

    axes = skull_axes(ref, placements[reference][1], scale)
    if len(views) > 1:
        samples, spacing, axes = _hull_samples(views, bodies, placements, scale, budget, rng, axes)
    else:
        step = max(1.0, np.sqrt(float((ref.alpha > 0.35).sum()) * 1.4 / budget))
        parts = [_view_samples(ref, bodies[0], placements[0][0], placements[0][1], scale, step, rng)]
        parts.append(_view_samples(ref, bodies[0], placements[0][0], placements[0][1], scale, step * 1.25, rng, back=True))
        parts = [part for part in parts if part is not None]
        if not parts:
            raise ValueError("No hair found in the captures")
        samples = {key: np.concatenate([part[key] for part in parts]) for key in parts[0]}
        spacing = step / scale

    samples["pos"] = _outside_skull(samples["pos"], axes)
    keep = _clear_neck(samples["pos"])
    samples = {key: value[keep] for key, value in samples.items()}
    t1, t2, n = _frame(samples["tangent"], samples["normal"])
    scales = np.tile([spacing * 2.0, spacing * 0.85, spacing * 0.25], (len(t1), 1))
    scales[:, :2] *= samples["stretch"][:, None]
    hair_cov = _covariance((t1, t2, n), scales)
    pos = [samples["pos"]]
    cov = [hair_cov]
    color = [samples["color"]]
    alpha = [samples["alpha"]]
    if head is not None or mannequin:
        m_pos, m_cov, m_color, m_alpha = head(axes) if head is not None else _mannequin(mannequin, rng, axes)
        pos.append(m_pos)
        cov.append(m_cov)
        color.append(m_color)
        alpha.append(m_alpha)
    pos, cov = np.concatenate(pos), np.concatenate(cov)
    color, alpha = np.concatenate(color), np.concatenate(alpha)

    hair_pos = samples["pos"]
    center = np.array([0.0, (hair_pos[:, 1].min() + hair_pos[:, 1].max()) / 2, 0.0])
    extent = np.abs(hair_pos - center).max(axis=0)
    A = np.diag([1.0, -1.0, 1.0]) * (FIT_RADIUS / max(extent[0], extent[1], 1.0))
    pos = (pos - center) @ A.T
    cov = np.einsum("ij,njk,lk->nil", A, cov, A)
    upper = np.stack([cov[:, 0, 0], cov[:, 0, 1], cov[:, 0, 2], cov[:, 1, 1], cov[:, 1, 2], cov[:, 2, 2]], axis=1)
    rows = np.concatenate([pos, upper, np.clip(color, 0, 1), alpha[:, None]], axis=1).astype(np.float32)
    return rows, {
        "count": int(len(rows)),
        "hair": int(len(hair_pos)),
        "mannequin": int(len(rows) - len(hair_pos)),
        "views": len(views),
    }
