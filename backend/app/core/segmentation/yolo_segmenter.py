from pathlib import Path

import cv2
import numpy as np

MODELS_DIR = Path(__file__).resolve().parents[3] / "models"


class HairSegmenter:
    def __init__(self, weights="hair_best.pt", conf=0.5):
        path = MODELS_DIR / weights
        if not path.exists():
            raise FileNotFoundError(f"Weights not found: {path}")
        from ultralytics import YOLO

        self.model = YOLO(str(path))
        self.conf = conf

    def hair_mask(self, image_bgr):
        """Full-resolution binary mask (0/255) of every hair region detected."""
        results = self.model.predict(image_bgr, conf=self.conf, verbose=False)
        if not results or results[0].masks is None:
            return None
        h, w = image_bgr.shape[:2]
        mask = np.zeros((h, w), np.uint8)
        for polygon in results[0].masks.xyn:
            points = (np.array(polygon) * [w, h]).astype(np.int32)
            cv2.fillPoly(mask, [points], 255)
        return mask
