"""Figuras de Fiesta (cambio de cara, caricatura y fusión) para el informe.

Se ejecuta desde backend/ con el entorno del proyecto:

    cd backend && venv/bin/python ../report/diagramas/fiesta.py

Usa solo los retratos de dominio público de la NASA (Horowitz y Rubio),
corre FaceStudio tal como lo llama la API y guarda las tiras en
report/figures/ y las miniaturas del diagrama en img/.
"""

import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.faces.caricature import PRESETS  # noqa: E402
from app.core.faces.mesh import face_triangles, face_width, ring  # noqa: E402
from app.core.faces.session import FaceStudio  # noqa: E402

FIGURES = ROOT / "report" / "figures"
IMG = HERE / "img"
SIZE = (300, 340)
GAP = 6

studio = FaceStudio()
horowitz = cv2.imread(str(IMG / "horowitz.jpg"))
rubio = cv2.imread(str(ROOT / "frontend" / "assets" / "samples" / "muestra.jpg"))


def box(image, height=2.75, lift=0.15, size=SIZE):
    points = studio.detect(image)[0]
    fw = face_width(points)
    h, w = image.shape[:2]
    hh = height * fw / 2
    hw = hh * size[0] / size[1]
    shrink = min(1.0, w / (2 * hw), h / (2 * hh))
    hh, hw = hh * shrink, hw * shrink
    cx, cy = points.mean(axis=0) - (0, lift * fw)
    cx, cy = np.clip(cx, hw, w - hw), np.clip(cy, hh, h - hh)
    return int(cx - hw), int(cy - hh), int(cx + hw), int(cy + hh)


def crop(image, area, size=SIZE):
    x0, y0, x1, y1 = area
    return cv2.resize(image[y0:y1, x0:x1], size, interpolation=cv2.INTER_AREA)


def strip(images):
    h = images[0].shape[0]
    gap = np.full((h, GAP, 3), 255, np.uint8)
    row = [images[0]]
    for image in images[1:]:
        row += [gap, image]
    return np.hstack(row)


def save(path, image):
    cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, 90])


area_h, area_r = box(horowitz), box(rubio)

h_with_r, _ = studio.apply(horowitz, "swap", other=rubio)
r_with_h, _ = studio.apply(rubio, "swap", other=horowitz)
save(FIGURES / "fiesta_swap.jpg", strip([
    crop(horowitz, area_h), crop(rubio, area_r), crop(h_with_r, area_h), crop(r_with_h, area_r)]))

wide = box(horowitz, 3.2)
cartoons = [studio.apply(horowitz, "caricature", preset, 1.0)[0] for preset in PRESETS]

frames = studio.fusion(horowitz, rubio, steps=5)
save(FIGURES / "fiesta_fusion.jpg", strip([cv2.resize(f, (300, 300), interpolation=cv2.INTER_AREA) for f in frames]))

points = studio.detect(horowitz)[0]
mesh = np.vstack([points, ring(points)])
lines = horowitz.copy()
for a, b, c in face_triangles(True):
    cv2.polylines(lines, [np.round(mesh[[a, b, c]] * 16).astype(np.int32)], True, (224, 111, 46), 1, cv2.LINE_AA, shift=4)
for x, y in mesh[468:]:
    cv2.circle(lines, (int(round(x)), int(round(y))), 4, (159, 100, 232), -1, cv2.LINE_AA)
panels = [crop(image, wide) for image in [horowitz] + cartoons + [lines]]
gap = np.full((GAP, strip(panels[:4]).shape[1], 3), 255, np.uint8)
save(FIGURES / "fiesta_caricatura.jpg", np.vstack([strip(panels[:4]), gap, strip(panels[4:])]))

dots = horowitz.copy()
for x, y in points:
    cv2.circle(dots, (int(round(x)), int(round(y))), 2, (58, 58, 224), -1, cv2.LINE_AA)
thin = horowitz.copy()
for a, b, c in face_triangles(False):
    cv2.polylines(thin, [np.round(points[[a, b, c]] * 16).astype(np.int32)], True, (224, 111, 46), 1, cv2.LINE_AA, shift=4)
save(IMG / "fi_foto.jpg", crop(horowitz, area_h))
save(IMG / "fi_otra.jpg", crop(rubio, area_r))
save(IMG / "fi_puntos.jpg", crop(dots, area_h))
save(IMG / "fi_malla.jpg", crop(thin, area_h))
save(IMG / "fi_swap.jpg", crop(h_with_r, area_h))
save(IMG / "fi_cari.jpg", crop(cartoons[0], area_h))
save(IMG / "fi_fusion.jpg", cv2.resize(frames[2], (300, 300), interpolation=cv2.INTER_AREA))
print("listo:", ", ".join(p.name for p in sorted(FIGURES.glob("fiesta_*.jpg"))))
