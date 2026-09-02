import cv2
import numpy as np


def warp_template(template_bgra, src_points, dst_points, triangles, out_shape, focus_bbox=None):
    """Piecewise-affine warp of a template onto target landmarks.

    Each Delaunay triangle of the target mesh gets its own affine transform
    (computed from the corresponding source triangle), so the template
    deforms to the target face. Triangles far from `focus_bbox` are skipped.
    """
    h, w = out_shape[:2]
    src = np.asarray(src_points, np.float32)
    dst = np.asarray(dst_points, np.float32)
    out = np.zeros((h, w, 4), np.float32)

    margin = 80
    for a, b, c in triangles:
        tri_dst = dst[[a, b, c]]
        if focus_bbox is not None:
            fx0, fy0, fx1, fy1 = focus_bbox
            tx0, ty0 = tri_dst[:, 0].min(), tri_dst[:, 1].min()
            tx1, ty1 = tri_dst[:, 0].max(), tri_dst[:, 1].max()
            if tx1 < fx0 - margin or tx0 > fx1 + margin or ty1 < fy0 - margin or ty0 > fy1 + margin:
                continue
        transform = cv2.getAffineTransform(src[[a, b, c]], tri_dst)
        warped = cv2.warpAffine(
            template_bgra.astype(np.float32),
            transform,
            (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0),
        )
        tri_mask = np.zeros((h, w), np.float32)
        cv2.fillConvexPoly(tri_mask, tri_dst.astype(np.int32), 1.0, cv2.LINE_AA)
        region = tri_mask > 0
        out[region] = warped[region]
    return out
