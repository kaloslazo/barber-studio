import numpy as np

FOVY = np.radians(35)
KEY = np.array([0.45, 0.65, 0.75]) / np.linalg.norm([0.45, 0.65, 0.75])
FILL = np.array([-0.6, 0.15, -0.5]) / np.linalg.norm([-0.6, 0.15, -0.5])


def orbit(yaw, pitch, distance):
    cy, sy, cp, sp = np.cos(yaw), np.sin(yaw), np.cos(pitch), np.sin(pitch)
    r = np.array([[cy, 0, -sy], [sy * sp, cp, cy * sp], [sy * cp, -sp, cy * cp]])
    return r, np.array([0.0, 0.0, -distance])


def unpack(rows):
    pos = rows[:, :3].astype(np.float64)
    c = rows[:, 3:9].astype(np.float64)
    cov = np.stack([c[:, [0, 1, 2]], c[:, [1, 3, 4]], c[:, [2, 4, 5]]], axis=1)
    return pos, cov, rows[:, 9:12].astype(np.float64), rows[:, 12].astype(np.float64)


def smooth_normals(pos, normal, cell=0.04, passes=2):
    lo = pos.min(axis=0)
    g = (pos - lo) / cell + 1
    shape = (np.floor((pos.max(axis=0) - lo) / cell) + 4).astype(int)
    grid = np.zeros(tuple(shape) + (3,))
    base = np.floor(g).astype(int)
    frac = g - base
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = np.where(dx, frac[:, 0], 1 - frac[:, 0]) * np.where(dy, frac[:, 1], 1 - frac[:, 1]) * np.where(dz, frac[:, 2], 1 - frac[:, 2])
                np.add.at(grid, (base[:, 0] + dx, base[:, 1] + dy, base[:, 2] + dz), normal * w[:, None])
    for _ in range(passes):
        for axis in range(3):
            grid = (np.roll(grid, 1, axis) + 2 * grid + np.roll(grid, -1, axis)) / 4
    out = np.zeros_like(normal)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = np.where(dx, frac[:, 0], 1 - frac[:, 0]) * np.where(dy, frac[:, 1], 1 - frac[:, 1]) * np.where(dz, frac[:, 2], 1 - frac[:, 2])
                out += grid[base[:, 0] + dx, base[:, 1] + dy, base[:, 2] + dz] * w[:, None]
    length = np.linalg.norm(out, axis=1, keepdims=True)
    return np.where(length > 1e-4, out / np.maximum(length, 1e-9), normal)


def lit_colors(pos, cov, color, eye):
    vals, vecs = np.linalg.eigh(cov)
    normal = vecs[:, :, 0]
    tangent = vecs[:, :, 2]
    center = pos.mean(axis=0)
    flip = ((pos - center) * normal).sum(axis=1) < 0
    normal[flip] *= -1
    normal = smooth_normals(pos, normal)
    key = np.clip(((normal @ KEY) + 0.35) / 1.35, 0, 1)
    fill = np.clip(((normal @ FILL) + 0.35) / 1.35, 0, 1)
    to_eye = eye[None, :] - pos
    to_eye /= np.linalg.norm(to_eye, axis=1, keepdims=True)
    tl = tangent @ KEY
    te = (tangent * to_eye).sum(axis=1)
    kk = np.maximum(tl * te + np.sqrt(np.maximum(1 - tl * tl, 0)) * np.sqrt(np.maximum(1 - te * te, 0)), 0)
    spec = kk ** 110 * np.clip(key / 0.3, 0, 1)
    return color * (0.38 + 0.78 * key + 0.22 * fill)[:, None] + 0.10 * spec[:, None]


def render(rows, yaw=0.0, pitch=0.1, distance=2.1, size=480, lit=True, background=(0.98, 0.98, 0.973), chunk=700):
    pos, cov, color, alpha = unpack(rows)
    R, t = orbit(yaw, pitch, distance)
    cam = pos @ R.T + t
    eye = -R.T @ t
    if lit:
        color = lit_colors(pos, cov, color, eye)
    color = np.clip(color, 0, 1)
    focal = size / (2 * np.tan(FOVY / 2))
    z = cam[:, 2]
    keep = z < -0.05
    cam, cov, color, alpha = cam[keep], cov[keep], color[keep], alpha[keep]
    z = cam[:, 2]
    u = size / 2 + focal * cam[:, 0] / -z
    v = size / 2 - focal * cam[:, 1] / -z
    J = np.zeros((len(z), 2, 3))
    J[:, 0, 0] = focal / -z
    J[:, 1, 1] = -focal / -z
    J[:, 0, 2] = focal * cam[:, 0] / (z * z)
    J[:, 1, 2] = -focal * cam[:, 1] / (z * z)
    T = J @ R
    c2 = np.einsum("nij,njk,nlk->nil", T, cov, T)
    c2[:, 0, 0] += 0.3
    c2[:, 1, 1] += 0.3
    det = c2[:, 0, 0] * c2[:, 1, 1] - c2[:, 0, 1] ** 2
    inv = np.stack([c2[:, 1, 1] / det, -c2[:, 0, 1] / det, c2[:, 0, 0] / det], axis=1)
    mid = 0.5 * (c2[:, 0, 0] + c2[:, 1, 1])
    lam = mid + np.sqrt(np.maximum(mid ** 2 - det, 0))
    radius = np.clip(np.ceil(3 * np.sqrt(lam)), 1, 60).astype(int)
    order = np.argsort(z)
    image = np.tile(np.array(background, np.float64), (size * size, 1))
    for start in range(0, len(order), chunk):
        idx = order[start:start + chunk]
        sum_a = np.zeros(size * size)
        sum_ac = np.zeros((size * size, 3))
        log_t = np.zeros(size * size)
        for r in np.unique(radius[idx]):
            sel = idx[radius[idx] == r]
            span = np.arange(-r, r + 1)
            oy, ox = np.meshgrid(span, span, indexing="ij")
            px = np.round(u[sel])[:, None] + ox.ravel()[None]
            py = np.round(v[sel])[:, None] + oy.ravel()[None]
            dx = px - u[sel][:, None]
            dy = py - v[sel][:, None]
            q = inv[sel, 0][:, None] * dx * dx + 2 * inv[sel, 1][:, None] * dx * dy + inv[sel, 2][:, None] * dy * dy
            a = np.minimum(0.99, alpha[sel][:, None] * np.exp(-0.5 * q))
            depth_w = np.exp((z[sel] - z[idx].max()) / 0.004)[:, None] * np.ones_like(a)
            ok = (q <= 9) & (a > 0.004) & (px >= 0) & (px < size) & (py >= 0) & (py < size)
            flat = (py * size + px).astype(np.int64)[ok]
            a = a[ok]
            wa = a * depth_w[ok]
            col = np.repeat(color[sel][:, None, :], ok.shape[1], axis=1)[ok]
            sum_a += np.bincount(flat, weights=wa, minlength=size * size)
            log_t += np.bincount(flat, weights=np.log1p(-a), minlength=size * size)
            for ch in range(3):
                sum_ac[:, ch] += np.bincount(flat, weights=wa * col[:, ch], minlength=size * size)
        A = 1 - np.exp(log_t)
        C = sum_ac / np.maximum(sum_a, 1e-9)[:, None]
        image = image * (1 - A[:, None]) + C * A[:, None]
    return (np.clip(image.reshape(size, size, 3), 0, 1)[..., ::-1] * 255).astype(np.uint8)
