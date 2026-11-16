import cv2
import numpy as np

from app.core.faces.mesh import face_width, ring
from app.core.faces.warp import warp_mesh
from app.core.geometry.delaunay_fortune import delaunay_triangles


def _frame_points(width, height, count=4):
    xs = np.linspace(0, width - 1, count + 1)
    ys = np.linspace(0, height - 1, count + 1)
    top = [(x, 0) for x in xs]
    bottom = [(x, height - 1) for x in xs]
    left = [(0, y) for y in ys[1:-1]]
    right = [(width - 1, y) for y in ys[1:-1]]
    return np.array(top + bottom + left + right, np.float64)


def _crop(image, points, size):
    """Square picture around the face, scaled so the face width is the side
    divided by 2.1."""
    fw = face_width(points)
    center = points.mean(axis=0)
    scale = size / (fw * 2.1)
    shift = np.array([size / 2.0, size * 0.5]) - center * scale
    matrix = np.array([[scale, 0.0, shift[0]], [0.0, scale, shift[1]]])
    crop = cv2.warpAffine(image, matrix, (size, size), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    return crop, points * scale + shift


def morph(image_a, points_a, image_b, points_b, steps=13, size=480):
    """Classic mesh morph between two faces. Both faces are cut to the same
    square, the second one is aligned to the first with a similarity fit,
    and for each t in [0, 1] both meshes are interpolated to an in-between
    shape: each photo is warped onto that shape and the two are cross
    dissolved with weights 1 - t and t. t = 0.5 is the "child" of both."""
    crop_a, pa = _crop(image_a, points_a.astype(np.float64), size)
    crop_b, pb = _crop(image_b, points_b.astype(np.float64), size)
    align, _ = cv2.estimateAffinePartial2D(pb.astype(np.float32), pa.astype(np.float32))
    crop_b = cv2.warpAffine(crop_b, align, (size, size), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    pb = pb @ align[:, :2].T + align[:, 2]

    frame = _frame_points(size, size)
    full_a = np.vstack([pa, ring(pa, 1.5, 20), frame])
    full_b = np.vstack([pb, ring(pb, 1.5, 20), frame])
    triangles = np.asarray(delaunay_triangles((full_a + full_b) / 2.0), np.int32)

    frames = []
    for t in np.linspace(0.0, 1.0, steps):
        shape = (1.0 - t) * full_a + t * full_b
        warped_a, _ = warp_mesh(crop_a, full_a, shape, triangles, out=crop_a)
        warped_b, _ = warp_mesh(crop_b, full_b, shape, triangles, out=crop_b)
        frames.append(np.clip((1.0 - t) * warped_a + t * warped_b, 0, 255).astype(np.uint8))
    return frames
