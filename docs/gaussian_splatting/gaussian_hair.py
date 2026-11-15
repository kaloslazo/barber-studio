# Gaussian Splatting del cabello 
# siluetas -> visual hull -> puntos en la superficie -> dirección de hebras
# -> covarianza -> color/opacidad -> filas para el visor
import cv2
import numpy as np


class HairView:
    def __init__(self, image, alpha, yaw, center_x, eye_y):
        self.image = image                       # foto BGR
        self.alpha = alpha.astype(np.float32)    # 0..1, cuánto cabello hay en cada píxel
        self.yaw = yaw   # giro de la cabeza en grados
        self.center_x = center_x  # centro de la cabeza en la imagen
        self.eye_y = eye_y   # altura de los ojos en la imagen


# 1. Silueta: dónde empieza y termina el cabello en cada fila
def _row_extents(mask):
    valid = mask.any(axis=1)
    w = mask.shape[1]
    left = np.where(valid, mask.argmax(axis=1), 0).astype(np.float32)
    right = np.where(valid, w - 1 - mask[:, ::-1].argmax(axis=1), 0).astype(np.float32)
    return left, right, valid


# 2-3. Visual hull + puntos sobre superficie
def _hull_samples(views, scale, budget, rng):
    yaws = np.radians([v.yaw for v in views])
    extents = [_row_extents(v.alpha > 0.3) for v in views]
    ref = int(np.argmin(np.abs(yaws)))           # la vista más de frente

    # cortes horizontales cada 0.01 (en anchos de cara) y 360 direcciones
    rows = np.flatnonzero(extents[ref][2])
    eye = views[ref].eye_y
    levels = np.arange((rows.min() - eye) / scale, (rows.max() - eye) / scale, 0.01)
    phis = np.linspace(0, 2 * np.pi, 360, endpoint=False)
    dirs = np.stack([np.cos(phis), np.sin(phis)], axis=1)

    # cada cámara recorta el radio: el punto tiene que caer dentro de su silueta
    radius = np.full((len(levels), 360), np.inf)
    for v, (left, right, valid), yaw in zip(views, extents, yaws):
        r = np.clip(np.round(v.eye_y + scale * levels).astype(int), 0, len(valid) - 1)
        lo = (left[r] - v.center_x) / scale
        hi = (right[r] - v.center_x) / scale
        along = dirs[:, 0] * np.cos(yaw) + dirs[:, 1] * np.sin(yaw)   # eje x de esa cámara
        with np.errstate(divide="ignore"):
            bound = np.where(along > 1e-3, hi[:, None] / along,
                             np.where(along < -1e-3, lo[:, None] / along, np.inf))
        bound[~valid[r]] = np.inf
        radius = np.minimum(radius, bound)
    radius = np.clip(np.where(np.isfinite(radius), radius, 0.02), 0.02, 3.0)

    # separación entre puntos según el presupuesto
    perimeter = (radius * 2 * np.pi / 360).sum(axis=1)
    spacing = np.sqrt(perimeter.sum() * 0.01 / budget)
    d_level = np.gradient(radius, levels, axis=0)
    d_phi = np.gradient(radius, phis, axis=1)

    pos, normal = [], []
    for i in range(0, len(levels), max(1, round(spacing / 0.01))):
        k = max(3, int(perimeter[i] / spacing))
        j = (np.arange(k) * 360 // k + rng.integers(0, 360 // k + 1)) % 360
        r, c, s = radius[i, j], np.cos(phis[j]), np.sin(phis[j])
        pos.append(np.stack([r * c, np.full(k, levels[i]), r * s], axis=1))
        # normal = cruz de la tangente alrededor y la tangente hacia abajo
        around = np.stack([d_phi[i, j] * c - r * s, np.zeros(k), d_phi[i, j] * s + r * c], axis=1)
        down = np.stack([d_level[i, j] * c, np.ones(k), d_level[i, j] * s], axis=1)
        n = np.cross(around, down)
        n *= np.sign(n[:, 0] * c + n[:, 2] * s)[:, None]      # hacia afuera
        normal.append(n)
    pos = np.concatenate(pos)
    normal = np.concatenate(normal)
    normal /= np.linalg.norm(normal, axis=1, keepdims=True) + 1e-9
    return pos, normal, spacing


# 4. Dirección de las hebras con el structure tensor
def _strand_field(image, sigma):
    gray = cv2.GaussianBlur(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 1.0)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    jxx = cv2.GaussianBlur(gx * gx, (0, 0), sigma)
    jyy = cv2.GaussianBlur(gy * gy, (0, 0), sigma)
    jxy = cv2.GaussianBlur(gx * gy, (0, 0), sigma)

    angle = 0.5 * np.arctan2(2 * jxy, jxx - jyy)          # dirección del gradiente
    coherence = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / (jxx + jyy + 1e-3)
    dx, dy = -np.sin(angle), np.cos(angle)                # la hebra va perpendicular
    flip = dy < 0
    dx[flip], dy[flip] = -dx[flip], -dy[flip]             # siempre hacia abajo

    # si no hay una dirección clara, el pelo cae por gravedad
    w = np.clip(coherence, 0, 1)
    dx, dy = w * dx, w * dy + (1 - w)
    norm = np.sqrt(dx * dx + dy * dy) + 1e-6
    return dx / norm, dy / norm


# 5. Forma y orientación: Σ = R S² Rᵀ
def _frame(tangent, normal):
    tangent = tangent - (tangent * normal).sum(axis=1, keepdims=True) * normal   # pegarla a la superficie
    tangent /= np.linalg.norm(tangent, axis=1, keepdims=True) + 1e-9
    return tangent, np.cross(normal, tangent), normal


def _covariance(axes, scales):
    R = np.stack(axes, axis=2)                            # ejes como columnas
    return np.einsum("nij,nj,nkj->nik", R, scales ** 2, R)


# 6. Color y opacidad: cada cámara aporta según qué tan de frente ve el punto
def _sample_color(image, xy):
    h, w = image.shape[:2]
    x = np.clip(xy[:, 0], 0, w - 1.001)
    y = np.clip(xy[:, 1], 0, h - 1.001)
    x0, y0 = x.astype(int), y.astype(int)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    img = image.astype(np.float32)
    top = img[y0, x0] * (1 - fx) + img[y0, x0 + 1] * fx
    bottom = img[y0 + 1, x0] * (1 - fx) + img[y0 + 1, x0 + 1] * fx
    return (top * (1 - fy) + bottom * fy)[:, ::-1] / 255.0   # BGR -> RGB


def _paint(views, pos, normal, scale):
    n = len(pos)
    color, alpha, total = np.zeros((n, 3)), np.zeros(n), np.zeros(n)
    tangent = np.tile([0.0, 1.0, 0.0], (n, 1))
    best = np.full(n, -1.0)
    for v in views:
        yaw = np.radians(v.yaw)
        h, w = v.alpha.shape
        facing = normal[:, 0] * -np.sin(yaw) + normal[:, 2] * np.cos(yaw)
        u = v.center_x + scale * (pos[:, 0] * np.cos(yaw) + pos[:, 2] * np.sin(yaw))
        vv = v.eye_y + scale * pos[:, 1]
        seen = (facing > 0.15) & (u >= 0) & (u < w - 1) & (vv >= 0) & (vv < h - 1)
        a = np.zeros(n)
        a[seen] = v.alpha[vv[seen].astype(int), u[seen].astype(int)]
        hair = seen & (a > 0.35)
        if not hair.any():
            continue

        weight = np.where(hair, facing ** 6, 0.0)          # las vistas frontales mandan
        color[hair] += _sample_color(v.image, np.stack([u[hair], vv[hair]], 1)) * weight[hair, None]
        alpha += a * weight
        total += weight

        # la hebra la pone la cámara que mejor ve el punto
        dx, dy = _strand_field(v.image, max(2.0, scale * 0.03))
        top = hair & (facing > best)
        best[top] = facing[top]
        px, py = u[top].astype(int), vv[top].astype(int)
        tangent[top] = np.stack([dx[py, px] * np.cos(yaw), dy[py, px], dx[py, px] * np.sin(yaw)], 1)

    ok = total > 1e-6
    color[ok] /= total[ok, None]
    alpha[ok] = np.clip(alpha[ok] / total[ok] * 1.05, 0, 0.95)
    return color, alpha, tangent, ok


# 7. Todo junto -> filas [x y z | Σxx Σxy Σxz Σyy Σyz Σzz | r g b | a]
def build_hair_splats(views, scale, budget=70000, seed=5):
    rng = np.random.default_rng(seed)
    pos, normal, spacing = _hull_samples(views, scale, budget, rng)
    color, alpha, tangent, ok = _paint(views, pos, normal, scale)
    pos, normal, tangent, color, alpha = pos[ok], normal[ok], tangent[ok], color[ok], alpha[ok]

    # gaussianos largos a lo largo de la hebra, finos hacia afuera
    t1, t2, n = _frame(tangent, normal)
    scales = np.tile([spacing * 2.0, spacing * 0.85, spacing * 0.25], (len(pos), 1))
    cov = _covariance((t1, t2, n), scales)

    # centrar y voltear y (en la imagen y crece hacia abajo)
    center = np.array([0.0, (pos[:, 1].min() + pos[:, 1].max()) / 2, 0.0])
    extent = np.abs(pos - center).max(axis=0)
    A = np.diag([1.0, -1.0, 1.0]) * (0.62 / max(extent[0], extent[1], 1.0))
    pos = (pos - center) @ A.T
    cov = A @ cov @ A.T

    upper = cov[:, [0, 0, 0, 1, 1, 2], [0, 1, 2, 1, 2, 2]]
    return np.concatenate([pos, upper, color, alpha[:, None]], axis=1).astype(np.float32)


# info de como se ve en frontend (frontend/js/splat3d.js):
#  - se ordenan de atrás hacia adelante
#  - cada Σ se proyecta a pantalla: Σ2D = J W Σ Wᵀ Jᵀ
#  - cada píxel recibe alpha = a * exp(-r²/2) y se mezcla encima de lo anterior
