import numpy as np


def _affine_from_triangles(dst_tri, src_tri):
    """Solve the affine map dst -> src from three point correspondences.

    We want, for each output pixel, where to read from in the template
    (inverse mapping), so the transform goes destination -> source.
    Each coordinate is u = a*x + b*y + c, found by solving a 3x3 system.
    """
    A = np.array(
        [
            [dst_tri[0, 0], dst_tri[0, 1], 1.0],
            [dst_tri[1, 0], dst_tri[1, 1], 1.0],
            [dst_tri[2, 0], dst_tri[2, 1], 1.0],
        ],
        dtype=np.float64,
    )
    try:
        cu = np.linalg.solve(A, src_tri[:, 0])
        cv = np.linalg.solve(A, src_tri[:, 1])
    except np.linalg.LinAlgError:
        return None
    return cu, cv


def _points_in_triangle(xs, ys, tri):
    """Vectorized barycentric inside-test for a batch of pixel centers."""
    (x0, y0), (x1, y1), (x2, y2) = tri
    denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    if abs(denom) < 1e-12:
        return np.zeros(len(xs), dtype=bool)
    a = ((y1 - y2) * (xs - x2) + (x2 - x1) * (ys - y2)) / denom
    b = ((y2 - y0) * (xs - x2) + (x0 - x2) * (ys - y2)) / denom
    c = 1.0 - a - b
    eps = -1e-6
    return (a >= eps) & (b >= eps) & (c >= eps)


def _bilinear_sample(img, xs, ys):
    """Sample img at float coordinates (xs, ys) with bilinear interpolation.

    Returns the sampled values and a validity mask (points outside the image
    are marked invalid so we don't paste garbage from clamped edges).
    """
    h, w = img.shape[:2]
    x0 = np.floor(xs).astype(np.int64)
    y0 = np.floor(ys).astype(np.int64)
    wx = xs - x0
    wy = ys - y0

    valid = (xs >= 0) & (xs <= w - 1) & (ys >= 0) & (ys <= h - 1)

    x0c = np.clip(x0, 0, w - 1)
    y0c = np.clip(y0, 0, h - 1)
    x1c = np.clip(x0 + 1, 0, w - 1)
    y1c = np.clip(y0 + 1, 0, h - 1)

    top_left = img[y0c, x0c]
    top_right = img[y0c, x1c]
    bottom_left = img[y1c, x0c]
    bottom_right = img[y1c, x1c]

    wa = ((1 - wx) * (1 - wy))[:, None]
    wb = (wx * (1 - wy))[:, None]
    wc = ((1 - wx) * wy)[:, None]
    wd = (wx * wy)[:, None]

    sampled = top_left * wa + top_right * wb + bottom_left * wc + bottom_right * wd
    return sampled, valid


def warp_template(template_bgra, src_points, dst_points, triangles, out_shape, focus_bbox=None):
    """Piecewise-affine warp of a template onto target landmarks (from scratch).

    Each Delaunay triangle of the target mesh gets its own affine transform
    (computed from the matching source triangle), so the template deforms to
    the target face. Triangles far from `focus_bbox` are skipped. Replaces the
    previous cv2.getAffineTransform + cv2.warpAffine version with the same
    signature.
    """
    h, w = out_shape[:2]
    src = np.asarray(src_points, np.float64)
    dst = np.asarray(dst_points, np.float64)
    template = np.asarray(template_bgra, np.float32)
    out = np.zeros((h, w, 4), np.float32)

    margin = 80
    for a, b, c in triangles:
        tri_dst = dst[[a, b, c]]
        tri_src = src[[a, b, c]]

        if focus_bbox is not None:
            fx0, fy0, fx1, fy1 = focus_bbox
            tx0, ty0 = tri_dst[:, 0].min(), tri_dst[:, 1].min()
            tx1, ty1 = tri_dst[:, 0].max(), tri_dst[:, 1].max()
            if tx1 < fx0 - margin or tx0 > fx1 + margin or ty1 < fy0 - margin or ty0 > fy1 + margin:
                continue

        minx = max(0, int(np.floor(tri_dst[:, 0].min())))
        maxx = min(w - 1, int(np.ceil(tri_dst[:, 0].max())))
        miny = max(0, int(np.floor(tri_dst[:, 1].min())))
        maxy = min(h - 1, int(np.ceil(tri_dst[:, 1].max())))
        if maxx < minx or maxy < miny:
            continue

        grid_y, grid_x = np.mgrid[miny:maxy + 1, minx:maxx + 1]
        xs = grid_x.ravel().astype(np.float64)
        ys = grid_y.ravel().astype(np.float64)

        inside = _points_in_triangle(xs, ys, tri_dst)
        if not inside.any():
            continue
        xs, ys = xs[inside], ys[inside]

        coeffs = _affine_from_triangles(tri_dst, tri_src)
        if coeffs is None:
            continue
        cu, cv = coeffs
        src_x = cu[0] * xs + cu[1] * ys + cu[2]
        src_y = cv[0] * xs + cv[1] * ys + cv[2]

        sampled, valid = _bilinear_sample(template, src_x, src_y)
        px = xs.astype(np.int64)[valid]
        py = ys.astype(np.int64)[valid]
        out[py, px] = sampled[valid]

    return out
