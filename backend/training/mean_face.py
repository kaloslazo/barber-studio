"""Average face mesh for the caricature mode.

Runs the MediaPipe face mesh over frontal CelebAMask-HQ photos, aligns every
468-point mesh to the running mean with a similarity Procrustes fit (center,
unit size, best rotation) and averages them. Writes
backend/app/assets/faces/mean_face.npy (468 x 2, centered, RMS radius 1).

Usage, from backend/:
    venv/bin/python training/mean_face.py <CelebA-HQ-img folder> [count]
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.faces.mesh import FaceMeshes, normalize, procrustes

OUT = Path(__file__).resolve().parents[1] / "app" / "assets" / "faces" / "mean_face.npy"


def frontal(points):
    left, right, nose = points[234], points[454], points[1]
    span = right[0] - left[0]
    if span <= 0:
        return False
    return abs((nose[0] - left[0]) / span - 0.5) < 0.06


def main():
    folder = Path(sys.argv[1])
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    meshes = FaceMeshes(max_faces=1)
    shapes = []
    for index in range(count * 3):
        image = cv2.imread(str(folder / f"{index}.jpg"))
        if image is None:
            continue
        faces = meshes.detect(image)
        if len(faces) != 1 or not frontal(faces[0]):
            continue
        shapes.append(normalize(faces[0]))
        if len(shapes) >= count:
            break
    mean = shapes[0]
    for _ in range(4):
        aligned = [procrustes(shape, mean) for shape in shapes]
        mean = normalize(np.mean(aligned, axis=0))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    np.save(OUT, mean.astype(np.float32))
    print(f"{len(shapes)} faces -> {OUT}")


if __name__ == "__main__":
    main()
