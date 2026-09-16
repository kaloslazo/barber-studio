import numpy as np


def _orientation(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])


def _in_circumcircle(p, a, b, c):
    """True if p lies strictly inside the circumcircle of triangle a,b,c.

    Uses the classic in-circle determinant. The sign flips with the winding
    of a,b,c, so we read the orientation first and compare accordingly.
    """
    ax, ay = a[0] - p[0], a[1] - p[1]
    bx, by = b[0] - p[0], b[1] - p[1]
    cx, cy = c[0] - p[0], c[1] - p[1]
    det = (
        (ax * ax + ay * ay) * (bx * cy - cx * by)
        - (bx * bx + by * by) * (ax * cy - cx * ay)
        + (cx * cx + cy * cy) * (ax * by - bx * ay)
    )
    orient = _orientation(a, b, c)
    if orient > 0:
        return det > 0
    if orient < 0:
        return det < 0
    return False


def delaunay_triangles(points, rect=None):
    """Delaunay triangulation over 2D points (Bowyer-Watson, from scratch).

    Returns a list of index triplets referencing the input points, matching
    the previous cv2.Subdiv2D-based signature. `rect` is accepted for
    compatibility and ignored (a super-triangle is derived from the data).
    """
    pts = np.asarray(points, dtype=np.float64)
    n = len(pts)
    if n < 3:
        return []

    min_xy = pts.min(axis=0)
    max_xy = pts.max(axis=0)
    span = float((max_xy - min_xy).max()) or 1.0
    mid = (min_xy + max_xy) / 2.0

    super_verts = np.array(
        [
            [mid[0] - 20.0 * span, mid[1] - span],
            [mid[0], mid[1] + 20.0 * span],
            [mid[0] + 20.0 * span, mid[1] - span],
        ],
        dtype=np.float64,
    )
    verts = np.vstack([pts, super_verts])
    s0, s1, s2 = n, n + 1, n + 2

    triangles = [(s0, s1, s2)]

    for i in range(n):
        p = verts[i]
        bad = [
            t for t in triangles
            if _in_circumcircle(p, verts[t[0]], verts[t[1]], verts[t[2]])
        ]

        edge_count = {}
        for t in bad:
            for e in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                key = (e[0], e[1]) if e[0] < e[1] else (e[1], e[0])
                edge_count[key] = edge_count.get(key, 0) + 1

        bad_set = set(bad)
        triangles = [t for t in triangles if t not in bad_set]

        for (a, b), count in edge_count.items():
            if count == 1:
                triangles.append((a, b, i))

    return [t for t in triangles if t[0] < n and t[1] < n and t[2] < n]


def draw_mesh(image_bgr, points, triangles, color=(255, 90, 40)):
    import cv2

    canvas = image_bgr.copy()
    points = np.asarray(points, dtype=np.int32)
    for a, b, c in triangles:
        pts = points[[a, b, c]].reshape(-1, 1, 2)
        cv2.polylines(canvas, [pts], True, color, 1, cv2.LINE_AA)
    for px, py in points:
        cv2.circle(canvas, (int(px), int(py)), 2, color, -1)
    return canvas
