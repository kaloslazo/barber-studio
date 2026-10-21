import time
from pathlib import Path

import cv2
import numpy as np

from app.core.detection.one_euro import OneEuroFilter

MODELS_DIR = Path(__file__).resolve().parents[3] / "models"

MP_TO_68 = [
    70, 63, 105, 66, 107,
    300, 293, 334, 296, 336,
    168, 6, 197, 4,
    129, 98, 2, 327, 358,
    33, 246, 161, 133, 160, 159,
    263, 466, 388, 362, 385, 373,
    61, 185, 40, 0, 267, 269, 291, 375, 321, 17, 314, 83,
    78, 191, 80, 81, 82, 13, 87, 88,
]

MP_JAW_ARC = [
    127, 234, 93, 132, 58, 172, 136, 150, 149, 176, 148, 152,
    377, 400, 378, 379, 365, 397, 288, 361, 323, 454, 356,
]


def _resample_polyline(points, n):
    """Evenly resample a polyline to n points by arc length."""
    points = np.asarray(points, np.float64)
    segment = np.linalg.norm(np.diff(points, axis=0), axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(segment)])
    targets = np.linspace(0.0, cumulative[-1], n)
    xs = np.interp(targets, cumulative, points[:, 0])
    ys = np.interp(targets, cumulative, points[:, 1])
    return np.stack([xs, ys], axis=1).astype(np.float32)


class LandmarkDetector:
    """68-point facial landmarks (iBUG convention).

    Primary: MediaPipe FaceMesh (468 points, robust to head rotation), mapped
    down to the classic 68 layout. Fallback: LBF facemark anchored to YuNet
    detections with a similarity transform.
    """

    def __init__(self, lbf_model="lbfmodel.yaml", yunet_model="yunet.onnx", live=False):
        self.live = live
        self._last_ms = 0
        self._filter = OneEuroFilter(min_cutoff=3.0, beta=0.3)
        self._mp_mesh = None
        self._mp_failed = False
        self.last_yaw = None
        self._lbf = None
        self._yunet = None
        self._yunet_template = str(MODELS_DIR / yunet_model)
        self._lbf_path = MODELS_DIR / lbf_model

    def _mediapipe_landmarks(self, image_bgr):
        if self._mp_failed:
            return None
        model_path = MODELS_DIR / "face_landmarker.task"
        if not model_path.exists():
            self._mp_failed = True
            return None
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
        except ImportError:
            self._mp_failed = True
            return None
        if self._mp_mesh is None:
            options = vision.FaceLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
                running_mode=(
                    vision.RunningMode.VIDEO if self.live else vision.RunningMode.IMAGE
                ),
                num_faces=1,
                min_face_detection_confidence=0.5,
                min_tracking_confidence=0.5,
                output_facial_transformation_matrixes=True,
            )
            self._mp_mesh = vision.FaceLandmarker.create_from_options(options)
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        if self.live:
            now_ms = max(self._last_ms + 1, int(time.monotonic() * 1000))
            self._last_ms = now_ms
            result = self._mp_mesh.detect_for_video(mp_image, now_ms)
        else:
            result = self._mp_mesh.detect(mp_image)
        if not result.face_landmarks:
            self._filter.reset()
            return None
        if result.facial_transformation_matrixes:
            rotation = np.asarray(result.facial_transformation_matrixes[0])[:3, :3]
            self.last_yaw = float(np.degrees(np.arctan2(rotation[0, 2], rotation[2, 2])))
        mesh = result.face_landmarks[0]
        h, w = image_bgr.shape[:2]
        all_points = np.array(
            [[lm.x * w, lm.y * h] for lm in mesh], dtype=np.float32
        )
        jaw = _resample_polyline(all_points[MP_JAW_ARC], 17)
        rest = all_points[MP_TO_68]
        points = np.vstack([jaw, rest])
        if self.live:
            points = self._filter(points, self._last_ms / 1000.0)
        return points

    def mesh3d(self, image_bgr):
        """Full MediaPipe mesh as (478, 3) pixels: x, y and depth z (same
        scale as x; smaller z is closer to the camera)."""
        if self.live or self._mediapipe_landmarks(image_bgr) is None:
            return None
        import mediapipe as mp

        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        result = self._mp_mesh.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
        if not result.face_landmarks:
            return None
        h, w = image_bgr.shape[:2]
        return np.array([[lm.x * w, lm.y * h, lm.z * w] for lm in result.face_landmarks[0]], np.float32)

    def _lbf_landmarks(self, image_bgr):
        if self._lbf is None:
            if not self._lbf_path.exists():
                return None, None
            self._lbf = cv2.face.createFacemarkLBF()
            self._lbf.loadModel(str(self._lbf_path))

        if self._yunet is None:
            if not Path(self._yunet_template).exists():
                return None, None
            h, w = image_bgr.shape[:2]
            self._yunet = cv2.FaceDetectorYN.create(
                self._yunet_template, "", (w, h), score_threshold=0.6
            )
        h, w = image_bgr.shape[:2]
        self._yunet.setInputSize((w, h))
        _, faces = self._yunet.detect(image_bgr)
        if faces is None or len(faces) == 0:
            return None, None
        face = max(faces, key=lambda f: float(f[2]) * float(f[3]))
        box = [float(v) for v in face[:4]]
        anchors = np.array(
            [
                [face[4], face[5]],
                [face[6], face[7]],
                [face[8], face[9]],
                [(face[10] + face[12]) / 2, (face[11] + face[13]) / 2],
            ],
            dtype=np.float32,
        )
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        ok, marks = self._lbf.fit(gray, np.array([box], dtype=np.float32))
        if not ok or not marks:
            return None, None
        points = np.asarray(marks[0]).reshape(-1, 2)

        lbf_anchors = np.array(
            [
                points[36:42].mean(axis=0),
                points[42:48].mean(axis=0),
                points[30],
                points[48:60].mean(axis=0),
            ],
            dtype=np.float32,
        )
        transform, _ = cv2.estimateAffinePartial2D(
            lbf_anchors.reshape(-1, 1, 2),
            anchors.reshape(-1, 1, 2),
            method=cv2.LMEDS,
        )
        if transform is not None:
            points = cv2.transform(points.reshape(-1, 1, 2), transform).reshape(-1, 2)
        return points, box

    def landmarks(self, image_bgr, face_box=None):
        self.last_yaw = None
        points = self._mediapipe_landmarks(image_bgr)
        if points is not None:
            return points
        points, _ = self._lbf_landmarks(image_bgr)
        return points
