import cv2
import numpy as np


def delaunay_triangles(points, rect=None):
    """Delaunay triangulation over 2D points.

    Returns a list of index triplets referencing the input points.
    """
    points = np.asarray(points, dtype=np.float64)
    if rect is None:
        x, y, w, h = cv2.boundingRect(points.astype(np.float32))
        rect = (x - 10, y - 10, w + 20, h + 20)

    subdiv = cv2.Subdiv2D(rect)
    for px, py in points:
        subdiv.insert((float(px), float(py)))

    triangles = []
    for t in subdiv.getTriangleList():
        vertices = [(t[0], t[1]), (t[2], t[3]), (t[4], t[5])]
        idx = []
        for vx, vy in vertices:
            distances = np.hypot(points[:, 0] - vx, points[:, 1] - vy)
            nearest = int(np.argmin(distances))
            if distances[nearest] > 2.0:
                idx = None
                break
            idx.append(nearest)
        if idx and len(set(idx)) == 3:
            triangles.append(tuple(idx))
    return triangles


def draw_mesh(image_bgr, points, triangles, color=(255, 90, 40)):
    canvas = image_bgr.copy()
    points = np.asarray(points, dtype=np.int32)
    for a, b, c in triangles:
        pts = points[[a, b, c]].reshape(-1, 1, 2)
        cv2.polylines(canvas, [pts], True, color, 1, cv2.LINE_AA)
    for px, py in points:
        cv2.circle(canvas, (int(px), int(py)), 2, color, -1)
    return canvas
