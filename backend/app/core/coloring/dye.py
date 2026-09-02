import cv2
import numpy as np

from app.core.compositing.alpha import inside_feather


def hex_to_hsv(hex_color):
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        raise ValueError(f"Invalid hex color: {hex_color}")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    pixel = np.uint8([[[b, g, r]]])
    hsv = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV)[0, 0]
    return int(hsv[0]), int(hsv[1]), int(hsv[2])


def apply_dye(image_bgr, mask, target_hsv, strength=0.75):
    """Recolor masked pixels with the target color, keeping smooth shading.

    Hue and saturation come from the target dye. The brightness map is the
    hair's own luminance smoothed (strand noise removed, only large lights
    and shadows kept), rescaled to the target color brightness. Dark hair is
    therefore lifted to the dye's lightness automatically, like real opaque
    dye. `strength` (0..1) blends between natural hair and full dye.
    """
    target_h, target_s, target_v = target_hsv
    strength = float(np.clip(strength, 0.0, 1.0))

    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)

    rows = np.where((mask > 0).any(axis=1))[0]
    span = rows.max() - rows.min() if len(rows) else image_bgr.shape[0] // 4
    smooth_k = max(15, min(81, int(span / 8) | 1))
    v_smooth = cv2.GaussianBlur(hsv[..., 2], (smooth_k, smooth_k), 0)

    inside = mask > 0
    mean_v = v_smooth[inside].mean() + 1e-6
    v_rel = v_smooth / mean_v
    v_rel = 1.0 + 0.6 * (v_rel - 1.0)

    dyed_hsv = hsv.copy()
    dyed_hsv[..., 0] = target_h
    dyed_hsv[..., 1] = np.clip(target_s * (0.85 + 0.15 * hsv[..., 1] / 255.0), 0, 255)
    dyed_hsv[..., 2] = np.clip(target_v * v_rel, 0, 255).astype(np.uint8)
    dyed_hsv[..., 1] = dyed_hsv[..., 1].astype(np.uint8)
    dyed = cv2.cvtColor(dyed_hsv, cv2.COLOR_HSV2BGR)

    feather = max(4.0, min(25.0, span / 40.0))
    alpha = inside_feather(mask, feather)
    alpha = alpha[..., None] * strength
    blended = image_bgr.astype(np.float32) * (1.0 - alpha) + dyed.astype(np.float32) * alpha
    return np.clip(blended, 0, 255).astype(np.uint8)
