import numpy as np

from app.core.faces.blend import face_alpha, match_colors, pyramid_blend
from app.core.faces.mesh import OVAL, face_triangles, face_width
from app.core.faces.warp import bounds, warp_mesh


def paste_face(canvas, target, target_points, source, source_points):
    """Puts the face of `source` on the person in `target` and draws it on
    `canvas`. The source face is moved triangle by triangle onto the target
    mesh, recolored to the target's skin and light, and blended band by band
    inside the target's face oval."""
    triangles = face_triangles(False)
    fw = face_width(target_points)
    x0, y0, x1, y1 = bounds(target_points, target.shape, int(fw * 0.25))
    if x1 - x0 < 16 or y1 - y0 < 16:
        return canvas
    local = target_points - (x0, y0)
    window = target[y0:y1, x0:x1]
    warped, covered = warp_mesh(source, source_points, local, triangles, out=window)
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
