import cv2
import numpy as np


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
    """Recolor masked pixels with the target hue, preserving hair texture.

    Hue comes from the target color, saturation keeps per-strand variation and
    value preserves the original shading. `strength` (0..1) controls the blend.
    """
    target_h, target_s, target_v = target_hsv
    strength = float(np.clip(strength, 0.0, 1.0))

    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    dyed_hsv = hsv.copy()
    dyed_hsv[..., 0] = target_h
    dyed_hsv[..., 1] = np.clip(
        target_s * (0.55 + 0.45 * hsv[..., 1] / 255.0), 0, 255
    ).astype(np.uint8)
    v_scale = 1.0 - 0.55 * (1.0 - target_v / 255.0)
    dyed_hsv[..., 2] = np.clip(hsv[..., 2] * v_scale, 0, 255).astype(np.uint8)
    dyed = cv2.cvtColor(dyed_hsv, cv2.COLOR_HSV2BGR)

    rows = np.where((mask > 0).any(axis=1))[0]
    span = rows.max() - rows.min() if len(rows) else image_bgr.shape[0] // 4
    kernel = max(21, min(101, int(span // 12) | 1))
    alpha = cv2.GaussianBlur(mask, (kernel, kernel), 0).astype(np.float32) / 255.0
    alpha = alpha[..., None] * strength
    blended = image_bgr.astype(np.float32) * (1.0 - alpha) + dyed.astype(np.float32) * alpha
    return np.clip(blended, 0, 255).astype(np.uint8)
