import cv2
import numpy as np

from app.core.compositing.beard import STYLES as BEARD_STYLES
from app.core.compositing.beard import beard_mask
from app.core.segmentation.mp_segmenter import FACE_SKIN


def _smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def facial_hair_alpha(image_bgr, points, probabilities=None, style=None):
    """Soft mask of the beard and mustache actually on the face.

    Inside the area where a full beard grows, a pixel counts as facial hair
    when it is darker and less red than the person's own skin and textured
    like hair: many short strokes in every direction. Smooth shading and
    the long edge of the jaw stay out. With `style`, the beard this app drew
    in that style is known and counts whole."""
    points = np.asarray(points, np.float32)
    face_w = float(np.linalg.norm(points[16] - points[0]))
    region = beard_mask(image_bgr.shape, points, "full")
    if region.max() <= 0:
        return np.zeros(image_bgr.shape[:2], np.float32)
    jaw = np.zeros(image_bgr.shape[:2], np.uint8)
    cv2.fillPoly(jaw, [np.round(points[0:17]).astype(np.int32)], 255)
    inner = max(3, int(face_w * 0.09) | 1)
    jaw = cv2.erode(jaw, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (inner, inner)))
    region = cv2.bitwise_and(region, jaw)
    region = cv2.GaussianBlur(region.astype(np.float32) / 255.0, (0, 0), max(1.0, face_w * 0.01))

    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    lightness = lab[..., 0]
    redness = lab[..., 1]
    face = np.zeros(image_bgr.shape[:2], np.uint8)
    cv2.fillPoly(face, [np.round(points[0:17]).astype(np.int32)], 255)
    skin = (face > 0) & (region < 0.05)
    skin &= points[29, 1] > np.mgrid[0:image_bgr.shape[0], 0:1][0]
    if probabilities is not None:
        skin &= probabilities[FACE_SKIN] > 0.6
    if skin.sum() < 50:
        skin = (face > 0) & (region < 0.05)
    reference = float(np.percentile(lightness[skin], 60)) if skin.any() else float(np.median(lightness))
    skin_red = float(np.median(redness[skin])) if skin.any() else 140.0

    size = max(3, int(face_w * 0.012) | 1)
    mean = cv2.blur(lightness, (size, size))
    spread = np.sqrt(np.maximum(cv2.blur(lightness * lightness, (size, size)) - mean * mean, 0.0))
    darker = _smoothstep((reference - lightness - 10.0) / 25.0)
    textured = _smoothstep((spread - 4.5) / 6.0)
    duller = _smoothstep((skin_red - redness - 1.0) / 6.0)
    gx = cv2.Sobel(lightness, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(lightness, cv2.CV_32F, 0, 1, ksize=3)
    sigma = max(1.5, face_w * 0.02)
    jxx = cv2.GaussianBlur(gx * gx, (0, 0), sigma)
    jyy = cv2.GaussianBlur(gy * gy, (0, 0), sigma)
    jxy = cv2.GaussianBlur(gx * gy, (0, 0), sigma)
    coherence = np.sqrt((jxx - jyy) ** 2 + 4.0 * jxy * jxy) / (jxx + jyy + 1e-3)
    scattered = 1.0 - _smoothstep((coherence - 0.6) / 0.25)
    alpha = darker * textured * scattered * (0.4 + 0.6 * duller)
    alpha = cv2.GaussianBlur(alpha, (0, 0), max(1.0, face_w * 0.008))
    alpha = _smoothstep((alpha - 0.12) / 0.35)
    close = max(3, int(face_w * 0.07) | 1)
    seed = np.where(alpha * region > 0.4, 255, 0).astype(np.uint8)
    enclosed = cv2.morphologyEx(seed, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close, close)))
    alpha = np.maximum(alpha, (enclosed > 0) * darker * duller)
    if style in BEARD_STYLES:
        drawn = beard_mask(image_bgr.shape, points, style).astype(np.float32) / 255.0
        drawn = cv2.GaussianBlur(drawn, (0, 0), max(1.0, face_w * 0.01))
        alpha = np.maximum(alpha * region, drawn * (0.55 + 0.45 * darker))
        return np.clip(cv2.GaussianBlur(alpha, (0, 0), max(0.8, face_w * 0.004)), 0.0, 1.0)
    alpha = cv2.GaussianBlur(alpha * region, (0, 0), max(0.8, face_w * 0.004))
    return np.clip(alpha, 0.0, 1.0)
