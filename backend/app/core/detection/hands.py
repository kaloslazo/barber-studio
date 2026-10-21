import time
from pathlib import Path

import cv2
import numpy as np

MODELS_DIR = Path(__file__).resolve().parents[3] / "models"
INDEX_TIP = 8
INDEX_PIP = 6
MIDDLE_TIP = 12
MIDDLE_PIP = 10
HAND_EDGES = [
    (0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12), (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
]


class FingerTracker:
    """Index fingertip tracker (MediaPipe Hand Landmarker, VIDEO mode).

    Returns the fingertip in pixels plus a 'pointing' flag: index finger
    extended and middle finger folded. Pointing switches the clipper on; an
    open hand only moves it.
    """

    def __init__(self, model="hand_landmarker.task"):
        self._path = MODELS_DIR / model
        self._landmarker = None
        self._failed = False
        self._last_ms = 0
        self.last_hand = None

    @property
    def available(self):
        return self._path.exists() and not self._failed

    def _ensure(self):
        if self._landmarker is not None or self._failed:
            return self._landmarker
        if not self._path.exists():
            self._failed = True
            return None
        try:
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
        except ImportError:
            self._failed = True
            return None
        options = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(self._path)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        return self._landmarker

    def fingertip(self, image_bgr):
        landmarker = self._ensure()
        if landmarker is None:
            return None
        import mediapipe as mp

        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        frame = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        now_ms = max(self._last_ms + 1, int(time.monotonic() * 1000))
        self._last_ms = now_ms
        result = landmarker.detect_for_video(frame, now_ms)
        if not result.hand_landmarks:
            self.last_hand = None
            return None
        hand = result.hand_landmarks[0]
        h, w = image_bgr.shape[:2]
        self.last_hand = np.array([[p.x * w, p.y * h] for p in hand], np.float32)
        point = lambda i: self.last_hand[i]
        wrist = point(0)
        tip = point(INDEX_TIP)
        index_out = np.linalg.norm(tip - wrist) > np.linalg.norm(point(INDEX_PIP) - wrist) * 1.15
        middle_out = np.linalg.norm(point(MIDDLE_TIP) - wrist) > np.linalg.norm(point(MIDDLE_PIP) - wrist) * 1.15
        return tip, bool(index_out and not middle_out)


def draw_hand(image_bgr, points, active):
    """Thin hand skeleton so the player sees what the tracker sees."""
    color = (80, 220, 80) if active else (235, 235, 235)
    for a, b in HAND_EDGES:
        pa = tuple(int(v) for v in points[a])
        pb = tuple(int(v) for v in points[b])
        cv2.line(image_bgr, pa, pb, color, 1, cv2.LINE_AA)
    for p in points:
        cv2.circle(image_bgr, (int(p[0]), int(p[1])), 2, color, -1, cv2.LINE_AA)
