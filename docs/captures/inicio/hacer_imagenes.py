"""Imágenes del inicio hechas con la app, sobre retratos de la NASA (dominio público).

Desde backend/:  venv/bin/python ../docs/captures/inicio/hacer_imagenes.py
Las vistas 3D (Espejo y Peluca) se dibujan con render_splats.py, un rasterizador
de gaussianas en CPU, a partir de las mismas gaussianas que devuelve la API.
"""
import base64
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "frontend/assets/inicio"
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(HERE))
from fastapi.testclient import TestClient

from app.core.faces.mesh import FaceMeshes
from app.core.faces.session import FaceStudio
from app.main import app
from render_splats import render

client = TestClient(app)
HOROWITZ = (ROOT / "frontend/assets/samples/ejemplo.jpg").read_bytes()
RUBIO = (ROOT / "frontend/assets/samples/muestra.jpg").read_bytes()
CARD = (237 / 255, 237 / 255, 235 / 255)
meshes = FaceMeshes()


def decode(data):
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)


def from_url(url):
    return decode(base64.b64decode(url.split(",", 1)[1]))


def portrait(image, reference=None, side=640):
    h, w = image.shape[:2]
    faces = meshes.detect(reference if reference is not None else image, 1)
    if faces:
        points = faces[0]
        cx = float(points[:, 0].mean())
        top, bottom = float(points[:, 1].min()), float(points[:, 1].max())
        span = (bottom - top) * 2.05
        cy = top + (bottom - top) * 0.32
    else:
        cx, cy, span = w / 2, h / 2, min(h, w)
    span = min(span, h, w)
    x0 = int(np.clip(cx - span / 2, 0, w - span))
    y0 = int(np.clip(cy - span / 2, 0, h - span))
    crop = image[y0:y0 + int(span), x0:x0 + int(span)]
    return cv2.resize(crop, (side, side), interpolation=cv2.INTER_AREA)


def square(image, side=640):
    h, w = image.shape[:2]
    s = min(h, w)
    crop = image[(h - s) // 2:(h - s) // 2 + s, (w - s) // 2:(w - s) // 2 + s]
    return cv2.resize(crop, (side, side), interpolation=cv2.INTER_AREA if s > side else cv2.INTER_CUBIC)


def save(name, image):
    OUT.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT / f"{name}.jpg"), image, [cv2.IMWRITE_JPEG_QUALITY, 84, cv2.IMWRITE_JPEG_PROGRESSIVE, 1])
    print(name, image.shape)


def post(path, data, photo=HOROWITZ, files=None):
    files = files or {"image": ("a.jpg", photo, "image/jpeg")}
    response = client.post(path, files=files, data=data)
    if response.status_code != 200:
        raise SystemExit(f"{path} {data}: {response.status_code} {response.text[:120]}")
    return response


def splats(response):
    rows = np.frombuffer(response.content, np.float32).reshape(-1, 13).copy()
    solid = rows[rows[:, 12] > 0.5, :3]
    return rows, solid


base = decode(HOROWITZ)
rubio = decode(RUBIO)

save("tinte-original", portrait(base))
for name, color in [("rubio", "#d9b04a"), ("rojo", "#b3312c"), ("azul", "#2f4fb8"), ("morado", "#7a3ba8"), ("rosado", "#d95fa6")]:
    result = decode(post("/api/dye", {"color": color, "strength": "0.85"}).content)
    save(f"tinte-{name}", portrait(result, base))

for style in ["crew", "buzz"]:
    result = decode(post("/api/haircut", {"style": style, "strength": "0.9"}).content)
    save(f"corte-{style}", portrait(result, base))

for item in post("/api/gallery", {"key": ""}).json()["results"]:
    if item["key"] not in ("marx", "einstein", "vangogh", "lincoln"):
        continue
    picture = from_url(item["image"])
    h, w = picture.shape[:2]
    scale = 760 / max(h, w)
    save(f"galeria-{item['key']}", cv2.resize(picture, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA))

for preset in ["eyes", "big-head", "alien"]:
    result = decode(post("/api/faces/photo", {"mode": "caricature", "preset": preset, "amount": "0.9"}).content)
    save(f"caricatura-{preset}", portrait(result, base))

studio = FaceStudio()
swap_a, _ = studio.apply(base, "swap", other=rubio)
swap_b, _ = studio.apply(rubio, "swap", other=base)
save("cambio-horowitz", portrait(base))
save("cambio-rubio", portrait(rubio))
save("cambio-a", portrait(swap_a, base))
save("cambio-b", portrait(swap_b, rubio))

frames = studio.fusion(base, rubio, 9)
save("fusion", cv2.resize(frames[len(frames) // 2], (640, 640), interpolation=cv2.INTER_AREA))

looks = [
    ("practicante-1", {"beard": "full", "color": "#d95fa6", "cut": "buzz"}),
    ("practicante-2", {"beard": "mustache", "color": "#3d8b3d", "cut": "undercut"}),
    ("practicante-3", {"beard": "goatee", "color": "#d9b04a", "cut": "crew"}),
]
for name, look in looks:
    save(name, portrait(decode(post("/api/look", look).content), base))

result = post("/api/gaussians", {"count": "600"}, photo=RUBIO).json()
save("gaussianas", square(from_url(result["ellipses"])))
save("gaussianas-render", square(from_url(result["render"])))
save("contrarreloj", square(cv2.imread(str(ROOT / "report/diagramas/img/j_medio.jpg")), 420))

rows, solid = splats(post("/api/head3d", {"beard": "full"}, photo=RUBIO))
rows[:, :3] -= np.median(solid, axis=0)
save("espejo", render(rows, yaw=np.radians(18), pitch=0.04, distance=2.3, size=640, lit=False, background=CARD))

wig = [("frames", ("a.jpg", HOROWITZ, "image/jpeg")), ("face_frames", ("f.jpg", HOROWITZ, "image/jpeg"))]
rows, _ = splats(post("/api/transfer/splat", {"angles": "0", "head": "face"}, files=wig))
lo, hi = np.percentile(rows[rows[:, 12] > 0.3, :3], [1, 99], axis=0)
rows[:, :3] -= (lo + hi) / 2
for name, yaw in [("peluca-frente", 0), ("peluca-giro", 42)]:
    save(name, render(rows, yaw=np.radians(yaw), pitch=0.08, distance=2.35, size=640, lit=True, background=CARD))
print("listo")
