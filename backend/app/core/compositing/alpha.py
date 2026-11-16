import cv2
import numpy as np


def inside_feather(mask, feather):
    """Smooth alpha ramp that stays strictly inside the mask."""
    dist = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 5)
    return np.clip(dist / max(feather, 1.0), 0.0, 1.0).astype(np.float32)


def organic_feather(mask, feather, noise_scale=0.6, seed=3, noise=None):
    """Feather whose boundary jitters per pixel, like a real hairline."""
    dist = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 5)
    if noise is None:
        rng = np.random.default_rng(seed)
        noise = cv2.GaussianBlur(rng.random(dist.shape).astype(np.float32), (0, 0), 2.0)
        noise = (noise - noise.min()) / (np.ptp(noise) + 1e-6) - 0.5
    alpha = np.clip((dist - noise * feather * noise_scale) / np.maximum(feather, 1.0), 0.0, 1.0)
    outside = cv2.distanceTransform((mask == 0).astype(np.uint8), cv2.DIST_L2, 5)
    band = np.clip(1.0 - outside / np.maximum(feather * 1.2, 1.0), 0.0, 1.0)
    return (alpha * band).astype(np.float32)


def local_feather(mask, feather, share=0.6):
    """Per-pixel feather capped at `share` of the local half-width of the
    mask, so a strip that is foreshortened (the far cheek of a turned head)
    keeps a solid core instead of fading out entirely."""
    dist = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 5)
    radius = int(np.ceil(2 * feather))
    widest = cv2.dilate(dist, cv2.getStructuringElement(cv2.MORPH_RECT, (2 * radius + 1, 2 * radius + 1)))
    return np.clip(share * widest, 2.0, feather).astype(np.float32)
