import cv2
import numpy as np

from app.core.faces.blend import face_alpha, match_colors, pyramid_blend
from app.core.faces.mesh import OVAL, face_width, ring
from app.core.faces.warp import warp_mesh
from app.core.geometry.delaunay_fortune import delaunay_triangles

BASE_SWITCH = (0.5, 0.62)
MISSING_EDGE = 0.02


def _frame_points(width, height, count=4):
    xs = np.linspace(0, width - 1, count + 1)
    ys = np.linspace(0, height - 1, count + 1)
    top = [(x, 0) for x in xs]
    bottom = [(x, height - 1) for x in xs]
    left = [(0, y) for y in ys[1:-1]]
    right = [(width - 1, y) for y in ys[1:-1]]
    return np.array(top + bottom + left + right, np.float64)


def _crop(image, points, size):
    """Square picture around the face, with the face width a 2.1th of the
    side. The square is slid (and shrunk if it must) to stay inside the
    photo, so the frames never show mirrored borders."""
    h, w = image.shape[:2]
    side = min(face_width(points) * 2.1, h, w)
    center = np.clip(points.mean(axis=0), side / 2.0, (w - side / 2.0, h - side / 2.0))
    scale = size / side
    shift = np.array([size / 2.0, size / 2.0]) - center * scale
    matrix = np.array([[scale, 0.0, shift[0]], [0.0, scale, shift[1]]])
    crop = cv2.warpAffine(image, matrix, (size, size), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    return crop, points * scale + shift, matrix


def _missing(image, matrix, size):
    inside = cv2.warpAffine(np.ones(image.shape[:2], np.float32), matrix, (size, size), flags=cv2.INTER_LINEAR, borderValue=0)
    return float((inside < 0.5).mean())


def _place(image, matrix, size):
    """The photo moved by `matrix` into the square. Where the square goes past
    the photo, the edge colours are spread and blurred instead of mirrored,
    so a tightly cropped portrait does not grow copies of its own head."""
    placed = cv2.warpAffine(image, matrix, (size, size), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    inside = cv2.warpAffine(np.ones(image.shape[:2], np.float32), matrix, (size, size), flags=cv2.INTER_LINEAR, borderValue=0)
    if inside.min() > 0.999:
        return placed
    fill = cv2.GaussianBlur(placed, (0, 0), size / 18.0)
    inside = cv2.GaussianBlur(cv2.erode(inside, np.ones((5, 5), np.uint8)), (0, 0), size / 120.0)[..., None]
    return np.clip(placed * inside + fill * (1.0 - inside), 0, 255).astype(np.uint8)


def morph(image_a, points_a, image_b, points_b, steps=13, size=480):
    """Mesh morph between two faces. Both faces are cut to the same square,
    the second one is aligned to the first with a similarity fit, and for
    each t in [0, 1] both meshes are interpolated to an in-between shape and
    both photos are warped onto it. Only the face is cross dissolved (weights
    1 - t and t) and set in with a multiband blend; the rest of the frame is
    the photo of one parent (A up to the middle, then B after a short fade),
    so backgrounds, hair and shoulders never show as ghosts. When B's photo
    is cut too tight to fill the square, A's photo stays as the base all the
    way and B's face takes A's skin tone, so t = 1 is a face swap. t = 0.5
    is the "child": A's head and hair with the mixed face."""
    crop_a, pa, _ = _crop(image_a, points_a.astype(np.float64), size)
    _, pb, matrix_b = _crop(image_b, points_b.astype(np.float64), size)
    align, _ = cv2.estimateAffinePartial2D(pb.astype(np.float32), pa.astype(np.float32))
    total = np.hstack([align[:, :2] @ matrix_b[:, :2], (align[:, :2] @ matrix_b[:, 2] + align[:, 2])[:, None]])
    crop_b = _place(image_b, total, size)
    switch = _missing(image_b, total, size) <= MISSING_EDGE
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
        warped_a, warped_b = warped_a.astype(np.float32), warped_b.astype(np.float32)
        points = shape[:len(pa)]
        alpha = face_alpha(points, OVAL, (size, size), face_width(points), shrink=0.03, feather=0.06)
        if not switch:
            warped_b = match_colors(warped_b, warped_a, alpha, face_width(points), spread_range=(0.0, 1.6))
        face = (1.0 - t) * warped_a + t * warped_b
        lean = float(np.clip((t - BASE_SWITCH[0]) / (BASE_SWITCH[1] - BASE_SWITCH[0]), 0.0, 1.0))
        lean = lean * lean * (3.0 - 2.0 * lean) if switch else 0.0
        base = (1.0 - lean) * warped_a + lean * warped_b
        frames.append(np.clip(pyramid_blend(base, face, alpha), 0, 255).astype(np.uint8))
    return frames
