import time

import cv2
import numpy as np


def _sigma_max(chol):
    l1, l2, l3 = chol[:, 0], chol[:, 1], chol[:, 2]
    a = l1 * l1
    b = l1 * l2
    c = l2 * l2 + l3 * l3
    half_trace = (a + c) / 2
    root = np.sqrt(np.maximum(half_trace ** 2 - (a * c - b * b), 0.0))
    smallest = np.maximum(half_trace - root, 1e-8)
    return 1.0 / np.sqrt(smallest)


RADIUS_LEVELS = np.array([1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128, 160])


def _buckets(chol, cap):
    radius = np.clip(np.ceil(2.5 * _sigma_max(chol)), 1, cap)
    levels = RADIUS_LEVELS[np.searchsorted(RADIUS_LEVELS, radius)]
    levels = np.minimum(levels, cap).astype(int)
    groups = []
    for r in np.unique(levels):
        idx = np.where(levels == r)[0]
        span = np.arange(-r, r + 1, dtype=np.float32)
        oy, ox = np.meshgrid(span, span, indexing="ij")
        groups.append((idx, ox.ravel(), oy.ravel()))
    return groups


def _patch(mu, chol, idx, ox, oy, h, w):
    m = mu[idx].astype(np.float32)
    cx = np.floor(m[:, 0])[:, None] + ox[None]
    cy = np.floor(m[:, 1])[:, None] + oy[None]
    inside = (cx >= 0) & (cx < w) & (cy >= 0) & (cy < h)
    dx = cx + 0.5 - m[:, 0][:, None]
    dy = cy + 0.5 - m[:, 1][:, None]
    k = chol[idx].astype(np.float32)
    l1 = k[:, 0][:, None]
    l2 = k[:, 1][:, None]
    l3 = k[:, 2][:, None]
    u = l1 * dx + l2 * dy
    v = l3 * dy
    g = np.exp(-0.5 * (u * u + v * v)) * inside
    flat = (np.clip(cy, 0, h - 1) * w + np.clip(cx, 0, w - 1)).astype(np.int64)
    return g, flat, dx, dy, u, v


def _render(mu, chol, color, h, w, groups):
    canvas = np.zeros((h * w, 3), np.float32)
    cache = []
    for idx, ox, oy in groups:
        g, flat, dx, dy, u, v = _patch(mu, chol, idx, ox, oy, h, w)
        for ch in range(3):
            canvas[:, ch] += np.bincount(
                flat.ravel(), weights=(g * color[idx, ch][:, None]).ravel(), minlength=h * w,
            )
        cache.append((idx, g, flat, dx, dy, u, v))
    return canvas, cache


class _Adam:
    def __init__(self, shape, lr, beta1=0.9, beta2=0.999):
        self.lr = lr
        self.b1, self.b2 = beta1, beta2
        self.m = np.zeros(shape)
        self.v = np.zeros(shape)
        self.t = 0

    def step(self, param, grad):
        self.t += 1
        self.m = self.b1 * self.m + (1 - self.b1) * grad
        self.v = self.b2 * self.v + (1 - self.b2) * grad * grad
        m_hat = self.m / (1 - self.b1 ** self.t)
        v_hat = self.v / (1 - self.b2 ** self.t)
        return param - self.lr * m_hat / (np.sqrt(v_hat) + 1e-8)


def _initial_params(target, count, rng):
    h, w = target.shape[:2]
    gray = cv2.cvtColor((target * 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
    detail = cv2.GaussianBlur(np.hypot(gx, gy), (0, 0), 2.0)
    weight = 0.35 + detail / (detail.max() + 1e-6)
    weight = (weight / weight.sum()).ravel()
    picks = rng.choice(h * w, size=count, replace=count > h * w, p=weight)
    ys, xs = np.divmod(picks, w)
    mu = np.stack([xs + rng.random(count), ys + rng.random(count)], axis=1)
    sigma = np.sqrt(h * w / count) * 0.6
    chol = np.tile([1.0 / sigma, 0.0, 1.0 / sigma], (count, 1))
    overlap = max(1.0, count * 2 * np.pi * sigma * sigma / (h * w))
    color = target[ys, xs] / overlap
    return mu, chol, color


def fit_gaussians(image_bgr, count, fit_size=160, iterations=None, seed=0):
    """Fit `count` 2D Gaussians to an image (GaussianImage-style, from scratch).

    Each Gaussian has a center mu, an inverse-covariance Cholesky factor
    (l1, l2, l3) so that Sigma^-1 = L L^T stays positive definite, and an RGB
    weight. The render is an accumulated sum, C(x) = sum_i c_i G_i(x), and all
    parameters are optimized with hand-written Adam on the mean squared error,
    using analytic gradients.
    """
    started = time.perf_counter()
    h0, w0 = image_bgr.shape[:2]
    scale = fit_size / max(h0, w0)
    h, w = max(8, int(round(h0 * scale))), max(8, int(round(w0 * scale)))
    target = cv2.resize(image_bgr, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    rng = np.random.default_rng(seed)
    mu, chol, color = _initial_params(target, count, rng)

    if iterations is None:
        iterations = int(np.clip(190 - 20 * np.log10(count), 110, 160))
    sigma0 = np.sqrt(h * w / count) * 0.6
    cap = int(min(max(h, w) / 2, 40))
    min_l = 3.0 / cap
    opt_mu = _Adam(mu.shape, lr=0.15 * max(0.5, sigma0 / 3))
    opt_chol = _Adam(chol.shape, lr=0.04 / sigma0)
    opt_color = _Adam(color.shape, lr=0.02)
    target_flat = target.reshape(-1, 3)
    norm = 2.0 / (h * w * 3)

    groups = _buckets(chol, cap)
    history = []
    for step in range(iterations):
        if step % 10 == 0:
            groups = _buckets(chol, cap)
        rendered, cache = _render(mu, chol, color, h, w, groups)
        error = rendered - target_flat
        if step % 20 == 0 or step == iterations - 1:
            history.append(float((error ** 2).mean()))
        grad_mu = np.zeros_like(mu)
        grad_chol = np.zeros_like(chol)
        grad_color = np.zeros_like(color)
        for idx, g, flat, dx, dy, u, v in cache:
            e = error[flat] * np.float32(norm)
            grad_color[idx] = np.einsum("npc,np->nc", e, g)
            dg = np.einsum("npc,nc->np", e, color[idx].astype(np.float32))
            t = dg * g * -0.5
            l1 = chol[idx, 0][:, None]
            l2 = chol[idx, 1][:, None]
            l3 = chol[idx, 2][:, None]
            grad_chol[idx, 0] = (t * 2 * u * dx).sum(axis=1)
            grad_chol[idx, 1] = (t * 2 * u * dy).sum(axis=1)
            grad_chol[idx, 2] = (t * 2 * v * dy).sum(axis=1)
            grad_mu[idx, 0] = (t * -2 * u * l1).sum(axis=1)
            grad_mu[idx, 1] = (t * (-2 * u * l2 - 2 * v * l3)).sum(axis=1)
        mu = opt_mu.step(mu, grad_mu)
        chol = opt_chol.step(chol, grad_chol)
        color = opt_color.step(color, grad_color)
        mu[:, 0] = np.clip(mu[:, 0], 0, w - 1e-3)
        mu[:, 1] = np.clip(mu[:, 1], 0, h - 1e-3)
        chol[:, 0] = np.maximum(chol[:, 0], min_l)
        chol[:, 2] = np.maximum(chol[:, 2], min_l)

    rendered, _ = _render(mu, chol, color, h, w, _buckets(chol, cap))
    mse = float(((rendered - target_flat) ** 2).mean())
    return {
        "mu": mu / np.array([w, h]),
        "chol": chol * max(h, w),
        "color": color,
        "aspect": (h0, w0),
        "psnr": float(10 * np.log10(1.0 / max(mse, 1e-10))),
        "seconds": time.perf_counter() - started,
        "iterations": iterations,
        "history": history,
    }


def _scaled(params, out_w, out_h):
    side = max(out_w, out_h)
    mu = params["mu"] * np.array([out_w, out_h])
    chol = params["chol"] / side
    return mu, chol


def render_gaussians(params, out_width):
    """Render the fitted Gaussians at any resolution (they are continuous)."""
    h0, w0 = params["aspect"]
    out_w = int(out_width)
    out_h = int(round(out_width * h0 / w0))
    mu, chol = _scaled(params, out_w, out_h)
    cap = int(min(max(out_h, out_w) / 2, 160))
    canvas, _ = _render(mu, chol, params["color"], out_h, out_w, _buckets(chol, cap))
    image = np.clip(canvas.reshape(out_h, out_w, 3) * 255.0, 0, 255)
    return image.astype(np.uint8)


def draw_ellipses(params, out_width):
    """Draw every Gaussian as its 1-sigma ellipse, filled with the color the
    render has at its center, so the image reads as a mosaic of splats."""
    h0, w0 = params["aspect"]
    out_w = int(out_width)
    out_h = int(round(out_width * h0 / w0))
    mu, chol = _scaled(params, out_w, out_h)
    shaded = render_gaussians(params, out_w)
    canvas = np.full((out_h, out_w, 3), 245, np.uint8)
    l1, l2, l3 = chol[:, 0], chol[:, 1], chol[:, 2]
    a, b, c = l1 * l1, l1 * l2, l2 * l2 + l3 * l3
    inv = np.stack([np.stack([a, b], -1), np.stack([b, c], -1)], -2)
    vals, vecs = np.linalg.eigh(np.linalg.inv(inv))
    cx = np.clip(mu[:, 0].astype(int), 0, out_w - 1)
    cy = np.clip(mu[:, 1].astype(int), 0, out_h - 1)
    fill = shaded[cy, cx]
    outline = (out_w / max(1, len(mu))) > 0.15
    for i in np.argsort(-vals[:, 1]):
        axes = (max(1, int(np.sqrt(vals[i, 1]))), max(1, int(np.sqrt(vals[i, 0]))))
        angle = float(np.degrees(np.arctan2(vecs[i, 1, 1], vecs[i, 0, 1])))
        center = (int(mu[i, 0]), int(mu[i, 1]))
        cv2.ellipse(canvas, center, axes, angle, 0, 360, tuple(int(x) for x in fill[i]), -1, cv2.LINE_AA)
        if outline:
            cv2.ellipse(canvas, center, axes, angle, 0, 360, (30, 30, 30), 1, cv2.LINE_AA)
    return canvas
