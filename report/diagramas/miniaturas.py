"""Miniaturas de cada etapa para los diagramas del informe.

Se ejecuta desde backend/ con el entorno del proyecto:

    cd backend && venv/bin/python ../report/diagramas/miniaturas.py

Toma el retrato de dominio público de la NASA en img/horowitz.jpg, corre
las etapas reales del pipeline y guarda un recorte de la cabeza de cada una
en img/.
"""

import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.coloring.dye import hex_to_bgr  # noqa: E402
from app.core.compositing import beard as beard_module  # noqa: E402
from app.core.compositing import haircut  # noqa: E402
from app.core.geometry.warp import warp_template  # noqa: E402
from app.core.segmentation.mask_refiner import refine_hair_mask  # noqa: E402
from app.core.geometry.delaunay import draw_mesh  # noqa: E402
from app.core.geometry.delaunay_fortune import delaunay_triangles  # noqa: E402
from app.core.pipeline import StylePipeline  # noqa: E402
from app.core.segmentation.mp_segmenter import BACKGROUND, CLOTHES, FACE_SKIN, HAIR  # noqa: E402

IMG = HERE / "img"
SIZE = (300, 340)

pipeline = StylePipeline()
photo = cv2.imread(str(IMG / "horowitz.jpg"))
face = pipeline.detector.largest_face(photo)
points = pipeline._landmarks(photo, face)
geometry = pipeline._head_geometry(points, face)
probabilities = pipeline._part_probabilities(photo, geometry)
hair_mask = pipeline.transfer_hair_mask(photo, face, points, probabilities=probabilities, geometry=geometry)

cx, cy = geometry["center"]
fw = geometry["face_w"]
h, w = photo.shape[:2]
box = [int(cx - 1.05 * fw), int(cy - 1.25 * fw), int(cx + 1.05 * fw), int(cy + 1.12 * fw)]
box = [max(0, box[0]), max(4, box[1]), min(w, box[2]), min(h, box[3])]


def save(name, image):
    x0, y0, x1, y1 = box
    crop = cv2.resize(image[y0:y1, x0:x1], SIZE, interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(IMG / f"{name}.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])


def dim(image, amount=0.45):
    return (image.astype(np.float32) * amount + 255 * (1 - amount) * 0.35).astype(np.uint8)


def overlay(base, mask, color, alpha=0.65):
    out = base.astype(np.float32)
    weight = np.clip(mask, 0, 1)[..., None] * alpha
    return (out * (1 - weight) + np.array(color, np.float32) * weight).astype(np.uint8)


save("foto", photo)

dots = photo.copy()
for x, y in points:
    cv2.circle(dots, (int(round(x)), int(round(y))), 3, (58, 58, 224), -1, cv2.LINE_AA)
save("puntos", dots)

seg = dim(photo, 0.55)
seg = overlay(seg, probabilities[BACKGROUND], (224, 111, 46), 0.55)
seg = overlay(seg, probabilities[CLOTHES], (120, 120, 120), 0.45)
seg = overlay(seg, probabilities[FACE_SKIN], (150, 170, 245), 0.55)
seg = overlay(seg, probabilities[HAIR], (26, 161, 217), 0.75)
save("segmentacion", seg)

save("malla", draw_mesh(photo, points, delaunay_triangles(points), color=(224, 111, 46)))

save("barba", pipeline.apply_beard(photo, "full", 0.9))
save("tinte", pipeline.apply_hair_dye(photo, "#b0502a", 0.85))
save("corte", pipeline.apply_haircut(photo, "mid-fade", 0.9))
gauss = pipeline.gaussian_portrait(photo, 1500, False, None)["render"]
save("gaussianas", cv2.resize(gauss, (w, h), interpolation=cv2.INTER_CUBIC))

x, y = haircut._frame(photo.shape[:2], geometry)
parts = haircut._parts(photo, hair_mask, geometry, probabilities)
front = haircut._front_hairline(x, y, geometry, parts["face_skin"])
crown = haircut._column_top(x, y, parts["hair"] + parts["skin"] > 0.5, front)
top = float(np.clip(max(front - 0.33, crown + 0.03), -0.9, -0.55))
skull = haircut._skull(x, y, top).astype(np.uint8)

frame = dim(photo, 0.6)
contours, _ = cv2.findContours(skull, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
cv2.drawContours(frame, contours, -1, (224, 111, 46), 3, cv2.LINE_AA)
line = (np.abs(y - haircut._hairline(x, front)) < 0.008) & (np.abs(x) < 0.42) & (skull > 0)
frame[line] = (58, 58, 224)
cv2.circle(frame, (int(cx), int(cy)), 5, (224, 111, 46), -1, cv2.LINE_AA)
save("marco", frame)

zeros = np.zeros_like(x)
keep, density, _, _ = haircut._layout(x, y, "mid-fade", haircut.SHORT_DENSITY * (1.1 - 0.4 * 0.9), zeros, front, top)
head = cv2.dilate(skull, np.ones((9, 9), np.uint8)).astype(np.float32)
zone = (y < haircut._hairline(x, front)).astype(np.float32)
plan = dim(photo, 0.6)
plan = overlay(plan, keep * head * zone, (26, 161, 217), 0.7)
plan = overlay(plan, (1 - keep) * head * zone * density / max(density.max(), 1e-6), (106, 160, 35), 0.8)
plan = overlay(plan, (1 - keep) * head * zone * (density < 0.05), (150, 170, 245), 0.7)
save("plan", plan)

original_layout = haircut._layout
haircut._layout = lambda x, y, *args: (np.zeros_like(x), np.zeros_like(x), np.zeros_like(x), np.zeros_like(x))
save("sin_pelo", pipeline.apply_haircut(photo, "mid-fade", 0.9))
haircut._layout = original_layout


extended = beard_module._extended_points(points)
dots = photo.copy()
for i, (px, py) in enumerate(extended):
    color = (58, 58, 224) if i < 68 else (224, 111, 46)
    cv2.circle(dots, (int(round(px)), int(round(py))), 3, color, -1, cv2.LINE_AA)
save("b_puntos", dots)
save("b_malla", draw_mesh(photo, extended, delaunay_triangles(extended), color=(224, 111, 46)))

templates = beard_module.load_templates()
pool = [t for t in templates if t["category"] == "full"]
skin = beard_module._target_skin_ycrcb(photo, points)
best = min(pool, key=lambda t: (t["skin_ycrcb"][1] - skin[1]) ** 2 + (t["skin_ycrcb"][2] - skin[2]) ** 2)
src = beard_module._extended_points(best["points"])
clamp = beard_module.beard_mask((h, w), points, "full")
rows, cols = np.where(clamp.any(axis=1))[0], np.where(clamp.any(axis=0))[0]
warped = warp_template(best["bgra"], src, extended, delaunay_triangles(extended), (h, w),
                       (cols.min(), rows.min(), cols.max(), rows.max()))
alpha = warped[..., 3:4].astype(np.float32) / 255.0
paper = np.full((h, w, 3), 236, np.float32)
save("b_plantilla", (paper * (1 - alpha) + warped[..., :3].astype(np.float32) * alpha).astype(np.uint8))
region = cv2.GaussianBlur(clamp.astype(np.float32) / max(clamp.max(), 1), (0, 0), 6)
save("b_region", overlay(dim(photo, 0.6), region, (46, 111, 224), 0.6))

raw = pipeline.segmenter.hair_mask(photo) if pipeline.segmenter is not None else None
mp_mask, _ = pipeline.transfer_hair_mask(photo, face, points, soft=True)
save("t_mediapipe", overlay(dim(photo, 0.6), (mp_mask > 0).astype(np.float32), (26, 161, 217), 0.75))
if raw is not None:
    yolo = refine_hair_mask(photo, raw)
    save("t_yolo", overlay(dim(photo, 0.6), (yolo > 0).astype(np.float32), (46, 111, 224), 0.75))
    union = np.count_nonzero((yolo > 0) | (mp_mask > 0))
    print("IoU YOLO / MediaPipe:", round(np.count_nonzero((yolo > 0) & (mp_mask > 0)) / union, 3))
lightness = cv2.cvtColor(photo, cv2.COLOR_BGR2LAB)[..., 0].astype(np.float32)
blurred = cv2.GaussianBlur(lightness, (0, 0), 1.5)
detail = np.clip(128 + 4.0 * (lightness - blurred), 0, 255).astype(np.uint8)
save("t_detalle", cv2.cvtColor(detail, cv2.COLOR_GRAY2BGR))
shading = cv2.normalize(cv2.GaussianBlur(lightness, (0, 0), 6), None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
save("t_sombreado", cv2.cvtColor(shading, cv2.COLOR_GRAY2BGR))

portrait = pipeline.gaussian_portrait(photo, 1500, False, None)
for key in ("target", "ellipses", "render"):
    save(f"g2_{key}", cv2.resize(portrait[key], (w, h), interpolation=cv2.INTER_CUBIC))
few = pipeline.gaussian_portrait(photo, 60, False, None)["render"]
save("g2_pocas", cv2.resize(few, (w, h), interpolation=cv2.INTER_CUBIC))

mesh = pipeline.landmark_detector.mesh3d(photo)
depth = dim(photo, 0.5)
z = mesh[:, 2]
z = (z - z.min()) / max(np.ptp(z), 1e-6)
colors = cv2.applyColorMap((255 * (1 - z)).astype(np.uint8).reshape(-1, 1), cv2.COLORMAP_VIRIDIS).reshape(-1, 3)
for (px, py), color in zip(mesh[:, :2], colors):
    cv2.circle(depth, (int(round(px)), int(round(py))), 2, tuple(int(c) for c in color), -1, cv2.LINE_AA)
save("e_malla3d", depth)

hair_alpha = pipeline.transfer_hair_mask(photo, face, points)
save("p_mascara", overlay(dim(photo, 0.6), (hair_alpha > 0).astype(np.float32), (26, 161, 217), 0.75))


def panel(source, index, count, name, skip=0):
    image = cv2.imread(str(ROOT / "report" / "figures" / source))
    width = image.shape[1] // count
    tile = image[skip:, index * width:(index + 1) * width]
    th, tw = tile.shape[:2]
    target = tw * SIZE[1] / SIZE[0]
    if target <= th:
        top = int((th - target) / 2)
        tile = tile[top:top + int(target)]
    cv2.imwrite(str(IMG / f"{name}.jpg"), cv2.resize(tile, SIZE, interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 92])


panel("fisica.jpg", 0, 3, "f_reposo")
panel("fisica.jpg", 1, 3, "f_movimiento")
panel("contrarreloj.jpg", 0, 5, "j_inicio", skip=30)
panel("contrarreloj.jpg", 2, 5, "j_medio", skip=30)
panel("contrarreloj.jpg", 4, 5, "j_final", skip=30)

print("miniaturas en", IMG)
