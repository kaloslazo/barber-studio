"""GIFs de Fiesta con retratos de la NASA (dominio público).

Desde backend/:  venv/bin/python ../docs/captures/p6_fiesta/hacer_gifs.py
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.faces.caricature import PRESETS, caricature
from app.core.faces.session import FaceStudio

HOROWITZ = cv2.imread(str(ROOT / "frontend/assets/samples/ejemplo.jpg"))
RUBIO = cv2.imread(str(ROOT / "frontend/assets/samples/muestra.jpg"))
NAMES = {"caricature": "Caricatura", "eyes": "Ojotes", "nose": "Narizon", "big-head": "Cacheton", "tiny-face": "Carita", "alien": "Alien"}


def gif(frames, path, ms):
    images = [Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)) for frame in frames]
    images[0].save(path, save_all=True, append_images=images[1:], duration=ms, loop=0, optimize=True)


def square(image, side=360):
    h, w = image.shape[:2]
    s = min(h, w)
    crop = image[(h - s) // 2:(h - s) // 2 + s, (w - s) // 2:(w - s) // 2 + s]
    return cv2.resize(crop, (side, side), interpolation=cv2.INTER_AREA)


def caption(image, text):
    out = image.copy()
    cv2.rectangle(out, (0, out.shape[0] - 34), (out.shape[1], out.shape[0]), (20, 20, 20), -1)
    cv2.putText(out, text, (12, out.shape[0] - 11), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return out


studio = FaceStudio()

frames = [cv2.resize(frame, (360, 360), interpolation=cv2.INTER_AREA) for frame in studio.fusion(HOROWITZ, RUBIO, 17)]
gif(frames + frames[-2:0:-1], HERE / "fusion_horowitz_rubio.gif", 90)

faces = studio.detect(HOROWITZ)
frames = []
for preset in PRESETS:
    ramp = list(np.linspace(0.0, 1.0, 8)) + [1.0] * 5 + list(np.linspace(1.0, 0.0, 6))
    for amount in ramp:
        frames.append(caption(square(caricature(HOROWITZ, faces, preset, amount)), NAMES[preset]))
gif(frames, HERE / "caricaturas_horowitz.gif", 80)

swap_a, _ = studio.apply(HOROWITZ, "swap", other=RUBIO)
swap_b, _ = studio.apply(RUBIO, "swap", other=HOROWITZ)
row = [square(image) for image in (HOROWITZ, swap_a, RUBIO, swap_b)]
cv2.imwrite(str(HERE / "cambio_de_cara.jpg"), np.hstack(row), [cv2.IMWRITE_JPEG_QUALITY, 90])
print("listo")
