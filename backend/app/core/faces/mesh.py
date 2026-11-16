import time
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from app.core.detection.landmarks import MODELS_DIR
from app.core.geometry.delaunay_fortune import delaunay_triangles

MESH_POINTS = 468
MEAN_FACE = Path(__file__).resolve().parents[2] / "assets" / "faces" / "mean_face.npy"

OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377,
        152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
RIGHT_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 246, 161, 160, 159, 158, 157, 173]
LEFT_EYE = [263, 249, 390, 373, 374, 380, 381, 382, 362, 466, 388, 387, 386, 385, 384, 398]
LIPS = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185]
NOSE = [1, 2, 4, 5, 6, 19, 45, 48, 64, 94, 97, 98, 115, 129, 168, 195, 197, 275, 278, 294, 326, 327, 344, 358, 440, 220]
CHIN = [152, 148, 176, 149, 377, 400, 378, 175, 199, 200, 18, 83, 313, 421, 201]
RING = 28


class FaceMeshes:
    """Every face in a picture as a 468-point MediaPipe mesh in pixels,
    sorted left to right. Live mode tracks between frames.

    MediaPipe's face detector shrinks the whole picture to 128 px, so a face
    narrower than about a fifth of the frame is lost (two people a meter
    away from a laptop). When fewer faces than `wanted` show up, the picture
    is searched again in overlapping square tiles, first as tall as the
    frame and then smaller, and the meshes found are mapped back and merged."""

    def __init__(self, live=False, max_faces=2):
        self.live = live
        self.max_faces = max_faces
        self._landmarker = None
        self._tiles = None
        self._failed = False
        self._last_ms = 0

    def _create(self, live):
        model_path = MODELS_DIR / "face_landmarker.task"
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
        except ImportError:
            self._failed = True
            return None
        if not model_path.exists():
            self._failed = True
            return None
        options = vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO if live else vision.RunningMode.IMAGE,
            num_faces=self.max_faces,
            min_face_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._mp = mp
        return vision.FaceLandmarker.create_from_options(options)

    def _run(self, landmarker, image_bgr, live):
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        frame = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        if live:
            now_ms = max(self._last_ms + 1, int(time.monotonic() * 1000))
            self._last_ms = now_ms
            result = landmarker.detect_for_video(frame, now_ms)
        else:
            result = landmarker.detect(frame)
        h, w = image_bgr.shape[:2]
        return [np.array([[p.x * w, p.y * h] for p in mesh[:MESH_POINTS]], np.float32) for mesh in result.face_landmarks]

    def _tiled(self, image_bgr, faces, wanted):
        if self._tiles is None:
            self._tiles = self._create(False)
        h, w = image_bgr.shape[:2]
        for side in (min(h, w), int(min(h, w) * 0.6)):
            if side < 96 or len(faces) >= wanted:
                break
            step = max(1, int(side * 0.7))
            xs = sorted({*range(0, max(1, w - side), step), max(0, w - side)})
            ys = sorted({*range(0, max(1, h - side), step), max(0, h - side)})
            for y in ys:
                for x in xs:
                    for points in self._run(self._tiles, image_bgr[y:y + side, x:x + side], False):
                        points = points + (x, y)
                        if not any(_same_face(points, other) for other in faces):
                            faces.append(points)
        return faces

    def detect(self, image_bgr, wanted=1):
        if self._landmarker is None and not self._failed:
            self._landmarker = self._create(self.live)
        if self._failed:
            return []
        faces = self._run(self._landmarker, image_bgr, self.live)
        if len(faces) < min(wanted, self.max_faces):
            faces = self._tiled(image_bgr, faces, min(wanted, self.max_faces))
        return sorted(faces, key=lambda points: float(points[:, 0].mean()))


def _same_face(a, b):
    """Two meshes are the same face when their centers are closer than half
    a face width."""
    width = max(face_width(a), face_width(b), 1.0)
    return float(np.linalg.norm(a.mean(axis=0) - b.mean(axis=0))) < width * 0.5


def normalize(points):
    """Centered at the origin with an RMS radius of 1."""
    centered = points - points.mean(axis=0)
    return centered / np.sqrt((centered ** 2).sum(axis=1).mean())


def procrustes(shape, reference):
    """`shape` rotated to best match `reference` (both already normalized)."""
    u, _, vt = np.linalg.svd(shape.T @ reference)
    rotation = u @ vt
    if np.linalg.det(rotation) < 0:
        u[:, -1] *= -1
        rotation = u @ vt
    return shape @ rotation


def fit_similarity(src, dst):
    """Scale, rotation and shift that best take `src` onto `dst` in the
    least-squares sense (Umeyama). Returns a function that applies them."""
    mu_s, mu_d = src.mean(axis=0), dst.mean(axis=0)
    a, b = src - mu_s, dst - mu_d
    u, sigma, vt = np.linalg.svd(a.T @ b)
    d = np.sign(np.linalg.det(u @ vt))
    fix = np.diag([1.0, d])
    rotation = u @ fix @ vt
    scale = (sigma * np.diag(fix)).sum() / (a ** 2).sum()

    def apply(points):
        return (np.asarray(points, np.float64) - mu_s) @ rotation * scale + mu_d

    return apply


@lru_cache(maxsize=1)
def mean_face():
    if MEAN_FACE.exists():
        return np.load(MEAN_FACE).astype(np.float64)
    return None


def ring(points, scale=1.9, count=RING):
    """Fixed points on an ellipse around the face: beyond it nothing moves,
    so every warp blends into the untouched photo."""
    center = points[OVAL].mean(axis=0)
    half = (points[OVAL].max(axis=0) - points[OVAL].min(axis=0)) / 2.0
    angles = np.linspace(0.0, 2.0 * np.pi, count, endpoint=False)
    return center + np.stack([np.cos(angles) * half[0], np.sin(angles) * half[1]], axis=1) * scale


@lru_cache(maxsize=2)
def face_triangles(with_ring):
    """Triangles over the face points (and the outer ring), computed once
    with our Fortune sweep on the average face, so every face in every frame
    shares the same topology."""
    reference = mean_face()
    if reference is None:
        raise FileNotFoundError("mean_face.npy is missing: run training/mean_face.py")
    points = reference
    if with_ring:
        points = np.vstack([reference, ring(reference)])
    return np.asarray(delaunay_triangles(points), np.int32)


def face_width(points):
    return float(np.linalg.norm(points[454] - points[234]))


def signed_areas(points, triangles):
    a, b, c = (points[triangles[:, k]].astype(np.float64) for k in range(3))
    return 0.5 * ((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1]))


@lru_cache(maxsize=1)
def facing():
    """Sign of every face triangle seen from the front, read on the average
    face. A triangle whose sign flips on a turned head is facing away."""
    return np.sign(signed_areas(mean_face(), face_triangles(False)))


MIDLINE = [10, 151, 9, 8, 168, 6, 197, 195, 5, 4, 1, 2, 164, 0, 13, 14, 17, 18, 200, 199, 175, 152]


@lru_cache(maxsize=1)
def mirror_index():
    """For each of the 468 points, the point on the other side of the face.
    Every point is reflected across the midline of the average face (a line
    fitted to the forehead, nose and chin points) and the pairs are taken
    greedily from the closest, each point used once, so the result is a
    true swap of the two cheeks."""
    reference = mean_face()
    line = reference[MIDLINE]
    slope, offset = np.linalg.lstsq(np.c_[line[:, 1], np.ones(len(line))], line[:, 0], rcond=None)[0]
    axis = slope * reference[:, 1] + offset
    reflected = np.c_[2.0 * axis - reference[:, 0], reference[:, 1]]
    distance = ((reference[None, :, :] - reflected[:, None, :]) ** 2).sum(axis=2)
    distance = (distance + distance.T) / 2.0
    pairs = np.full(len(reference), -1)
    for flat in np.argsort(distance, axis=None):
        i, j = divmod(int(flat), len(reference))
        if pairs[i] < 0 and pairs[j] < 0:
            pairs[i], pairs[j] = j, i
        if (pairs >= 0).all():
            break
    return pairs
