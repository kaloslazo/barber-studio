import cv2
import numpy as np


def match_colors(source, target, mask, face_w):
    """Makes `source` (a face moved onto another person) take the skin tone
    and light of `target`. First a Reinhard transfer in Lab (mean and spread
    of each channel inside the mask), then the broad shading of the target:
    the ratio of both lightness channels blurred at a tenth of the face
    width, so a face lit from the left stays lit from the left."""
    inside = mask > 0.5
    if inside.sum() < 50:
        return source
    src = cv2.cvtColor(np.clip(source, 0, 255).astype(np.uint8), cv2.COLOR_BGR2LAB).astype(np.float32)
    dst = cv2.cvtColor(np.clip(target, 0, 255).astype(np.uint8), cv2.COLOR_BGR2LAB).astype(np.float32)
    for channel in range(3):
        s, d = src[..., channel][inside], dst[..., channel][inside]
        spread = np.clip(d.std() / (s.std() + 1e-3), 0.6, 1.6)
        src[..., channel] = (src[..., channel] - s.mean()) * spread + d.mean()
    sigma = max(2.0, face_w / 10.0)
    weight = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), sigma) + 1e-3
    low_src = cv2.GaussianBlur(src[..., 0] * mask, (0, 0), sigma) / weight
    low_dst = cv2.GaussianBlur(dst[..., 0] * mask, (0, 0), sigma) / weight
    src[..., 0] *= np.clip((low_dst + 5.0) / (low_src + 5.0), 0.7, 1.4)
    return cv2.cvtColor(np.clip(src, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR).astype(np.float32)


def pyramid_blend(base, top, alpha, levels=5):
    """Multiband blend (Burt and Adelson): both pictures are split in
    Laplacian bands and each band is mixed with the mask blurred to the same
    scale, so broad color changes blend over a wide strip and fine detail
    over a narrow one. No visible seam and no ghosting."""
    h, w = alpha.shape
    levels = int(max(1, min(levels, np.floor(np.log2(max(2, min(h, w)))) - 3)))
    gauss_a, gauss_b, gauss_m = [base.astype(np.float32)], [top.astype(np.float32)], [alpha.astype(np.float32)]
    for _ in range(levels):
        gauss_a.append(cv2.pyrDown(gauss_a[-1]))
        gauss_b.append(cv2.pyrDown(gauss_b[-1]))
        gauss_m.append(cv2.pyrDown(gauss_m[-1]))
    blended = None
    for level in range(levels, -1, -1):
        size = (gauss_a[level].shape[1], gauss_a[level].shape[0])
        if level == levels:
            band_a, band_b = gauss_a[level], gauss_b[level]
        else:
            band_a = gauss_a[level] - cv2.pyrUp(gauss_a[level + 1], dstsize=size)
            band_b = gauss_b[level] - cv2.pyrUp(gauss_b[level + 1], dstsize=size)
        m = gauss_m[level][..., None]
        band = band_a * (1.0 - m) + band_b * m
        blended = band if blended is None else cv2.pyrUp(blended, dstsize=size) + band
    return blended


def face_alpha(points, oval, shape, face_w, shrink=0.04, feather=0.05):
    """Soft mask of the face inside its oval, pulled in a little so the
    hairline and the jaw edge stay from the original photo."""
    mask = np.zeros(shape[:2], np.uint8)
    hull = cv2.convexHull(np.round(points[oval]).astype(np.int32))
    cv2.fillConvexPoly(mask, hull, 255)
    size = max(3, int(face_w * shrink) | 1)
    mask = cv2.erode(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size)))
    soft = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), max(1.0, face_w * feather))
    return np.clip(soft * 1.15, 0.0, 1.0) * (mask > 0)
