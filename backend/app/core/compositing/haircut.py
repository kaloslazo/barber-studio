import cv2
import numpy as np

STYLES = {
    "low-fade": {"reach": 0.45, "max_fade": 0.85},
}
DISABLED_STYLES = ("mid-fade", "high-fade", "buzz")


def _smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _protect_mask(shape, points, face_box):
    """Face protection: convex hull of the 68 landmarks, dilated. The fade
    alpha is exactly zero inside it (brows, eyes, glasses, skin)."""
    h, w = shape[:2]
    protect = np.zeros((h, w), np.uint8)
    if points is not None:
        hull = cv2.convexHull(np.asarray(points, np.float32).astype(np.int32))
        cv2.fillPoly(protect, [hull], 255)
    else:
        x, y, fw, fh = [int(v) for v in face_box]
        cv2.rectangle(protect, (x, y), (x + fw, y + fh), 255, -1)
    fh = int(face_box[3])
    grow = max(5, int(fh * 0.07))
    protect = cv2.dilate(protect, np.ones((grow * 2 + 1, grow * 2 + 1), np.uint8))
    return protect


def _scalp_samples(image_bgr, face_box, points, hair_mask):
    h, w = image_bgr.shape[:2]
    x, y, fw, fh = [int(v) for v in face_box]
    roi = np.zeros((h, w), np.uint8)
    if points is not None:
        pts = np.asarray(points, np.float32)
        nose_len = np.linalg.norm(pts[30] - pts[27])
        forehead = (pts[27] + pts[28]) / 2 + np.array([0.0, -nose_len * 0.45])
        cv2.circle(roi, (int(forehead[0]), int(forehead[1])), max(4, int(nose_len * 0.4)), 255, -1)
        cx = (pts[19][0] + pts[24][0]) / 2
        for corner in (pts[36], pts[45]):
            temple = corner + np.array([np.sign(corner[0] - cx) * fw * 0.08, -fh * 0.02])
            cv2.circle(roi, (int(temple[0]), int(temple[1])), max(3, int(fw * 0.05)), 255, -1)
    else:
        cv2.rectangle(roi, (x + fw // 4, y + fh // 12), (x + 3 * fw // 4, y + fh // 4), 255, -1)
    roi = cv2.subtract(roi, (hair_mask > 0).astype(np.uint8) * 255)
    return roi


def _scalp_lighting_field(image_bgr, hair_mask, scalp_bgr):
    replaced = image_bgr.astype(np.float32)
    replaced[hair_mask > 127] = scalp_bgr
    field = cv2.cvtColor(replaced.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
    field = cv2.GaussianBlur(field, (0, 0), max(8.0, image_bgr.shape[0] / 16.0))
    hair_zone = field[hair_mask > 127]
    median = np.median(hair_zone) if hair_zone.size else 128.0
    if median <= 1:
        median = 128.0
    return field / median


def _fade_field(image_bgr, face_box, points, hair_mask):
    """Continuous clipper field: 0 on top-center hair, growing toward temples,
    sideburns and nape. Zero inside the protected face hull."""
    h, w = image_bgr.shape[:2]
    x, y, fw, fh = [int(v) for v in face_box]
    cfg = STYLES["low-fade"]

    protect = _protect_mask(image_bgr.shape, points, face_box)
    protect_soft = cv2.GaussianBlur((protect > 0).astype(np.float32), (0, 0), max(2.0, fh / 90.0))

    d_face = cv2.distanceTransform((protect == 0).astype(np.uint8), cv2.DIST_L2, 5)

    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    cx = x + fw / 2.0
    lateral = np.abs(xs - cx) / max(fw * 0.55, 1.0)
    w_side = _smoothstep((lateral - 0.55) / 0.35)

    if points is not None:
        jaw_y = float(np.asarray(points, np.float32)[8][1])
    else:
        jaw_y = y + fh
    w_nape = 0.6 * _smoothstep((ys - jaw_y) / (fh * 0.35))

    reach_px = max(4.0, cfg["reach"] * fh)
    base = _smoothstep(1.0 - d_face / reach_px)
    fade = np.maximum(w_side * base, w_nape * base) * cfg["max_fade"]
    fade = fade * (1.0 - protect_soft)
    fade[protect > 0] = 0.0
    return fade, protect


def apply_haircut(image_bgr, hair_mask, face_box, points, style, strength):
    """Low-fade as a continuous length/density reduction on the real hair:
    texture smoothing + gradual pull toward local scalp tone with lighting.
    No deletion, no inpainting, face fully protected."""
    if style not in STYLES:
        raise ValueError(f"Style '{style}' is temporarily disabled during low-fade validation")
    h, w = image_bgr.shape[:2]
    fw, fh = int(face_box[2]), int(face_box[3])
    density = float(np.clip(strength, 0.0, 1.0))
    if density <= 0.0:
        return image_bgr.copy()

    hair_soft = cv2.GaussianBlur(
        (hair_mask > 0).astype(np.float32), (0, 0), max(2.0, fw / 150.0)
    )
    fade, protect = _fade_field(image_bgr, face_box, points, hair_mask)
    alpha = np.clip(fade * hair_soft * density, 0.0, 1.0)
    alpha[protect > 0] = 0.0

    roi = _scalp_samples(image_bgr, face_box, points, hair_mask)
    pixels = image_bgr[roi > 0]
    if len(pixels) < 100:
        bx, by, fw2, fh2 = [int(v) for v in face_box]
        pixels = image_bgr[by:by + fh2, bx:bx + fw2].reshape(-1, 3)
    scalp_bgr = np.median(pixels, axis=0).astype(np.float32)

    lighting = _scalp_lighting_field(image_bgr, hair_mask, scalp_bgr)
    k = max(5, int(fh / 60) | 1)
    shortened = cv2.GaussianBlur(image_bgr, (k, k), 0).astype(np.float32)

    target = scalp_bgr[None, None, :] * (0.80 + 0.20 * lighting)[..., None]
    clipped_blend = np.clip(0.72 * shortened + 0.28 * target, 0, 255)

    out = image_bgr.astype(np.float32) * (1.0 - alpha[..., None]) + clipped_blend * alpha[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)


def debug_overlays(image_bgr, hair_mask, face_box, points):
    """Colored overlays on the photo: protection, fade alpha, scalp samples."""
    fade, protect = _fade_field(image_bgr, face_box, points, hair_mask)
    hair_soft = cv2.GaussianBlur(
        (hair_mask > 0).astype(np.float32), (0, 0), max(2.0, int(face_box[2]) / 150.0)
    )
    alpha = np.clip(fade * hair_soft, 0.0, 1.0)
    roi = _scalp_samples(image_bgr, face_box, points, hair_mask)

    overlay1 = image_bgr.copy()
    overlay1[protect > 0] = (0.35 * overlay1[protect > 0] + 0.65 * np.array([60, 60, 240])).astype(np.uint8)
    contours, _ = cv2.findContours((hair_mask > 0).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(overlay1, contours, -1, (80, 220, 80), 3)

    overlay2 = image_bgr.copy()
    blue = np.array([220, 120, 60], np.float32)
    overlay2 = (overlay2 * (1.0 - 0.55 * alpha[..., None]) + blue * (0.55 * alpha[..., None])).astype(np.uint8)

    overlay3 = image_bgr.copy()
    overlay3[roi > 0] = (0.3 * overlay3[roi > 0] + 0.7 * np.array([60, 230, 230])).astype(np.uint8)

    return overlay1, overlay2, overlay3
