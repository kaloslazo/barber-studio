import cv2
import numpy as np


def hex_to_bgr(hex_color):
    hex_color = hex_color.strip().lstrip("#")
    if len(hex_color) != 6:
        raise ValueError(f"Invalid hex color: {hex_color}")
    try:
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError as error:
        raise ValueError(f"Invalid hex color: {hex_color}") from error
    return b, g, r


def hex_to_hsv(hex_color):
    b, g, r = hex_to_bgr(hex_color)
    hsv = cv2.cvtColor(np.uint8([[[b, g, r]]]), cv2.COLOR_BGR2HSV)[0, 0]
    return int(hsv[0]), int(hsv[1]), int(hsv[2])


def apply_dye(image_bgr, alpha, hex_color, strength=0.75):
    """Recolor the hair in `alpha` (0..1 soft mask) with the dye color.

    Works in Lab. The hair keeps its own strand texture (lightness detail
    around its mean) while the base lightness moves toward the dye, so dark
    hair can go blond and blond hair can go black. Chroma comes from the dye
    and fades in the deepest shadows like real pigment. `strength` (0..1)
    blends between natural hair and full dye."""
    weight = np.clip(alpha.astype(np.float32), 0.0, 1.0) * float(np.clip(strength, 0.0, 1.0))
    core = alpha > 0.5
    if core.sum() < 50:
        core = alpha > 0.1
    if core.sum() < 50:
        return image_bgr.copy()

    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    lightness = lab[..., 0]
    hair_mean = float(lightness[core].mean())
    hair_std = float(lightness[core].std()) + 1e-3
    target = cv2.cvtColor(np.uint8([[hex_to_bgr(hex_color)]]), cv2.COLOR_BGR2LAB)[0, 0].astype(np.float32)

    base = 0.72 * target[0] + 0.28 * hair_mean
    contrast = float(np.clip(20.0 / hair_std, 0.9, 1.8))
    detail = lightness - cv2.GaussianBlur(lightness, (0, 0), 1.5)
    shading = cv2.GaussianBlur(lightness, (0, 0), 1.5) - hair_mean
    new_l = np.clip(base + contrast * (0.8 * shading + 1.2 * detail), 0, 255)

    depth = np.clip(new_l / max(float(target[0]), 40.0), 0.0, 1.0)
    chroma = 0.4 + 0.5 * depth
    dyed = np.empty_like(lab)
    dyed[..., 0] = new_l
    dyed[..., 1] = 128.0 + (target[1] - 128.0) * chroma
    dyed[..., 2] = 128.0 + (target[2] - 128.0) * chroma
    dyed_bgr = cv2.cvtColor(np.clip(dyed, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR).astype(np.float32)

    weight = weight[..., None]
    blended = image_bgr.astype(np.float32) * (1.0 - weight) + dyed_bgr * weight
    return np.clip(blended, 0, 255).astype(np.uint8)
