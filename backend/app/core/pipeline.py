from app.core.coloring.dye import apply_dye, hex_to_hsv
from app.core.compositing.beard import apply_beard as render_beard
from app.core.compositing.beard import apply_real_beard, load_templates
from app.core.detection.face_detector import FaceDetector
from app.core.detection.landmarks import LandmarkDetector
from app.core.geometry.delaunay import delaunay_triangles, draw_mesh
from app.core.segmentation.hair_region import provisional_hair_mask
from app.core.segmentation.mask_refiner import refine_hair_mask

try:
    from app.core.segmentation.yolo_segmenter import HairSegmenter
except ImportError:
    HairSegmenter = None


class StylePipeline:
    def __init__(self):
        self.detector = FaceDetector()
        self.segmenter = self._load_segmenter()
        self.landmark_detector = None
        self.beard_templates = load_templates()

    @staticmethod
    def _load_segmenter():
        if HairSegmenter is None:
            return None
        try:
            return HairSegmenter()
        except FileNotFoundError:
            return None

    def _landmarks(self, image_bgr, face):
        if self.landmark_detector is None:
            try:
                self.landmark_detector = LandmarkDetector()
            except FileNotFoundError:
                return None
        return self.landmark_detector.landmarks(image_bgr, face)

    def hair_mask(self, image_bgr, face):
        if self.segmenter is not None:
            mask = self.segmenter.hair_mask(image_bgr)
            if mask is not None and (mask > 0).any():
                return refine_hair_mask(image_bgr, mask)
        return provisional_hair_mask(image_bgr, face)

    def apply_hair_dye(self, image_bgr, hex_color, strength=0.75):
        target_hsv = hex_to_hsv(hex_color)
        face = self.detector.largest_face(image_bgr)
        if face is None:
            return None
        mask = self.hair_mask(image_bgr, face)
        return apply_dye(image_bgr, mask, target_hsv, strength)

    def apply_beard(self, image_bgr, style="full", strength=0.9):
        face = self.detector.largest_face(image_bgr)
        if face is None:
            return None
        points = self._landmarks(image_bgr, face)
        if points is None:
            return None
        hair_yccrb = None
        if self.beard_templates:
            try:
                hair_mask = self.hair_mask(image_bgr, face)
                hair_pixels = image_bgr[hair_mask > 0]
                if len(hair_pixels) > 200:
                    hair_bgr = np.median(hair_pixels, axis=0)
                    hair_yccrb = cv2.cvtColor(
                        hair_bgr.reshape(1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2YCrCb
                    )[0, 0].astype(np.float32)
                return apply_real_beard(
                    image_bgr, points, style, strength, self.beard_templates,
                    hair_yccrb=hair_yccrb,
                )
            except Exception:
                pass
        return render_beard(image_bgr, points, style, strength)

    def face_mesh(self, image_bgr):
        face = self.detector.largest_face(image_bgr)
        if face is None:
            return None
        points = self._landmarks(image_bgr, face)
        if points is None:
            return None
        triangles = delaunay_triangles(points)
        return draw_mesh(image_bgr, points, triangles)
