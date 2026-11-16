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
    sorted left to right. Live mode tracks between frames."""

    def __init__(self, live=False, max_faces=2):
        self.live = live
        self.max_faces = max_faces
        self._landmarker = None
        self._failed = False
        self._last_ms = 0

    def _create(self):
        model_path = MODELS_DIR / "face_landmarker.task"
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
        except ImportError:
            self._failed = True
            return
        if not model_path.exists():
            self._failed = True
            return
        options = vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO if self.live else vision.RunningMode.IMAGE,
            num_faces=self.max_faces,
            min_face_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._mp = mp
        self._landmarker = vision.FaceLandmarker.create_from_options(options)

    def detect(self, image_bgr):
        if self._landmarker is None and not self._failed:
            self._create()
        if self._failed:
            return []
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        frame = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        if self.live:
            now_ms = max(self._last_ms + 1, int(time.monotonic() * 1000))
            self._last_ms = now_ms
            result = self._landmarker.detect_for_video(frame, now_ms)
        else:
            result = self._landmarker.detect(frame)
        h, w = image_bgr.shape[:2]
        faces = [np.array([[p.x * w, p.y * h] for p in mesh[:MESH_POINTS]], np.float32) for mesh in result.face_landmarks]
        return sorted(faces, key=lambda points: float(points[:, 0].mean()))


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
