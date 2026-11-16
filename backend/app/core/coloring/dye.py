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

    Works in Lab. Lightness is split in three bands: strand detail (photo
    minus an edge-preserving bilateral blur), fine clumps and broad shading
    (the hair's own light). The base lightness moves most of the way to the
    dye, so black hair can really go blond, and the bands are scaled by how
    much lighter the hair gets, like a lighter surface showing more texture.
    Very dark gaps are soft-clipped so they do not turn into black dots, and
    the shading is measured on lightness clamped to the hair's own range, so
    skin under the soft edge does not glow. Chroma comes from the dye and
    fades in the deepest shadows like real pigment. `strength` (0..1) blends
    between natural hair and full dye."""
    weight = np.clip(alpha.astype(np.float32), 0.0, 1.0) * float(np.clip(strength, 0.0, 1.0))
    core = alpha > 0.5
    if core.sum() < 50:
        core = alpha > 0.1
    if core.sum() < 50:
        return image_bgr.copy()

    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    lightness = lab[..., 0]
    low, hair_mean, high = (float(v) for v in np.percentile(lightness[core], [3, 50, 97]))
    target = cv2.cvtColor(np.uint8([[hex_to_bgr(hex_color)]]), cv2.COLOR_BGR2LAB)[0, 0].astype(np.float32)

    clamped = np.clip(lightness, low, high + 8.0)
    smooth = cv2.bilateralFilter(clamped, 7, 18.0, 5.0)
    broad = cv2.GaussianBlur(smooth, (0, 0), 3.0)
    detail = clamped - smooth
    fine = smooth - broad
    shading = broad - hair_mean

    base = hair_mean + (float(target[0]) - hair_mean) * 0.82
    gain = float(np.clip((base + 25.0) / (hair_mean + 25.0), 0.75, 1.55))
    new_l = base + gain * (0.85 * shading + fine + 0.9 * detail)
    floor = 0.35 * base
    new_l = np.clip(np.where(new_l < floor, floor - (floor - new_l) * 0.25, new_l), 0, 255)

    depth = np.clip(new_l / max(float(target[0]), 35.0), 0.0, 1.3)
    chroma = np.clip(0.55 + 0.45 * depth, 0.0, 1.1)
    dyed = np.empty_like(lab)
    dyed[..., 0] = new_l
    dyed[..., 1] = 128.0 + (target[1] - 128.0) * chroma
    dyed[..., 2] = 128.0 + (target[2] - 128.0) * chroma
    dyed_bgr = cv2.cvtColor(np.clip(dyed, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR).astype(np.float32)

    weight = weight[..., None]
    blended = image_bgr.astype(np.float32) * (1.0 - weight) + dyed_bgr * weight
    return np.clip(blended, 0, 255).astype(np.uint8)
