import cv2
import numpy as np


def inside_feather(mask, feather):
    """Smooth alpha ramp that stays strictly inside the mask."""
    dist = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 5)
    return np.clip(dist / max(feather, 1.0), 0.0, 1.0).astype(np.float32)


def organic_feather(mask, feather, noise_scale=0.6, seed=3):
    """Feather whose boundary jitters per pixel, like a real hairline."""
    rng = np.random.default_rng(seed)
    dist = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 5)
    noise = cv2.GaussianBlur(rng.random(dist.shape).astype(np.float32), (0, 0), 2.0)
    noise = (noise - noise.min()) / (np.ptp(noise) + 1e-6) - 0.5
    return np.clip((dist - noise * feather * noise_scale) / max(feather, 1.0), 0.0, 1.0).astype(np.float32)
