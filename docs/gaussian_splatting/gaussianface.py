# Gaussian Splatting del rostro (versión corta de lab/avatar.py)
# MediaPipe (478 puntos) -> malla -> gaussianos sobre los triángulos
# -> covarianza -> color de las fotos -> Adam -> render
import cv2
import numpy as np

from app.core.geometry.delaunay_fortune import delaunay_triangles   # Delaunay del proyecto

SIDE_A, SIDE_B = 234, 454      # landmarks a los lados de la cara


# 1. Los 478 puntos de MediaPipe, en píxeles (x*w, y*h, z*w)
def face_mesh(image, model_path="models/face_landmarker.task"):
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    options = vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=model_path), num_faces=1)
    detector = vision.FaceLandmarker.create_from_options(options)
    result = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                                      data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB)))
    if not result.face_landmarks:
        return None
    h, w = image.shape[:2]
    return np.array([[p.x * w, p.y * h, p.z * w] for p in result.face_landmarks[0]])


def face_width(mesh):
    return np.linalg.norm(mesh[SIDE_A] - mesh[SIDE_B])


# 2. Malla: triángulos con la normal hacia la cámara, y un marco por triángulo
def oriented_triangles(mesh):
    tris = np.array(delaunay_triangles(mesh[:, :2]))
    a, b, c = mesh[tris[:, 0]], mesh[tris[:, 1]], mesh[tris[:, 2]]
    flip = np.cross(b - a, c - a)[:, 2] > 0              # la cámara mira hacia -z
    tris[flip] = tris[flip][:, [0, 2, 1]]
    return tris


def triangle_frames(mesh, tris):
    a, b, c = mesh[tris[:, 0]], mesh[tris[:, 1]], mesh[tris[:, 2]]
    e1 = (b - a) / np.linalg.norm(b - a, axis=1, keepdims=True)
    n = np.cross(b - a, c - a)
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    return np.stack([e1, np.cross(n, e1), n], axis=2), n   # R = [e1 e2 n]


# 3. Gaussianos sobre la superficie, más en los triángulos grandes
def _surface(mesh, tris, budget, rng):
    a, b, c = mesh[tris[:, 0]], mesh[tris[:, 1]], mesh[tris[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    counts = np.maximum(1, np.round(budget * area / area.sum())).astype(int)
    tri = np.repeat(np.arange(len(tris)), counts)

    # punto al azar dentro del triángulo (si se sale, se refleja)
    u, v = rng.random(len(tri)), rng.random(len(tri))
    out = u + v > 1
    u[out], v[out] = 1 - u[out], 1 - v[out]
    bary = np.stack([1 - u - v, u, v], axis=1)

    # 4. forma: disco plano en el marco del triángulo (fino en la normal)
    spacing = np.sqrt(area[tri] / counts[tri]) / face_width(mesh)
    cov = np.zeros((len(tri), 3, 3))
    cov[:, 0, 0] = cov[:, 1, 1] = spacing ** 2
    cov[:, 2, 2] = (0.4 * spacing) ** 2
    return tri, bary, cov


# 4. Ubicar los gaussianos en una malla (cualquier vista o frame)
def place(mesh, tris, tri, bary, cov_local):
    R, normals = triangle_frames(mesh, tris)
    R = R[tri]
    s = face_width(mesh)
    pos = (bary[:, :, None] * mesh[tris[tri]]).sum(axis=1)
    cov = R @ cov_local @ R.transpose(0, 2, 1) * s ** 2    # Σ = R Σlocal Rᵀ
    return pos, cov, normals[tri][:, 2]                     # n_z: hacia dónde mira


# 7. Render: huella de cada gaussiano en 7x7 píxeles y mezcla normalizada
def _splat_weights(pos2, cov2, facing, shape, radius=3):
    h, w = shape
    inv = np.linalg.inv(cov2)
    off = np.arange(-radius, radius + 1)
    oy, ox = [g.ravel() for g in np.meshgrid(off, off, indexing="ij")]
    px = np.floor(pos2[:, :1]) + ox
    py = np.floor(pos2[:, 1:]) + oy
    dx, dy = px + 0.5 - pos2[:, :1], py + 0.5 - pos2[:, 1:]
    q = inv[:, :1, 0] * dx * dx + 2 * inv[:, :1, 1] * dx * dy + inv[:, 1:, 1] * dy * dy
    g = np.exp(-0.5 * q) * np.clip(-facing, 0, 1)[:, None] ** 2     # de espaldas no cuenta
    g *= (px >= 0) & (px < w) & (py >= 0) & (py < h)
    flat = (np.clip(py, 0, h - 1) * w + np.clip(px, 0, w - 1)).astype(int)
    return g, flat


def _render(color, g, flat, size):
    weight = np.bincount(flat.ravel(), g.ravel(), size)
    rgb = np.stack([np.bincount(flat.ravel(), (g * color[:, k:k + 1]).ravel(), size) for k in range(3)], 1)
    return rgb / np.maximum(weight, 1e-6)[:, None], weight


# Todo junto: varias fotos de la misma cara
def build_face(images, meshes, budget=40000, iterations=30, seed=5):
    rng = np.random.default_rng(seed)

    # la vista más de frente: la nariz (landmark 1) más centrada
    turn = [abs(m[1, 0] - (m[SIDE_A, 0] + m[SIDE_B, 0]) / 2) / face_width(m) for m in meshes]
    ref = int(np.argmin(turn))
    tris = oriented_triangles(meshes[ref])
    tri, bary, cov_local = _surface(meshes[ref], tris, budget, rng)

    # cada foto reducida a ~220 px de ancho de cara
    views = []
    for img, mesh in zip(images, meshes):
        k = 220.0 / face_width(mesh)
        small = cv2.resize(img, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
        pos, cov, facing = place(mesh, tris, tri, bary, cov_local)
        g, flat = _splat_weights(pos[:, :2] * k, cov[:, :2, :2] * k * k + np.eye(2) * 0.25,
                                 facing, small.shape[:2])
        hull = np.zeros(small.shape[:2], np.uint8)       # solo comparamos píxeles de la cara
        cv2.fillConvexPoly(hull, cv2.convexHull((mesh[:, :2] * k).astype(np.float32)).astype(np.int32), 1)
        views.append(dict(g=g, flat=flat, mask=hull.ravel() > 0, size=hull.size,
                          target=small[..., ::-1].reshape(-1, 3) / 255.0,
                          color=_sample_color(img, pos[:, :2]),
                          facing=np.clip(-facing, 0, 1) ** 2))

    # 5. color inicial: promedio de las fotos, pesando las que lo ven de frente
    num = sum(v["color"] * v["facing"][:, None] for v in views)
    den = sum(v["facing"] for v in views)[:, None]
    colors = num / np.maximum(den, 1e-6)

    # 6. Adam: ajustar colores para que el render se parezca a cada foto
    m, s = np.zeros_like(colors), np.zeros_like(colors)
    for t in range(1, iterations + 1):
        grad = np.zeros_like(colors)
        for v in views:
            img, weight = _render(colors, v["g"], v["flat"], v["size"])
            mask = v["mask"] & (weight > 1e-3)
            err = np.where(mask[:, None], img - v["target"], 0) / np.maximum(weight, 1e-6)[:, None]
            grad += (err[v["flat"]] * v["g"][..., None]).sum(axis=1) * 2 / max(mask.sum(), 1)
        m = 0.9 * m + 0.1 * grad
        s = 0.999 * s + 0.001 * grad ** 2
        colors -= 0.01 * (m / (1 - 0.9 ** t)) / (np.sqrt(s / (1 - 0.999 ** t)) + 1e-8)
        colors = np.clip(colors, 0, 1)

    pos, cov, _ = place(meshes[ref], tris, tri, bary, cov_local)
    return pos, cov, colors, np.full(len(pos), 0.97)


def _sample_color(image, xy):
    h, w = image.shape[:2]
    x = np.clip(xy[:, 0], 0, w - 1.001)
    y = np.clip(xy[:, 1], 0, h - 1.001)
    x0, y0 = x.astype(int), y.astype(int)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    img = image.astype(np.float32)
    top = img[y0, x0] * (1 - fx) + img[y0, x0 + 1] * fx
    bottom = img[y0 + 1, x0] * (1 - fx) + img[y0 + 1, x0 + 1] * fx
    return (top * (1 - fy) + bottom * fy)[:, ::-1] / 255.0


# El render final lo hace el navegador igual que con el cabello:
# ordenar por profundidad, proyectar Σ a 2D y mezclar con alpha * exp(-r²/2).
