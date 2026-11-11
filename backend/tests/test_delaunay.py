import cv2
import numpy as np

from app.core.geometry.delaunay import delaunay_triangles as bowyer_watson
from app.core.geometry.delaunay_fortune import delaunay_triangles as fortune


def _circumcircle(a, b, c):
    d = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
    ux = ((a @ a) * (b[1] - c[1]) + (b @ b) * (c[1] - a[1]) + (c @ c) * (a[1] - b[1])) / d
    uy = ((a @ a) * (c[0] - b[0]) + (b @ b) * (a[0] - c[0]) + (c @ c) * (b[0] - a[0])) / d
    return np.array([ux, uy]), np.hypot(ux - a[0], uy - a[1])


def _area(points, triangles):
    total = 0.0
    for i, j, k in triangles:
        a, b, c = points[i], points[j], points[k]
        total += abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2
    return total


def _hull(points):
    return cv2.convexHull(points.astype(np.float32))


def test_fortune_is_delaunay_on_random_points():
    rng = np.random.default_rng(0)
    for _ in range(40):
        points = rng.uniform(0, 500, (int(rng.integers(5, 120)), 2))
        triangles = fortune(points)
        assert len(triangles) == 2 * len(points) - 2 - len(_hull(points))
        for triangle in triangles:
            center, radius = _circumcircle(*points[list(triangle)])
            distance = np.hypot(*(points - center).T)
            distance[list(triangle)] = np.inf
            assert distance.min() >= radius * (1 - 1e-9)


def test_fortune_tiles_a_grid():
    for n in (4, 10, 20):
        points = np.array([(x, y) for x in range(n) for y in range(n)], float) * 10
        triangles = fortune(points)
        assert len(triangles) == 2 * n * n - 2 - 4 * (n - 1)
        assert abs(_area(points, triangles) / cv2.contourArea(_hull(points)) - 1) < 1e-6


def test_fortune_skips_degenerate_triangles():
    assert fortune(np.array([(i, 2 * i) for i in range(5)], float)) == []
    assert len(fortune(np.array([(0, 0), (10, 0), (0, 10), (10, 0)], float))) == 1


def test_fortune_contains_bowyer_watson():
    rng = np.random.default_rng(1)
    points = rng.uniform(0, 300, (80, 2))
    ours = {tuple(sorted(t)) for t in fortune(points)}
    check = {tuple(sorted(t)) for t in bowyer_watson(points)}
    assert check <= ours
