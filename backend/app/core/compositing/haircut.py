import cv2
import numpy as np

from app.core.compositing.bald import BaldRenderer

STYLES = {
    "low-fade": -0.05,
    "mid-fade": -0.30,
    "high-fade": -0.55,
    "buzz": None,
}
DISABLED_STYLES = ()


def _smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _kernel(size):
    size = max(3, int(size) | 1)
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))


def _stubble_color(image_bgr, hair_mask):
    pixels = image_bgr[hair_mask > 0]
    if len(pixels) < 50:
        hair = np.array([40.0, 128.0, 128.0], np.float32)
    else:
        lab = cv2.cvtColor(pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2LAB).reshape(-1, 3)
        hair = np.median(lab, axis=0).astype(np.float32)
    stubble = np.array([
        min(hair[0], 70.0) * 0.75,
        128.0 + (hair[1] - 128.0) * 0.15,
        128.0 + (hair[2] - 128.0) * 0.15 - 3.0,
    ], np.float32)
    pixel = np.clip(stubble, 0, 255).astype(np.uint8).reshape(1, 1, 3)
    return cv2.cvtColor(pixel, cv2.COLOR_LAB2BGR)[0, 0].astype(np.float32)


def _short_field(u, v, style):
    """1 where the cut leaves the hair short, 0 where it keeps it.

    `u`, `v` are skull coordinates (v = -1 at the crown, 0 at eye level).
    Fades shorten only the sides below the style's line and fade to skin
    toward the ears; the buzz shortens everything."""
    line = STYLES[style]
    if line is None:
        return np.ones_like(u), np.ones_like(u)
    lateral = _smoothstep((np.abs(u) - 0.42) / 0.30)
    short = _smoothstep((v - line) / 0.22) * lateral
    density = 1.0 - _smoothstep((v - (line + 0.30)) / 0.50)
    return short, density


def apply_haircut(image_bgr, hair_mask, geometry, style, strength, probabilities=None, seed=7):
    """Short-hair styles on a photo.

    The head is first shaved with the bald renderer (scalp painted inside
    the skull, background rebuilt where hair volume was), then a buzz-length
    stubble layer in the hair's own color grows back over the scalp. Fades
    blend that short version with the original along a line that rises
    from low to high fade; the buzz uses it everywhere."""
    if style not in STYLES:
        raise ValueError(f"Unknown haircut style: {style}")
    amount = float(np.clip(strength, 0.0, 1.0))
    if amount <= 0.0 or not (hair_mask > 0).any():
        return image_bgr.copy()

    fw = geometry["face_w"]
    shape = image_bgr.shape[:2]
    bald = BaldRenderer(work_face_width=240.0, inpaint_width=720.0).render(image_bgr, hair_mask, geometry, probabilities)
    skull, u, v, _ = BaldRenderer._skull(shape, geometry)
    short, density = _short_field(u, v, style)

    hair = (hair_mask > 0).astype(np.uint8)
    remove = cv2.dilate(hair, _kernel(fw * 0.07)).astype(np.float32)
    remove = cv2.GaussianBlur(remove, (0, 0), max(1.0, fw * 0.015))
    grow = cv2.dilate(hair, _kernel(5)).astype(np.float32)
    zone = cv2.GaussianBlur(skull.astype(np.float32) * grow, (0, 0), max(1.0, fw * 0.02))

    rng = np.random.default_rng(seed)
    noise = cv2.GaussianBlur(rng.random(shape).astype(np.float32), (0, 0), max(0.5, fw / 500.0))
    noise = (noise - noise.mean()) / (noise.std() + 1e-6)
    cover = density * zone * np.clip(0.66 + 0.14 * noise, 0.0, 0.9)
    cut = bald.astype(np.float32) * (1.0 - cover[..., None]) + _stubble_color(image_bgr, hair_mask) * cover[..., None]

    face = np.zeros(shape, np.uint8)
    cv2.fillPoly(face, [geometry["polygon"]], 255)
    face = cv2.erode(face, _kernel(fw * 0.03))
    weight = np.clip(short * np.maximum(remove, zone), 0.0, 1.0)
    weight[face > 0] = 0.0
    weight = (weight * amount)[..., None]
    out = image_bgr.astype(np.float32) * (1.0 - weight) + cut * weight
    return np.clip(out, 0, 255).astype(np.uint8)
