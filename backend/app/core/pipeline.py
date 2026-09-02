from app.core.coloring.dye import apply_dye, hex_to_hsv
from app.core.compositing.beard import apply_beard as render_beard
from app.core.compositing.beard import apply_real_beard, load_templates
from app.core.compositing.haircut import STYLES as HAIRCUT_STYLES
from app.core.compositing.haircut import apply_haircut, load_hair_templates
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
        self.hair_templates = load_hair_templates()
        self._live_crop = None

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

    def apply_haircut(self, image_bgr, style="low-fade", strength=0.9):
        face = self.detector.largest_face(image_bgr)
        if face is None:
            return None
        points = self._landmarks(image_bgr, face)
        hair_mask = self.hair_mask(image_bgr, face)
        return apply_haircut(
            image_bgr, hair_mask, face, points, style, strength,
            templates=self.hair_templates,
        )

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

    def face_mesh(self, image_bgr, crop=False):
        face = self.detector.largest_face(image_bgr)
        if face is None:
            self._live_crop = None
            return None
        points = self._landmarks(image_bgr, face)
        if points is None:
            return None
        triangles = delaunay_triangles(points)
        canvas = draw_mesh(image_bgr, points, triangles)
        if crop:
            h, w = image_bgr.shape[:2]
            x, y, fw, fh = face
            mx = int(fw * 0.7)
            x0 = float(max(0, x - mx))
            y0 = float(max(0, y - fh * 0.5))
            x1 = float(min(w, x + fw + mx))
            y1 = float(min(h, y + fh + fh * 0.7))
            cw, ch = x1 - x0, y1 - y0
            if cw > ch:
                pad = (cw - ch) / 2
                y0 = max(0.0, y0 - pad)
                y1 = min(float(h), y1 + pad)
            else:
                pad = (ch - cw) / 2
                x0 = max(0.0, x0 - pad)
                x1 = min(float(w), x1 + pad)

            previous = self._live_crop
            if previous is not None:
                jump = abs((x0 + x1) / 2 - (previous[0] + previous[2]) / 2)
                if jump < fw * 1.5:
                    alpha = 0.25
                    x0 = previous[0] * (1 - alpha) + x0 * alpha
                    y0 = previous[1] * (1 - alpha) + y0 * alpha
                    x1 = previous[2] * (1 - alpha) + x1 * alpha
                    y1 = previous[3] * (1 - alpha) + y1 * alpha
            self._live_crop = (x0, y0, x1, y1)
            canvas = canvas[int(y0):int(y1), int(x0):int(x1)]
        return canvas
