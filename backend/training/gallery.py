"""Prepares the portraits of the Galería (famous beards and haircuts).

Each original comes from Wikimedia Commons (public domain, see SOURCES). The
script crops it to a 3:4 bust around the face, measures its 468-point mesh
and draws the facial hair that must stay on top of the visitor's face (from
the app's own beard regions on the portrait's 68 points, grown in width and height by
factors picked by eye for each beard). Writes frontend/assets/galeria/<key>.jpg,
<key>-vello.png and galeria.json.

Usage, from backend/:
    venv/bin/python training/gallery.py <folder with the downloaded originals>
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.compositing.beard import _mustache_band, beard_mask, mouth_hole_mask
from app.core.faces.mesh import FaceMeshes, face_width
from app.core.pipeline import StylePipeline

OUT = Path(__file__).resolve().parents[2] / "frontend" / "assets" / "galeria"
WIDTH, HEIGHT = 900, 1200

PORTRAITS = [
    {"key": "lincoln", "short": "Lincoln", "name": "Abraham Lincoln", "year": "1863", "author": "Alexander Gardner",
     "style": "Barba de candado sin bigote", "ask": "barba larga solo en la mandíbula y el mentón, bigote y mejillas al ras",
     "hair": ["full"], "minus": ["mustache"], "grow": (0.02, 0.02),
     "source": "https://commons.wikimedia.org/wiki/File:Abraham_Lincoln_O-77_matte_collodion_print.jpg"},
    {"key": "marx", "short": "Marx", "name": "Karl Marx", "year": "1875", "author": "John Jabez Edwin Mayall",
     "style": "Barba completa larga", "ask": "barba completa sin recortar y melena hacia atrás",
     "hair": ["full", "mouth"], "minus": [], "grow": (0.05, 0.05),
     "source": "https://commons.wikimedia.org/wiki/File:Karl_Marx_001.jpg"},
    {"key": "twain", "short": "Twain", "name": "Mark Twain", "year": "1907", "author": "A. F. Bradley",
     "style": "Bigote de morsa y melena blanca", "ask": "bigote grueso que tape el labio de arriba, melena con volumen",
     "hair": ["mustache"], "minus": [], "grow": (0.16, 0.09),
     "source": "https://commons.wikimedia.org/wiki/File:Mark_Twain_by_AF_Bradley.jpg"},
    {"key": "douglass", "short": "Douglass", "name": "Frederick Douglass", "year": "c. 1879", "author": "George Kendall Warren",
     "style": "Melena hacia atrás y barba corta", "ask": "barba corta pareja y pelo largo peinado hacia atrás",
     "hair": ["full"], "minus": [], "grow": (0.03, 0.03),
     "source": "https://commons.wikimedia.org/wiki/File:Frederick_Douglass_(circa_1879).jpg"},
    {"key": "vangogh", "short": "Van Gogh", "name": "Vincent van Gogh", "year": "1887", "author": "autorretrato, Art Institute of Chicago",
     "style": "Barba pelirroja recortada", "ask": "barba corta recortada al ras de la mandíbula, tinte cobrizo",
     "hair": ["full"], "minus": [], "grow": (0.03, 0.03), "painting": True,
     "source": "https://commons.wikimedia.org/wiki/File:Vincent_van_Gogh_-_Self-Portrait_-_Google_Art_Project_(454045).jpg"},
    {"key": "einstein", "short": "Einstein", "name": "Albert Einstein", "year": "1947", "author": "Orren Jack Turner",
     "style": "Pelo despeinado y bigote", "ask": "nada de peine, bigote tupido",
     "hair": ["mustache"], "minus": [], "grow": (0.08, 0.05),
     "source": "https://commons.wikimedia.org/wiki/File:Albert_Einstein_Head.jpg"},
    {"key": "nietzsche", "short": "Nietzsche", "name": "Friedrich Nietzsche", "year": "1882", "author": "Gustav Adolf Schultze",
     "style": "Bigote manubrio gigante", "ask": "bigote sin recortar que tape la boca, lados cortos",
     "hair": ["mustache", "mouth"], "minus": [], "grow": (0.5, 0.1),
     "source": "https://commons.wikimedia.org/wiki/File:Nietzsche187a.jpg"},
]


def crop(image, points):
    """3:4 bust: face width a third of the crop, eyes at 40 % of its height."""
    fw = face_width(points)
    w = min(fw * 3.0, image.shape[1], image.shape[0] * 0.75)
    h = w / 0.75
    eyes = points[[33, 263]].mean(axis=0)
    x0 = float(np.clip(points[:, 0].mean() - w / 2, 0, image.shape[1] - w))
    y0 = float(np.clip(eyes[1] - 0.40 * h, 0, image.shape[0] - h))
    box = image[int(y0):int(y0 + h), int(x0):int(x0 + w)]
    return cv2.resize(box, (WIDTH, HEIGHT), interpolation=cv2.INTER_AREA)


def region(shape, points68, name):
    if name == "mustache":
        return _mustache_band(shape, points68, False)
    if name == "mouth":
        return mouth_hole_mask(shape, points68, False)
    return beard_mask(shape, points68, name)


def facial_hair(shape, points68, spec):
    shape = shape[:2]
    mask = np.zeros(shape, np.uint8)
    for name in spec["hair"]:
        mask = cv2.max(mask, region(shape, points68, name))
    for name in spec["minus"]:
        mask = cv2.subtract(mask, region(shape, points68, name))
    fw = float(np.linalg.norm(points68[16] - points68[0]))
    size = tuple(max(3, int(fw * g) | 1) for g in spec["grow"])
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, size))
    return cv2.GaussianBlur(mask, (0, 0), max(1.0, fw * 0.01))


def main():
    source = Path(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    meshes = FaceMeshes(max_faces=1)
    pipeline = StylePipeline()
    catalog = []
    for spec in PORTRAITS:
        original = cv2.imread(str(source / f"{spec['key']}.jpg"))
        found = meshes.detect(original)
        if not found:
            print(f"{spec['key']}: no face, skipped")
            continue
        portrait = crop(original, found[0])
        points = meshes.detect(portrait)[0]
        points68 = pipeline._landmarks(portrait, pipeline.detector.largest_face(portrait))
        cv2.imwrite(str(OUT / f"{spec['key']}.jpg"), portrait, [cv2.IMWRITE_JPEG_QUALITY, 88])
        cv2.imwrite(str(OUT / f"{spec['key']}-vello.png"), facial_hair(portrait.shape, points68, spec))
        entry = {k: v for k, v in spec.items() if k not in ("hair", "minus", "grow")}
        entry["painting"] = bool(spec.get("painting"))
        entry["license"] = "Dominio público (Wikimedia Commons)"
        entry["points"] = np.round(points, 1).tolist()
        catalog.append(entry)
        print(f"{spec['key']}: face {face_width(points):.0f} px")
    (OUT / "galeria.json").write_text(json.dumps(catalog, ensure_ascii=False))


if __name__ == "__main__":
    main()
