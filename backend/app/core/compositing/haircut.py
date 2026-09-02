import cv2
import numpy as np

from app.core.compositing.alpha import inside_feather, organic_feather

STYLES = {
    "low-fade": {"band": 0.22},
    "mid-fade": {"band": 0.40},
    "high-fade": {"band": 0.58},
    "buzz": {"band": 1.1},
}


def _scalp_reference(image_bgr, points):
    """Skin tone + brightness sampled from the forehead."""
    if points is None:
        ycrcb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2YCrCb).astype(np.float32)
        return np.median(ycrcb.reshape(-1, 3), axis=0)
    pts = np.asarray(points, np.float32)
    nose_len = np.linalg.norm(pts[30] - pts[27])
    center = pts[27] + np.array([0.0, -nose_len * 0.55])
    radius = max(4, int(nose_len * 0.35))
    ycrcb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2YCrCb).astype(np.float32)
    x, y = int(center[0]), int(center[1])
    patch = ycrcb[max(0, y - radius):y + radius, max(0, x - radius):x + radius]
    return np.median(patch.reshape(-1, 3), axis=0)


def _hair_shading(image_bgr, hair_mask, face_box):
    """Smooth luminance of the hair: keeps head volume while removing strand noise."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    _, _, fh = face_box[1], None, face_box[3]
    shading = cv2.GaussianBlur(gray, (0, 0), max(5.0, fh / 12.0))
    return shading


def apply_haircut(image_bgr, hair_mask, face_box, points, style, strength):
    """Clipper-cut simulation on the real hair.

    The lower band of the hair mask (by distance from the face) blends toward
    the scalp tone, keeping the smooth head shading and adding clumpy texture
    so the transition reads as shaved hair instead of a flat patch.
    """
    h, w = image_bgr.shape[:2]
    x, y, fw, fh = [int(v) for v in face_box]
    density = float(np.clip(strength, 0.0, 1.0))

    face_zone = np.zeros((h, w), np.uint8)
    cv2.rectangle(face_zone, (x - fw // 6, y), (x + fw + fw // 6, y + fh), 255, -1)
    dist_to_face = cv2.distanceTransform(
        cv2.bitwise_not(face_zone), cv2.DIST_L2, 5
    )

    band_px = STYLES[style]["band"] * fh
    cut_band = np.clip(1.0 - dist_to_face / max(band_px, 1.0), 0.0, 1.0)
    cut_band[hair_mask == 0] = 0.0

    rng = np.random.default_rng(9)
    clump = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), max(4.0, fw / 30.0))
    clump = (clump - clump.min()) / (np.ptp(clump) + 1e-6)
    clump = np.clip((clump - 0.2) * 1.5, 0.0, 1.0)
    follicle = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 1.2)

    scalp = _scalp_reference(image_bgr, points)
    shading = _hair_shading(image_bgr, hair_mask, face_box)
    hair_mean_v = shading[hair_mask > 0].mean() if (hair_mask > 0).any() else 128.0
    rel_shading = shading / max(hair_mean_v, 1.0)

    scalp_v = scalp[0]
    cut_layer = np.empty((h, w, 3), np.float32)
    cut_v = np.clip(rel_shading * scalp_v * (0.85 + 0.3 * follicle), 0, 255)
    cut_layer_ycc = np.stack(
        [cut_v, np.full((h, w), scalp[1], np.float32), np.full((h, w), scalp[2], np.float32)],
        axis=-1,
    )
    cut_layer = cv2.cvtColor(
        np.clip(cut_layer_ycc, 0, 255).astype(np.uint8), cv2.COLOR_YCrCb2BGR
    ).astype(np.float32)

    alpha = cut_band * density
    alpha = alpha * (0.55 + 0.45 * clump)
    alpha = alpha * organic_feather(hair_mask, max(4.0, fh / 40.0), noise_scale=0.8, seed=5)

    out = (
        image_bgr.astype(np.float32) * (1.0 - alpha[..., None])
        + cut_layer * alpha[..., None]
    )
    return np.clip(out, 0, 255).astype(np.uint8)
