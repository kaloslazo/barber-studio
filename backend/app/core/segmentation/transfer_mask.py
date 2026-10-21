import cv2
import numpy as np

from app.core.segmentation.mp_segmenter import BACKGROUND, HAIR


def head_geometry(points=None, face_box=None):
    """Head frame shared by the scan and the try-on: eye-level center, face
    width, in-plane roll and the face polygon that must never count as hair."""
    if points is not None and len(points) >= 68:
        points = np.asarray(points, np.float32)
        left_eye = points[36:42].mean(axis=0)
        right_eye = points[42:48].mean(axis=0)
        eye_mid = (left_eye + right_eye) / 2
        dx, dy = right_eye - left_eye
        face_w = float(max(np.linalg.norm(points[16] - points[0]), 1.0))
        brow_y = float(points[17:27, 1].min())
        chin = points[8]
        jaw = points[0:17].copy()
        jaw_center = jaw.mean(axis=0)
        jaw = jaw_center + (jaw - jaw_center) * 1.04
        polygon = np.vstack([jaw, points[26:16:-1]]).astype(np.int32)
        return {
            "center": (float(points[[0, 16], 0].mean()), float(eye_mid[1])),
            "face_w": face_w,
            "roll": float(np.arctan2(dy, dx)),
            "brow_y": brow_y,
            "chin": (float(chin[0]), float(chin[1])),
            "polygon": polygon,
        }
    x, y, w, h = [float(value) for value in face_box]
    polygon = cv2.ellipse2Poly(
        (int(x + w / 2), int(y + h * 0.54)), (max(1, int(w * 0.46)), max(1, int(h * 0.56))), 0, 0, 360, 10,
    )
    return {
        "center": (x + w / 2, y + h * 0.4),
        "face_w": w * 0.92,
        "roll": 0.0,
        "brow_y": y + h * 0.22,
        "chin": (x + w / 2, y + h),
        "polygon": polygon,
    }


def shift_geometry(geometry, dx, dy):
    shifted = dict(geometry)
    shifted["center"] = (geometry["center"][0] + dx, geometry["center"][1] + dy)
    shifted["brow_y"] = geometry["brow_y"] + dy
    shifted["chin"] = (geometry["chin"][0] + dx, geometry["chin"][1] + dy)
    shifted["polygon"] = geometry["polygon"] + np.array([int(dx), int(dy)], np.int32)
    return shifted


def scale_geometry(geometry, factor):
    if factor == 1.0:
        return geometry
    scaled = dict(geometry)
    scaled["center"] = (geometry["center"][0] * factor, geometry["center"][1] * factor)
    scaled["face_w"] = geometry["face_w"] * factor
    scaled["brow_y"] = geometry["brow_y"] * factor
    scaled["chin"] = (geometry["chin"][0] * factor, geometry["chin"][1] * factor)
    scaled["polygon"] = np.round(geometry["polygon"] * factor).astype(np.int32)
    return scaled


def follow_head(probabilities, source, target):
    """Carries a segmentation from the frame of `source` to the frame of
    `target` with the similarity transform of the head (shift, scale, roll)."""
    theta = target["roll"] - source["roll"]
    factor = target["face_w"] / source["face_w"]
    cos, sin = np.cos(theta) * factor, np.sin(theta) * factor
    sx, sy = source["center"]
    tx, ty = target["center"]
    matrix = np.array([[cos, -sin, tx - cos * sx + sin * sy], [sin, cos, ty - sin * sx - cos * sy]], np.float32)
    h, w = probabilities.shape[1:]
    layers = []
    for index, layer in enumerate(probabilities):
        border = 1.0 if index == BACKGROUND else 0.0
        layers.append(cv2.warpAffine(layer, matrix, (w, h), flags=cv2.INTER_LINEAR, borderValue=border))
    return np.stack(layers)


def head_window(shape, geometry, margin=1.0):
    """Square-ish window that contains the whole head and long hair."""
    h, w = shape
    cx, cy = geometry["center"]
    fw = geometry["face_w"] * margin
    x0, x1 = int(max(0, cx - 1.9 * fw)), int(min(w, cx + 1.9 * fw))
    y0, y1 = int(max(0, cy - 1.6 * fw)), int(min(h, cy + 2.2 * fw))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return 0, 0, w, h
    return x0, y0, x1, y1


def _ellipse(shape, geometry, offset, axes):
    mask = np.zeros(shape, np.uint8)
    cx, cy = geometry["center"]
    fw = geometry["face_w"]
    angle = np.degrees(geometry["roll"])
    cos, sin = np.cos(geometry["roll"]), np.sin(geometry["roll"])
    center = (int(cx - sin * offset * fw), int(cy + cos * offset * fw))
    cv2.ellipse(mask, center, (max(1, int(axes[0] * fw)), max(1, int(axes[1] * fw))), angle, 0, 360, 255, -1)
    return mask


def transfer_mask(image_bgr, geometry, probabilities=None, fallback=None):
    """Hair of the head in `geometry` only: a binary mask plus a soft alpha.

    Hair probability (or the fallback mask) is limited to a head-shaped zone,
    the face polygon is removed, and only blobs connected to the crown are
    kept, so dark furniture or another person's hair are dropped."""
    shape = image_bgr.shape[:2]
    if probabilities is not None:
        soft = probabilities[HAIR]
    elif fallback is not None:
        soft = fallback.astype(np.float32) / 255.0
    else:
        return np.zeros(shape, np.uint8), np.zeros(shape, np.float32)
    fw = geometry["face_w"]
    zone = _ellipse(shape, geometry, 0.35, (1.3, 1.85))
    crown = _ellipse(shape, geometry, -0.1, (0.72, 0.95))
    face = np.zeros(shape, np.uint8)
    if geometry.get("face_visible", True):
        cv2.fillPoly(face, [geometry["polygon"]], 255)
        chin = (int(geometry["chin"][0]), int(geometry["chin"][1]))
        cv2.ellipse(face, chin, (max(1, int(0.38 * fw)), max(1, int(0.32 * fw))), np.degrees(geometry["roll"]), 0, 360, 255, -1)

    binary = np.where(soft > 0.5, 255, 0).astype(np.uint8)
    binary = cv2.bitwise_and(binary, zone)
    binary = cv2.bitwise_and(binary, cv2.bitwise_not(face))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    minimum = 0.004 * fw * fw
    touching = np.unique(labels[(crown > 0) & (binary > 0)])
    keep = np.zeros(count, bool)
    for label in touching:
        if label and stats[label, cv2.CC_STAT_AREA] >= minimum:
            keep[label] = True
    mask = np.where(keep[labels], 255, 0).astype(np.uint8)
    if not mask.any():
        return mask, np.zeros(shape, np.float32)

    near = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    alpha = np.where(near > 0, soft, 0.0).astype(np.float32)
    alpha[face > 0] = 0.0
    alpha = np.clip((alpha - 0.25) / 0.5, 0.0, 1.0)
    alpha = cv2.GaussianBlur(alpha, (0, 0), 0.8)
    return mask, alpha
