import cv2
import numpy as np

from app.core.geometry.warp import _bilinear_sample

SUBPIXEL = 4


def triangle_ids(points, triangles, box, keep=None):
    """Which triangle covers each pixel of `box` (-1 = none). Each triangle
    is rasterized once with its index as the color, with 1/16 px precision.
    Triangles with `keep` False are not drawn (back-face culling)."""
    x0, y0, x1, y1 = box
    ids = np.full((y1 - y0, x1 - x0), -1, np.int32)
    shifted = np.round((points - (x0, y0)) * (1 << SUBPIXEL)).astype(np.int32)
    for index, triangle in enumerate(triangles):
        if keep is None or keep[index]:
            cv2.fillConvexPoly(ids, shifted[triangle], int(index), lineType=cv2.LINE_8, shift=SUBPIXEL)
    return ids


def affine_maps(dst, src, triangles):
    """For every triangle, the affine map that takes a destination pixel to
    where it is read in the source: [x, y, 1] @ M = [u, v]. All triangles
    are solved in one batched 3x3 system."""
    d = dst[triangles].astype(np.float64)
    s = src[triangles].astype(np.float64)
    a = np.concatenate([d, np.ones(d.shape[:2] + (1,))], axis=2)
    det = np.linalg.det(a)
    flat = np.abs(det) < 1e-6
    a[flat] = np.eye(3)
    maps = np.linalg.solve(a, s)
    maps[flat] = np.nan
    return maps


def bounds(points, shape, pad=2):
    h, w = shape[:2]
    x0, y0 = np.floor(points.min(axis=0)).astype(int) - pad
    x1, y1 = np.ceil(points.max(axis=0)).astype(int) + pad
    return max(0, x0), max(0, y0), min(w, x1), min(h, y1)


def warp_mesh(image, src_points, dst_points, triangles, out=None, keep=None):
    """Piecewise-affine warp by inverse mapping: the pixels inside the
    destination mesh are read from `image` where the same triangle sits in
    the source mesh, with bilinear sampling. Returns the warped picture
    (pixels outside the mesh come from `out`, or are black) and the
    coverage mask. `keep` leaves triangles out."""
    shape = image.shape if out is None else out.shape
    box = bounds(dst_points, shape)
    x0, y0, x1, y1 = box
    result = np.zeros(shape[:2] + (3,), np.float32) if out is None else out.astype(np.float32).copy()
    covered = np.zeros(shape[:2], np.float32)
    if x1 <= x0 or y1 <= y0:
        return result, covered
    ids = triangle_ids(dst_points, triangles, box, keep)
    rows, cols = np.nonzero(ids >= 0)
    if not len(rows):
        return result, covered
    maps = affine_maps(dst_points, src_points, triangles)[ids[rows, cols]]
    xs, ys = (cols + x0).astype(np.float64), (rows + y0).astype(np.float64)
    u = xs * maps[:, 0, 0] + ys * maps[:, 1, 0] + maps[:, 2, 0]
    v = xs * maps[:, 0, 1] + ys * maps[:, 1, 1] + maps[:, 2, 1]
    real = np.isfinite(u) & np.isfinite(v)
    rows, cols, u, v = rows[real], cols[real], u[real], v[real]
    sampled, valid = _bilinear_sample(image.astype(np.float32), u, v)
    py, px = (rows + y0)[valid], (cols + x0)[valid]
    result[py, px] = sampled[valid]
    covered[py, px] = 1.0
    return result, covered
