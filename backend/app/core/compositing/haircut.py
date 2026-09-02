import cv2
import numpy as np

STYLES = {
    "low-fade": {"lateral_start": 0.85, "lateral_full": 1.15},
    "mid-fade": {"lateral_start": 0.62, "lateral_full": 1.00},
    "high-fade": {"lateral_start": 0.40, "lateral_full": 0.85},
    "buzz": {"uniform": 0.55, "blur": 3},
}


def _smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _skin_reference(image_bgr, hair_mask, face_box):
    x, y, fw, fh = [int(v) for v in face_box]
    region = image_bgr[y:y + fh, x:x + fw]
    region_hair = (hair_mask > 0)[y:y + fh, x:x + fw]
    if region.size == 0:
        return np.array([140.0, 130.0, 120.0])
    skin_pixels = region[~region_hair]
    if len(skin_pixels) < 100:
        skin_pixels = region.reshape(-1, 3)
    return np.median(skin_pixels, axis=0).astype(np.float32)


def _scalp_tone_map(image_bgr, hair_mask, face_box):
    """Local scalp tone: spatially smoothed skin colors from a ring of
    skin-like pixels around the hair mask (background and clothes excluded)."""
    h, w = image_bgr.shape[:2]
    grow = max(15, int(face_box[3] * 0.06))
    ring = cv2.subtract(
        cv2.dilate(hair_mask, np.ones((grow * 2 + 1, grow * 2 + 1), np.uint8)),
        cv2.dilate(hair_mask, np.ones((7, 7), np.uint8)),
    )

    skin_ref = _skin_reference(image_bgr, hair_mask, face_box)
    ring_pixels = image_bgr[ring > 0].astype(np.float32)
    if len(ring_pixels) > 0:
        distances = np.linalg.norm(ring_pixels - skin_ref, axis=1)
        valid = distances < 60.0
        if valid.sum() > 300:
            skin_ring = np.zeros((h, w), np.float32)
            ys, xs = np.where(ring > 0)
            keep = valid
            skin_ring[ys[keep], xs[keep]] = 1.0
            coverage = skin_only = None
            skin_layer = np.zeros((h, w, 3), np.float32)
            skin_layer[ys[keep], xs[keep]] = ring_pixels[keep]
            k = max(21, int(face_box[3] * 0.35) | 1)
            num = cv2.GaussianBlur(skin_layer, (k, k), 0)
            den = cv2.GaussianBlur(skin_ring, (k, k), 0)[..., None] + 1e-3
            tone_map = num / den
            tone_map[den[..., 0] < 0.02] = skin_ref
            return tone_map
    return np.full((h, w, 3), skin_ref, np.float32)


def apply_haircut(image_bgr, hair_mask, face_box, points, style, strength):
    """Clipper-cut simulation on the real hair.

    fade = 0 on the top-center hair, grows smoothly toward the temples,
    sideburns and lower contour; the hair keeps its own texture and lighting
    while blending toward the LOCAL scalp tone:

        out = hair * (1 - fade) + scalp_tone * fade

    Buzz additionally blurs the hair slightly (short-hair look).
    """
    h, w = image_bgr.shape[:2]
    x, y, fw, fh = [int(v) for v in face_box]
    cfg = STYLES[style]
    density = float(np.clip(strength, 0.0, 1.0))
    if density <= 0.0:
        return image_bgr.copy()

    soft_mask = cv2.GaussianBlur(
        (hair_mask > 0).astype(np.float32), (0, 0), max(2.0, fw / 120.0)
    )

    if points is not None:
        pts = np.asarray(points, np.float32)
        brow_y = float((pts[19][1] + pts[24][1]) / 2.0)
    else:
        brow_y = y + fh * 0.35

    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    lateral = np.abs(xs - (x + fw / 2.0)) / max(fw * 0.62, 1.0)

    if "uniform" in cfg:
        fade = np.full((h, w), cfg["uniform"], np.float32)
        fade = np.maximum(fade, 0.8 * _smoothstep((lateral - 0.6) / 0.5))
    else:
        span = max(cfg["lateral_full"] - cfg["lateral_start"], 0.05)
        lat_fade = _smoothstep((lateral - cfg["lateral_start"]) / span)
        below_brows = ys > brow_y
        sideburn = _smoothstep((lateral - 0.5) / 0.4)
        fade = np.where(below_brows, np.maximum(lat_fade, sideburn), lat_fade)
        nape = _smoothstep((ys - (y + fh * 1.05)) / (fh * 0.35))
        fade = np.maximum(fade, 0.8 * nape)

    fade = np.clip(fade, 0.0, 0.85) * soft_mask * density

    tone_map = _scalp_tone_map(image_bgr, hair_mask, face_box)

    img = image_bgr.astype(np.float32)
    if "blur" in cfg:
        k = (int(cfg["blur"]) * 2 + 1) | 1
        shortened = cv2.GaussianBlur(image_bgr, (k, k), 0).astype(np.float32)
        blend = soft_mask * density
        img = img * (1.0 - blend[..., None]) + shortened * blend[..., None]

    out = img * (1.0 - fade[..., None]) + tone_map * fade[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)
