from app.core.coloring.dye import apply_dye, hex_to_hsv
from app.core.detection.face_detector import FaceDetector
from app.core.segmentation.hair_region import provisional_hair_mask


class StylePipeline:
    def __init__(self):
        self.detector = FaceDetector()

    def apply_hair_dye(self, image_bgr, hex_color, strength=0.75):
        target_hsv = hex_to_hsv(hex_color)
        face = self.detector.largest_face(image_bgr)
        if face is None:
            return None
        mask = provisional_hair_mask(image_bgr, face)
        return apply_dye(image_bgr, mask, target_hsv, strength)
