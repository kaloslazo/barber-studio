"""Banco de robustez: 40 casos difíciles por cada herramienta de foto y de Fiesta.

Caras de CelebAMask-HQ elegidas por sus atributos y su pose (perfil, cabeza
inclinada, lentes, gorra, borrosa, flequillo, boca abierta, barba real,
calvo), fotos reales de Figaro1k (rizos, afro, trenzas, rastas, de espaldas),
una cara con diez degradaciones de cámara (baja resolución, poca luz con
ruido, luz lateral, contraluz, movida, JPEG malo, girada 25 grados, chica en
el cuadro, mano delante, selfie cortada) y cuatro fotos de varias personas.
Guarda una hoja de contacto por cada 8 casos, la de parejas y reporte.json.
Las hojas tienen caras de CelebA: no se suben al repositorio.

Desde backend/:
    venv/bin/python ../docs/robustez/robustez.py <CelebAMask-HQ> <Figaro1k/Original/Testing> [salida]
"""
import json
import sys
import time
import traceback
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.pipeline import StylePipeline
from app.core.faces.session import FaceStudio

OUT = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("robustez-salida")
OUT.mkdir(exist_ok=True)
CELEB = Path(sys.argv[1])
FIGARO = Path(sys.argv[2])
rng = np.random.default_rng(0)

lines = (CELEB / "CelebAMask-HQ-attribute-anno.txt").read_text().splitlines()
names = lines[1].split()
attrs = {}
for line in lines[2:6000]:
    parts = line.split()
    attrs[parts[0]] = {n: int(v) == 1 for n, v in zip(names, parts[1:])}
pose = {}
for line in (CELEB / "CelebAMask-HQ-pose-anno.txt").read_text().splitlines()[2:6000]:
    parts = line.split()
    pose[parts[0]] = tuple(float(v) for v in parts[1:4])


def pick(cond, count=1, skip=0):
    hits = [k for k in attrs if k in pose and cond(attrs[k], pose[k])]
    return hits[skip:skip + count]


def celeb(name):
    return cv2.imread(str(CELEB / "CelebA-HQ-img" / name))


cases = []
for label, cond, n in [
    ("perfil_der", lambda a, p: p[0] > 32 and not a["Wearing_Hat"], 2),
    ("perfil_izq", lambda a, p: p[0] < -32 and not a["Wearing_Hat"], 2),
    ("inclinada", lambda a, p: abs(p[2]) > 15, 1),
    ("lentes", lambda a, p: a["Eyeglasses"] and a["Male"], 2),
    ("gorra", lambda a, p: a["Wearing_Hat"] and a["Male"], 2),
    ("borrosa", lambda a, p: a["Blurry"], 2),
    ("flequillo", lambda a, p: a["Bangs"] and not a["Male"], 1),
    ("boca_abierta", lambda a, p: a["Mouth_Slightly_Open"] and a["Smiling"] and a["Male"], 1),
    ("barba_real", lambda a, p: a["Male"] and not a["No_Beard"] and a["Mustache"], 1),
    ("calvo", lambda a, p: a["Bald"], 1),
]:
    for index, name in enumerate(pick(cond, n)):
        cases.append((f"{label}_{index}", celeb(name)))

for frame in ["Frame00905", "Frame00930", "Frame00960", "Frame00320", "Frame00470", "Frame00620", "Frame00790", "Frame00170"]:
    hits = sorted(FIGARO.glob(f"{frame[:-2]}*-org.jpg"))
    if hits:
        cases.append((f"figaro_{hits[0].stem[5:10]}", cv2.imread(str(hits[0]))))

base = cv2.resize(celeb("32.jpg"), (512, 512))


def gradient(w, h, left, right):
    return np.tile(np.linspace(left, right, w, dtype=np.float32), (h, 1))[..., None]


def degrade(img, kind):
    h, w = img.shape[:2]
    f = img.astype(np.float32)
    if kind == "webcam_baja":
        small = cv2.resize(img, (w // 4, h // 4), interpolation=cv2.INTER_AREA)
        return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
    if kind == "oscura_ruido":
        return np.clip(f * 0.3 + rng.normal(0, 8, f.shape), 0, 255).astype(np.uint8)
    if kind == "luz_lateral":
        return np.clip(f * gradient(w, h, 1.25, 0.25), 0, 255).astype(np.uint8)
    if kind == "contraluz":
        out = f * 0.45
        out[: h // 6] = 250
        out[:, : w // 8] = 250
        return np.clip(out, 0, 255).astype(np.uint8)
    if kind == "movida":
        kernel = np.zeros((1, 21), np.float32)
        kernel[0] = 1 / 21
        return cv2.filter2D(img, -1, kernel)
    if kind == "jpeg_malo":
        return cv2.imdecode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 12])[1], cv2.IMREAD_COLOR)
    if kind == "girada_25":
        m = cv2.getRotationMatrix2D((w / 2, h / 2), 25, 1.0)
        return cv2.warpAffine(img, m, (w, h), borderMode=cv2.BORDER_REFLECT)
    if kind == "cara_chica":
        room = np.full((720, 1280, 3), (90, 95, 100), np.uint8)
        room[450:720, 300:1000] = (60, 50, 45)
        face = cv2.resize(img, (220, 220))
        room[200:420, 700:920] = face
        return room
    if kind == "mano":
        out = img.copy()
        cv2.ellipse(out, (w // 2 + 30, int(h * 0.78)), (110, 70), 15, 0, 360, (120, 150, 200), -1)
        return out
    if kind == "selfie_cortada":
        return cv2.resize(img[int(h * 0.25):, int(w * 0.1):int(w * 0.9)], None, fx=1.4, fy=1.4)
    raise ValueError(kind)


for kind in ["webcam_baja", "oscura_ruido", "luz_lateral", "contraluz", "movida", "jpeg_malo", "girada_25", "cara_chica", "mano", "selfie_cortada"]:
    cases.append((f"deg_{kind}", degrade(base, kind)))

pipeline = StylePipeline()
studio = FaceStudio()
studio.set_source(cv2.imread(str(ROOT / "frontend/assets/samples/ejemplo.jpg")))

TOOLS = [
    ("barba", lambda img: pipeline.apply_beard(img, "full", 0.9)),
    ("tinte", lambda img: pipeline.apply_hair_dye(img, "#b3312c", 0.8)),
    ("corte", lambda img: pipeline.apply_haircut(img, "mid-fade", 0.9)),
    ("alien", lambda img: studio.apply(img, "caricature", "alien", 1.0)[0]),
    ("cara_ajena", lambda img: studio.apply(img, "wear")[0]),
    ("forma", lambda img: pipeline.face_shape(img)),
    ("espejo3d", lambda img: pipeline.head3d(img, None)[0]),
]

report = []
crashes = []


def tile(img, text, size=220):
    if img is None or not isinstance(img, np.ndarray) or img.ndim != 3:
        cell = np.full((size, size, 3), 40, np.uint8)
    else:
        h, w = img.shape[:2]
        s = size / max(h, w)
        small = cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s))))
        cell = np.full((size, size, 3), 255, np.uint8)
        cell[: small.shape[0], : small.shape[1]] = small
    bar = np.full((22, size, 3), 255, np.uint8)
    cv2.putText(bar, text[:32], (3, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)
    return np.vstack([bar, cell])


rows = []
for name, img in cases:
    row = [tile(img, name)]
    for tool, fn in TOOLS:
        t = time.time()
        status = "ok"
        out = None
        try:
            out = fn(img)
            if out is None:
                status = "sin cara"
        except ValueError as error:
            status = f"aviso: {error}"[:40]
        except LookupError as error:
            status = f"aviso: {error}"[:40]
        except Exception as error:
            status = f"CRASH {type(error).__name__}"
            crashes.append((name, tool, traceback.format_exc()))
        seconds = time.time() - t
        report.append({"caso": name, "herramienta": tool, "estado": status, "s": round(seconds, 2)})
        if tool not in ("forma", "espejo3d"):
            row.append(tile(out if isinstance(out, np.ndarray) else None, f"{tool}: {status[:18]}"))
    rows.append(np.hstack(row))
    print(name, " | ".join(f"{r['herramienta']}={r['estado']}" for r in report if r["caso"] == name), flush=True)

for start in range(0, len(rows), 8):
    cv2.imwrite(str(OUT / f"hoja_{start // 8}.jpg"), np.vstack(rows[start:start + 8]), [cv2.IMWRITE_JPEG_QUALITY, 82])

pairs = []
a = cv2.resize(celeb("32.jpg"), (300, 300))
b = cv2.resize(celeb("441.jpg"), (200, 200))
room = np.full((720, 1280, 3), (110, 110, 115), np.uint8)
room[150:450, 250:550] = a
room[250:450, 800:1000] = b
pairs.append(("dos_tamanos", room))
side = celeb(pick(lambda a, p: p[0] > 25 and a["Male"], 1)[0])
pairs.append(("una_de_perfil", np.hstack([cv2.resize(celeb("10.jpg"), (512, 512)), cv2.resize(side, (512, 512))])))
pairs.append(("oscura_y_clara", np.hstack([degrade(base, "oscura_ruido"), cv2.resize(celeb("323.jpg"), (512, 512))])))
three = np.hstack([cv2.resize(celeb(n), (400, 400)) for n in ("32.jpg", "441.jpg", "10.jpg")])
pairs.append(("tres_personas", three))

prow = []
for name, img in pairs:
    row = [tile(img, name, 300)]
    for tool, fn in [("cambio", lambda i: studio.apply(i, "swap")), ("fusion", lambda i: studio.fusion(i, None, 5))]:
        try:
            out = fn(img)
            if tool == "cambio":
                out, count = out
                label = f"cambio ({count} caras)"
            else:
                out = out[2]
                label = "fusion t=0.5"
            row.append(tile(out, label, 300))
            report.append({"caso": name, "herramienta": tool, "estado": "ok"})
        except Exception as error:
            row.append(tile(None, f"{tool}: {type(error).__name__}", 300))
            report.append({"caso": name, "herramienta": tool, "estado": f"{type(error).__name__}: {error}"[:60]})
            if not isinstance(error, (ValueError, LookupError)):
                crashes.append((name, tool, traceback.format_exc()))
    prow.append(np.hstack(row))
    print(name, [r["estado"] for r in report if r["caso"] == name], flush=True)
cv2.imwrite(str(OUT / "parejas.jpg"), np.vstack(prow), [cv2.IMWRITE_JPEG_QUALITY, 82])

(OUT / "reporte.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
print("\nCRASHES:", len(crashes))
for name, tool, tb in crashes:
    print("---", name, tool)
    print(tb[-1500:])
