import numpy as np


def _window_means(integral, top, left, height, width, size):
    """Mean of every size x size window whose corner is shifted by (top,
    left) in the padded picture, read from the summed-area table in O(1)."""
    t = integral
    total = (t[top + size: top + size + height, left + size: left + size + width]
             - t[top: top + height, left + size: left + size + width]
             - t[top + size: top + size + height, left: left + width]
             + t[top: top + height, left: left + width])
    return total / float(size * size)


def kuwahara(image, radius):
    """Kuwahara filter: an oil-paint look that keeps edges.

    Around each pixel there are four overlapping square windows, one per
    corner, each (radius + 1) pixels wide. The pixel takes the mean color of
    the window whose brightness varies the least, so flat areas become
    strokes of one color and an edge is never averaged across. Means and
    variances of every window come from summed-area tables (integral
    images), so the cost does not depend on the radius."""
    a = max(1, int(radius))
    height, width = image.shape[:2]
    color = image.astype(np.float64)
    light = color @ np.array([0.114, 0.587, 0.299])
    stack = np.dstack([color, light, light * light])
    padded = np.pad(stack, ((a, a), (a, a), (0, 0)), mode="reflect")
    integral = np.zeros((padded.shape[0] + 1, padded.shape[1] + 1, stack.shape[2]))
    integral[1:, 1:] = padded.cumsum(axis=0).cumsum(axis=1)
    windows = [_window_means(integral, top, left, height, width, a + 1) for top in (0, a) for left in (0, a)]
    spread = np.stack([w[..., 4] - w[..., 3] ** 2 for w in windows])
    best = spread.argmin(axis=0)
    means = np.stack([w[..., :3] for w in windows])
    rows, cols = np.mgrid[0:height, 0:width]
    return means[best, rows, cols].astype(np.float32)
