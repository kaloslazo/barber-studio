import cv2
import numpy as np


def prune_background_gaps(image_bgr, mask, shrink=6, grow=25, margin=1.2):
    """Drops mask pixels whose color matches the background more than the hair.

    Seeds: eroded interior = confident hair, dilated ring outside = confident
    background. Each masked pixel is classified by normalized color distance
    to both clusters, so gaps between hair clumps fall out.
    """
    h, w = image_bgr.shape[:2]
    inner = cv2.erode(mask, np.ones((shrink, shrink), np.uint8))
    outer = cv2.dilate(mask, np.ones((grow, grow), np.uint8))
    ring = cv2.subtract(outer, mask)
    if (inner > 0).sum() < 500 or (ring > 0).sum() < 500:
        return mask

    hair_px = image_bgr[inner > 0].astype(np.float32)
    bg_px = image_bgr[ring > 0].astype(np.float32)
    hair_mu, hair_sd = hair_px.mean(0), hair_px.std(0) + 1e-6
    bg_mu, bg_sd = bg_px.mean(0), bg_px.std(0) + 1e-6

    query = image_bgr[mask > 0].astype(np.float32)
    d_hair = (np.abs(query - hair_mu) / hair_sd).sum(1)
    d_bg = (np.abs(query - bg_mu) / bg_sd).sum(1)

    keep = d_hair <= d_bg * margin
    result = np.zeros((h, w), np.uint8)
    hair_positions = np.where(mask > 0)
    keep_mask = np.zeros_like(mask, bool)
    keep_mask[hair_positions[0], hair_positions[1]] = keep
    result[keep_mask] = 255
    return result


def hair_matte(image_bgr, mask):
    """Soft alpha matte from a coarse binary hair mask.

    Two guided-filter passes with the photo as guide: the first spreads the
    mask along hair-colored regions with a radius that follows the size of
    the hair, the second snaps the transition to real edges. The result is
    a 0..1 matte without holes inside the hair and with soft, edge-aware
    borders, which a dye can blend through directly."""
    hair = (mask > 0).astype(np.float32)
    rows = np.where(hair > 0)[0]
    span = int(np.ptp(rows)) if len(rows) else 1
    radius = int(np.clip(span / 60.0, 3, 16))
    guide = image_bgr.astype(np.float32) / 255.0
    matte = cv2.ximgproc.guidedFilter(guide=guide, src=hair, radius=radius, eps=2e-3)
    matte = cv2.ximgproc.guidedFilter(guide=guide, src=np.clip(matte, 0.0, 1.0), radius=max(2, radius // 2), eps=1e-3)
    matte = np.clip((matte - 0.2) / 0.6, 0.0, 1.0)
    return matte * matte * (3.0 - 2.0 * matte)


def refine_hair_mask(image_bgr, mask, radius=8, eps=1e-3):
    """Edge-aware refinement: snaps the coarse YOLO mask to image structure.

    The guided filter uses the photo itself as guide, so the mask hugs real
    hair edges and background gaps between hair clumps drop out.
    """
    guide = image_bgr.astype(np.float32) / 255.0
    src = (mask > 0).astype(np.float32)
    refined = cv2.ximgproc.guidedFilter(guide=guide, src=src, radius=radius, eps=eps)
    cleaned = cv2.medianBlur((refined * 255).astype(np.uint8), 5)
    snapped = np.where(cleaned > 127, 255, 0).astype(np.uint8)
    return prune_background_gaps(image_bgr, snapped)
