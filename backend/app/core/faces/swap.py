import cv2
import numpy as np

from app.core.faces.blend import face_alpha, match_colors, pyramid_blend
from app.core.faces.mesh import OVAL, face_triangles, face_width, facing, mirror_index, signed_areas
from app.core.faces.warp import bounds, triangle_ids, warp_mesh

SEEN = 0.55


def mirrored(source, source_points):
    """The donor photo flipped left to right, with its points renumbered so
    that point i is again the same part of the face: the visible cheek takes
    the place of the hidden one."""
    flipped = cv2.flip(source, 1)
    points = source_points.copy()
    points[:, 0] = source.shape[1] - 1 - points[:, 0]
    return flipped, points[mirror_index()]


def visibility(points, target_points, triangles):
    """How much of each triangle the camera sees on the donor, compared with
    the same triangle on the target (1 = as open as on the target, 0 = seen
    edge-on or from behind)."""
    scale = (face_width(target_points) / max(face_width(points), 1.0)) ** 2
    donor = signed_areas(points, triangles) * facing() * scale
    target = np.maximum(signed_areas(target_points, triangles) * facing(), 1e-3)
    return np.clip(donor / target / SEEN, 0.0, 1.0)


def paste_face(canvas, target, target_points, source, source_points):
    """Puts the face of `source` on the person in `target` and draws it on
    `canvas`. The source face is moved triangle by triangle onto the target
    mesh, recolored to the target's skin and light, and blended band by band
    inside the target's face oval. Triangles that face away from the camera
    on the target are culled; where the donor shows a triangle edge-on (a
    turned head), its mirror twin on the other cheek is used instead."""
    triangles = face_triangles(False)
    fw = face_width(target_points)
    x0, y0, x1, y1 = bounds(target_points, target.shape, int(fw * 0.25))
    if x1 - x0 < 16 or y1 - y0 < 16:
        return canvas
    local = target_points - (x0, y0)
    window = target[y0:y1, x0:x1]
    front = signed_areas(local, triangles) * facing() > 0
    warped, covered = warp_mesh(source, source_points, local, triangles, out=window, keep=front)
    direct = visibility(source_points, local, triangles)
    if direct[front].min() < 0.8:
        flipped, flipped_points = mirrored(source, source_points)
        other = visibility(flipped_points, local, triangles)
        weight = np.where(front, other * (1.0 - direct), 0.0)
        if weight.max() > 0.05:
            twin, _ = warp_mesh(flipped, flipped_points, local, triangles, out=window, keep=front)
            ids = triangle_ids(local, triangles, (0, 0, x1 - x0, y1 - y0), front)
            per_pixel = np.where(ids >= 0, weight[np.maximum(ids, 0)], 0.0).astype(np.float32)
            per_pixel = cv2.GaussianBlur(per_pixel, (0, 0), max(1.0, fw * 0.02))[..., None]
            warped = warped * (1.0 - per_pixel) + twin * per_pixel
    alpha = face_alpha(local, OVAL, window.shape, fw) * covered
    corrected = match_colors(warped, window, alpha, fw)
    canvas[y0:y1, x0:x1] = pyramid_blend(canvas[y0:y1, x0:x1], corrected, alpha)
    return canvas


def swap_faces(image, faces):
    """Every face gets the face of the person to its right (the last one
    gets the first one's), all read from the untouched photo."""
    canvas = image.astype(np.float32)
    count = len(faces)
    for index in range(count):
        donor = faces[(index + 1) % count]
        paste_face(canvas, image, faces[index], image, donor)
    return np.clip(canvas, 0, 255).astype(np.uint8)


def wear_face(image, faces, source, source_points):
    """Everybody in the picture gets the face from the saved photo."""
    canvas = image.astype(np.float32)
    for points in faces:
        paste_face(canvas, image, points, source, source_points)
    return np.clip(canvas, 0, 255).astype(np.uint8)
