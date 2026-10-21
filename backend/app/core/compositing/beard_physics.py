import cv2
import numpy as np

from app.core.compositing.beard import _direction_maps, barycentric_locate, barycentric_map

NODES = 4
SUBSTEPS = 4
NODE_STIFFNESS = np.array([0.0, 0.34, 0.22, 0.13], np.float32)
COLOR_LEVELS = np.array([0.55, 0.68, 0.80, 0.92, 1.04])
DEBRIS_LIFE = 1.4


def _chaikin(curves):
    """One Chaikin corner-cutting pass: a cheap quadratic B-spline smoothing
    that turns the 4-node chain into a soft curve (keeps both endpoints)."""
    q = 0.75 * curves[:, :-1] + 0.25 * curves[:, 1:]
    r = 0.25 * curves[:, :-1] + 0.75 * curves[:, 1:]
    middle = np.stack([q, r], axis=2).reshape(len(curves), -1, 2)
    return np.concatenate([curves[:, :1], middle, curves[:, -1:]], axis=1)


def splat_strands(curves, widths, alphas, colors, shape, radius=6):
    """Render polyline strands as chains of anisotropic 2D Gaussians (P1).

    Every segment becomes one Gaussian elongated along the segment
    (sigma_along = half its length, sigma_across = the hair width). Density
    A = sum o_i G_i and color = sum o_i G_i c_i / A are accumulated with
    bincount; coverage is 1 - exp(-A), so overlapping hairs saturate smoothly
    instead of needing a depth sort.
    """
    h, w = shape
    if len(curves) == 0:
        return np.zeros((h, w, 3), np.float32), np.zeros((h, w), np.float32)
    a, b = curves[:, :-1], curves[:, 1:]
    center = ((a + b) / 2).reshape(-1, 2)
    seg = (b - a).reshape(-1, 2)
    length = np.linalg.norm(seg, axis=1) + 1e-6
    ux, uy = seg[:, 0] / length, seg[:, 1] / length
    s_along = np.maximum(length / 2.0, 0.6)
    s_across = np.repeat(widths, curves.shape[1] - 1)
    opacity = np.asarray(alphas, np.float64).ravel()
    col = np.repeat(colors, curves.shape[1] - 1, axis=0)
    span = np.arange(-radius, radius + 1, dtype=np.float32)
    oy, ox = np.meshgrid(span, span, indexing="ij")
    ox, oy = ox.ravel(), oy.ravel()
    px = np.floor(center[:, 0])[:, None] + ox[None]
    py = np.floor(center[:, 1])[:, None] + oy[None]
    dx = px + 0.5 - center[:, 0][:, None]
    dy = py + 0.5 - center[:, 1][:, None]
    u = (dx * ux[:, None] + dy * uy[:, None]) / s_along[:, None]
    v = (-dx * uy[:, None] + dy * ux[:, None]) / s_across[:, None]
    g = np.exp(-0.5 * (u * u + v * v)) * opacity[:, None]
    g = g * ((px >= 0) & (px < w) & (py >= 0) & (py < h))
    flat = (np.clip(py, 0, h - 1) * w + np.clip(px, 0, w - 1)).astype(np.int64).ravel()
    weights = g.ravel()
    density = np.bincount(flat, weights=weights, minlength=h * w)
    rgb = np.stack(
        [np.bincount(flat, weights=(g * col[:, ch][:, None]).ravel(), minlength=h * w) for ch in range(3)],
        axis=1,
    )
    alpha = 1.0 - np.exp(-density)
    color = rgb / np.maximum(density, 1e-6)[:, None]
    return color.reshape(h, w, 3).astype(np.float32), alpha.reshape(h, w).astype(np.float32)


def _segment_distance(points, a, b):
    """Distance from each point to the segment a-b (the clipper's swept path)."""
    ab = b - a
    denom = float(ab @ ab)
    if denom < 1e-6:
        return np.linalg.norm(points - a, axis=-1)
    t = np.clip(((points - a) @ ab) / denom, 0.0, 1.0)
    closest = a + t[..., None] * ab
    return np.linalg.norm(points - closest, axis=-1)


class BeardPhysics:
    """Long beard strands simulated as tiny chains of particles.

    Each strand has NODES particles. The root is glued to the skin with
    barycentric coordinates in the live Delaunay mesh; the other nodes follow
    with Verlet integration (inertia + gravity), a spring towards the rest pose
    (the strand grown along the hair direction and rotated with the head) and
    distance constraints that keep the segment lengths. When the head turns
    fast, the tips lag behind and swing back. Strands can be cut: they turn
    into falling debris that fades out.
    """

    def __init__(self, anchor, region, pts, face_w, seed=11, length_scale=1.0):
        h, w = region.shape
        rng = np.random.default_rng(seed)
        ys, xs = np.where(region > 0)
        count = int(min(max(len(xs) * 0.035, 1), 2600))
        chosen = rng.choice(len(xs), size=count, replace=False)
        roots = np.stack([xs[chosen], ys[chosen]], axis=1).astype(np.float32)
        anchor.ensure_mesh()
        self.roots_ref = roots
        self.tri, self.bary, self.valid = barycentric_locate(roots, anchor.ref_ext, anchor.triangles)
        dx, dy, _ = _direction_maps(np.asarray(pts, np.float32), h, w)
        direction = np.stack([dx[ys[chosen], xs[chosen]], dy[ys[chosen], xs[chosen]]], axis=1)
        direction = direction * np.array([0.55, 1.0], np.float32) + np.array([0.0, 0.9], np.float32)
        upper_lip = roots[:, 1] < float(pts[62, 1])
        side = np.sign(roots[:, 0] - float(pts[33, 0]))
        direction[upper_lip] = np.stack([side[upper_lip] * 1.0, np.full(int(upper_lip.sum()), 0.35)], axis=1)
        direction /= np.linalg.norm(direction, axis=1, keepdims=True) + 1e-6
        self.direction = direction.astype(np.float32)
        mouth_y = float(pts[48:60, 1].mean())
        chin_y = float(pts[8, 1])
        depth = np.clip((roots[:, 1] - mouth_y) / max(chin_y - mouth_y, 1.0), 0.0, 1.0)
        self.length = (
            face_w * length_scale * rng.uniform(0.10, 0.20, count) * (0.35 + 0.65 * depth)
        ).astype(np.float32)
        self.length[upper_lip] *= 0.5
        self.curl = rng.uniform(-0.35, 0.35, count).astype(np.float32)
        self.tone = rng.integers(0, len(COLOR_LEVELS), count)
        self.thick = np.where(rng.random(count) < 0.15, 2, 1)
        self.alive = np.ones(count, bool)
        self.face_w = float(face_w)
        self.length_scale = float(length_scale)
        self.pos = None
        self.prev = None
        self.root_prev = None
        self.last_dt = 0.1
        self.debris_pos = np.zeros((0, NODES, 2), np.float32)
        self.debris_vel = np.zeros((0, 2), np.float32)
        self.debris_age = np.zeros(0, np.float32)
        self.debris_tone = np.zeros(0, int)

    def _rest_offsets(self, linear):
        seg = (self.length / (NODES - 1))[:, None, None]
        k = np.arange(NODES, dtype=np.float32)[None, :, None]
        side = np.stack([-self.direction[:, 1], self.direction[:, 0]], axis=1)
        bend = (k / (NODES - 1)) ** 2 * self.curl[:, None, None] * self.length[:, None, None]
        local = k * seg * self.direction[:, None, :] + bend * side[:, None, :]
        return local @ linear.T

    def roots(self, anchor):
        return barycentric_map(
            self.roots_ref, self.tri, self.bary, self.valid,
            anchor.triangles, anchor.cur_ext, anchor.M,
        )

    def step(self, anchor, dt):
        roots = self.roots(anchor)
        linear = anchor.M[:, :2].astype(np.float32)
        scale = float(np.sqrt(abs(np.linalg.det(linear))))
        offsets = self._rest_offsets(linear)
        rest_len = (self.length / (NODES - 1) * scale)[:, None]
        if self.pos is None:
            self.pos = roots[:, None, :] + offsets
            self.prev = self.pos.copy()
            self.root_prev = roots
            return
        dt = float(np.clip(dt, 0.02, 0.25))
        self.last_dt = dt
        h = dt / SUBSTEPS
        gravity = np.array([0.0, 2.2 * self.face_w], np.float32)
        stiffness = NODE_STIFFNESS[None, :, None]
        for s in range(1, SUBSTEPS + 1):
            root = self.root_prev + (roots - self.root_prev) * (s / SUBSTEPS)
            rest = root[:, None, :] + offsets
            velocity = (self.pos - self.prev) * 0.86
            self.prev = self.pos.copy()
            self.pos = self.pos + velocity + gravity * h * h
            self.pos += stiffness * (rest - self.pos)
            self.pos[:, 0] = root
            for _ in range(2):
                for k in range(1, NODES):
                    seg = self.pos[:, k] - self.pos[:, k - 1]
                    dist = np.linalg.norm(seg, axis=1, keepdims=True) + 1e-6
                    self.pos[:, k] = self.pos[:, k - 1] + seg / dist * rest_len
        self.root_prev = roots
        self._step_debris(dt)

    def _step_debris(self, dt):
        if len(self.debris_age) == 0:
            return
        self.debris_vel[:, 1] += 3.5 * self.face_w * dt
        self.debris_pos += self.debris_vel[:, None, :] * dt
        self.debris_age += dt
        keep = self.debris_age < DEBRIS_LIFE
        self.debris_pos = self.debris_pos[keep]
        self.debris_vel = self.debris_vel[keep]
        self.debris_age = self.debris_age[keep]
        self.debris_tone = self.debris_tone[keep]

    def cut(self, start, end, radius):
        """Cut every live strand whose root section (skin level) is touched by
        the clipper moving from start to end. Tips hanging over the path are
        not cut, like a real clipper shaving close to the skin."""
        if self.pos is None:
            return np.zeros(0, int)
        start = np.asarray(start, np.float32)
        end = np.asarray(end, np.float32)
        dist = _segment_distance(self.pos[:, :2], start, end).min(axis=1)
        hit = np.where(self.alive & (dist < radius))[0]
        if len(hit) == 0:
            return hit
        self.alive[hit] = False
        rng = np.random.default_rng(len(self.debris_age) + int(hit.sum()))
        velocity = (self.pos[hit, -1] - self.prev[hit, -1]) / max(self.last_dt, 1e-3)
        velocity = velocity * 0.3 + rng.normal(0, 0.25 * self.face_w, (len(hit), 2))
        velocity[:, 1] -= 0.4 * self.face_w
        self.debris_pos = np.concatenate([self.debris_pos, self.pos[hit].copy()])
        self.debris_vel = np.concatenate([self.debris_vel, velocity.astype(np.float32)])
        self.debris_age = np.concatenate([self.debris_age, np.zeros(len(hit), np.float32)])
        self.debris_tone = np.concatenate([self.debris_tone, self.tone[hit]])
        return hit

    def tip_lag(self, anchor):
        """Mean distance between simulated tips and the rest pose tips (px)."""
        if self.pos is None:
            return 0.0
        linear = anchor.M[:, :2].astype(np.float32)
        rest_tip = self.pos[:, 0] + self._rest_offsets(linear)[:, -1]
        return float(np.linalg.norm(self.pos[:, -1] - rest_tip, axis=1).mean())

    def shadow(self, shape, density, alive_only=True):
        """Soft beard shadow built from the live roots only, so shaved areas
        lose their shadow too."""
        h, w = shape
        mask = np.zeros((h, w), np.float32)
        if self.pos is None:
            return mask
        count = int(len(self.pos) * float(np.clip(density, 0.0, 1.0)))
        roots = self.pos[:count, 0][self.alive[:count]] if alive_only else self.pos[:count, 0]
        xs = np.clip(roots[:, 0].astype(int), 0, w - 1)
        ys = np.clip(roots[:, 1].astype(int), 0, h - 1)
        np.add.at(mask, (ys, xs), 1.0)
        sigma = max(2.0, self.face_w / 38.0)
        mask = cv2.GaussianBlur(mask, (0, 0), sigma)
        level = 0.035 * 0.6
        return np.clip(mask / max(level, 1e-6), 0.0, 1.0)

    def render(self, shape, tint, density, include_live=True):
        """Live strands plus fading debris, rendered as Gaussian chains."""
        h, w = shape
        if self.pos is None:
            return np.zeros((h, w, 3), np.float32), np.zeros((h, w), np.float32)
        tint = np.asarray(tint, np.float32)
        count = int(len(self.pos) * float(np.clip(density, 0.0, 1.0))) if include_live else 0
        live = np.where(self.alive[:count])[0]
        nodes = [self.pos[live]]
        tones = [self.tone[live]]
        thick = [self.thick[live]]
        fades = [np.ones(len(live))]
        if len(self.debris_age):
            nodes.append(self.debris_pos)
            tones.append(self.debris_tone)
            thick.append(np.ones(len(self.debris_age), int))
            fades.append(np.clip(1.0 - self.debris_age / DEBRIS_LIFE, 0.1, 1.0))
        nodes = np.concatenate(nodes)
        if len(nodes) == 0:
            return np.zeros((h, w, 3), np.float32), np.zeros((h, w), np.float32)
        curves = _chaikin(nodes)
        segments = curves.shape[1] - 1
        taper = 0.8 * (1.0 - 0.6 * np.arange(segments) / max(segments - 1, 1))
        alphas = np.concatenate(fades)[:, None] * taper[None, :]
        widths = np.where(np.concatenate(thick) == 2, 0.75, 0.5)
        colors = np.clip(tint[None, :] * COLOR_LEVELS[np.concatenate(tones)][:, None], 0, 255)
        return splat_strands(curves, widths, alphas, colors, (h, w))
