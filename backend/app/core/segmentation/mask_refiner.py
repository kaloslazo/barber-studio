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
