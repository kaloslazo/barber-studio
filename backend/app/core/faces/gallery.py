import json
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from app.core.faces.paint import kuwahara
from app.core.faces.swap import paste_face

GALLERY_DIR = Path(__file__).resolve().parents[4] / "frontend" / "assets" / "galeria"
PUBLIC = ("key", "name", "short", "year", "author", "style", "ask", "painting", "source", "license")


@lru_cache(maxsize=1)
def catalog():
    path = GALLERY_DIR / "galeria.json"
    if not path.exists():
        return {}
    return {entry["key"]: entry for entry in json.loads(path.read_text(encoding="utf-8"))}


def listing():
    return [{field: entry[field] for field in PUBLIC} for entry in catalog().values()]


@lru_cache(maxsize=16)
def portrait(key):
    """The portrait, its 468-point mesh and the facial hair that stays on
    top (0..1), all prepared once by training/gallery.py."""
    image = cv2.imread(str(GALLERY_DIR / f"{key}.jpg"))
    hair = cv2.imread(str(GALLERY_DIR / f"{key}-vello.png"), cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
    return image, np.asarray(catalog()[key]["points"], np.float32), hair


def is_monochrome(image):
    """Black and white or sepia: almost no spread in the Lab color axes."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32)
    return float(lab[..., 1].std() + lab[..., 2].std()) < 6.0


def texture(window, sigma):
    """The finest detail of the portrait itself: brush marks or film grain."""
    picture = window.astype(np.float32)
    return picture - cv2.GaussianBlur(picture, (0, 0), sigma)


def oil(face, window, face_w):
    """Brush strokes about a fortieth of the face wide, plus the painting's
    own stroke texture on top so the face looks painted with the same
    brush."""
    return kuwahara(face, max(2, round(face_w / 40.0))) + 0.9 * texture(window, max(1.5, face_w / 120.0))


def grain(face, window, face_w):
    """An old photo is grainy and soft: the face is softened a little and
    takes the photo's own grain."""
    soft = cv2.GaussianBlur(face, (0, 0), max(0.6, face_w / 500.0))
    return soft + 0.8 * texture(window, max(0.8, face_w / 400.0))


def into_portrait(image_bgr, points, key):
    """The visitor's face inside a famous portrait. It goes on the
    portrait's mesh with the same swap as Fiesta, but the portrait's beard
    and mustache stay on top, an old photo turns the face black and white
    (Reinhard with the color spread allowed to reach zero, and the contrast
    of a dark webcam photo allowed to grow up to 2.5 times) and takes its
    grain, and a painting repaints it with the Kuwahara filter and the
    painting's own brush texture."""
    if key not in catalog():
        raise ValueError(f"Unknown portrait: {key}")
    picture, target, hair = portrait(key)
    canvas = picture.astype(np.float32)
    spread = (0.0, 2.5) if is_monochrome(picture) else (0.6, 2.5)
    finish = oil if catalog()[key].get("painting") else grain
    paste_face(canvas, picture, target, image_bgr, points, keep=hair, finish=finish, spread_range=spread)
    return np.clip(canvas, 0, 255).astype(np.uint8)
