import numpy as np

from app.core.faces.mesh import CHIN, LEFT_EYE, LIPS, NOSE, OVAL, RIGHT_EYE, face_triangles, fit_similarity, mean_face, ring
from app.core.faces.warp import warp_mesh

PRESETS = {
    "caricature": {"exaggerate": 2.0},
    "eyes": {"eyes": 0.9},
    "nose": {"nose": 1.0},
    "big-head": {"face": 0.6, "eyes": 0.3},
    "tiny-face": {"face": -0.4},
    "alien": {"eyes": 1.1, "mouth": -0.45, "chin": -0.35, "nose": -0.3},
}


def _smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def bulge(points, center, radius, factor):
    """Scales the points around `center` by `factor`, fully at the center
    and fading to nothing at `radius`, so a feature grows or shrinks and the
    skin around it stretches smoothly."""
    offset = points - center
    distance = np.linalg.norm(offset, axis=1) / max(radius, 1e-6)
    weight = _smoothstep(1.0 - distance)
    return center + offset * (1.0 + (factor - 1.0) * weight)[:, None]


def exaggerate(points, amount):
    """Brennan's caricature: the difference between this face and the
    average face (aligned to it with a similarity fit) is multiplied, so
    whatever makes the face unique gets bigger."""
    reference = mean_face()
    if reference is None:
        return points
    average = fit_similarity(reference, points)(reference)
    return average + (points - average) * (1.0 + amount)


def deform(points, preset, amount):
    spec = PRESETS[preset]
    moved = points.astype(np.float64)
    width = float(np.linalg.norm(points[454] - points[234]))
    if "exaggerate" in spec:
        moved = exaggerate(moved, spec["exaggerate"] * amount)
    if "face" in spec:
        center = points[OVAL].mean(axis=0)
        moved = bulge(moved, center, width * 1.2, 1.0 + spec["face"] * amount)
    for key, group in (("eyes", RIGHT_EYE), ("eyes", LEFT_EYE), ("nose", NOSE), ("mouth", LIPS), ("chin", CHIN)):
        if key in spec:
            center = points[group].mean(axis=0)
            size = np.ptp(points[group], axis=0).max()
            moved = bulge(moved, center, max(size * 1.4, width * 0.14), 1.0 + spec[key] * amount)
    return moved


def caricature(image, faces, preset="caricature", amount=0.8):
    """Moves the face mesh with the preset and warps the photo along: the
    face points go where the preset says, a ring of fixed points around the
    head keeps the rest of the picture still, and every triangle in between
    carries its piece of the photo with it."""
    if preset not in PRESETS:
        raise ValueError(f"Unknown caricature preset: {preset}")
    triangles = face_triangles(True)
    result = image.astype(np.float32)
    for points in faces:
        fixed = ring(points)
        src = np.vstack([points, fixed])
        dst = np.vstack([deform(points, preset, amount), fixed])
        result, _ = warp_mesh(image, src, dst, triangles, out=result)
    return np.clip(result, 0, 255).astype(np.uint8)
