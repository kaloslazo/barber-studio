import threading
from pathlib import Path

import cv2
import numpy as np

MODELS_DIR = Path(__file__).resolve().parents[3] / "models"

BACKGROUND, HAIR, BODY_SKIN, FACE_SKIN, CLOTHES, OTHERS = range(6)


class MultiClassSegmenter:
    """MediaPipe selfie multiclass model: per-pixel probabilities for
    background, hair, body skin, face skin, clothes and accessories.

    Unlike a dark-pixel threshold it is trained to tell hair from a dark
    background, so the transfer mask stops leaking into the scene.
    """

    def __init__(self, model="selfie_multiclass_256x256.tflite"):
        path = MODELS_DIR / model
        if not path.exists():
            raise FileNotFoundError(f"Segmentation model not found: {path}")
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp
        options = vision.ImageSegmenterOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(path)),
            running_mode=vision.RunningMode.IMAGE,
            output_confidence_masks=True,
            output_category_mask=False,
        )
        self._segmenter = vision.ImageSegmenter.create_from_options(options)
        self._lock = threading.Lock()

    def probabilities(self, image_bgr, box=None):
        """(6, H, W) float32 class probabilities at the image resolution.

        With `box` (x0, y0, x1, y1) only that window is segmented, at the
        model's native 256 px, and everything outside counts as background."""
        h, w = image_bgr.shape[:2]
        if box is not None:
            x0, y0, x1, y1 = box
            inner = self.probabilities(image_bgr[y0:y1, x0:x1])
            if inner is None:
                return None
            full = np.zeros((inner.shape[0], h, w), np.float32)
            full[BACKGROUND] = 1.0
            full[:, y0:y1, x0:x1] = inner
            return full
        small = cv2.resize(image_bgr, (256, 256), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        with self._lock:
            result = self._segmenter.segment(self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb))
        if not result.confidence_masks:
            return None
        layers = []
        for mask in result.confidence_masks:
            layer = np.asarray(mask.numpy_view(), np.float32)
            if layer.ndim == 3:
                layer = layer[..., 0]
            if layer.shape != (h, w):
                layer = cv2.resize(layer, (w, h), interpolation=cv2.INTER_LINEAR)
            layers.append(layer)
        return np.stack(layers)
