import base64

import cv2
import numpy as np

from app.core.coloring.dye import apply_dye, hex_to_hsv
from app.core.compositing.beard import apply_beard as render_beard
from app.core.compositing.beard import apply_real_beard, load_templates
from app.core.compositing.haircut import STYLES as HAIRCUT_STYLES
from app.core.compositing.haircut import apply_haircut
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
        self._live_crop = None
        self._transfer_face = None

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

    def transfer_hair_mask(self, image_bgr, face):
        mask = self.hair_mask(image_bgr, face)
        x, y, width, height = [int(value) for value in face]
        face_region = np.zeros(mask.shape, np.uint8)
        center = (x + width // 2, y + int(height * 0.54))
        axes = (max(1, int(width * 0.46)), max(1, int(height * 0.56)))
        cv2.ellipse(face_region, center, axes, 0, 0, 360, 255, -1)
        return cv2.bitwise_and(mask, cv2.bitwise_not(face_region))

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
        hair_mask = self.transfer_hair_mask(image_bgr, face)
        return apply_haircut(
            image_bgr, hair_mask, face, points, style, strength,
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

    def transfer_scan(self, image_bgr):
        pose, face = self.detector.pose(image_bgr)
        if face is not None:
            self._transfer_face = face
        elif self._transfer_face is not None:
            face = self._transfer_face
        else:
            h, w = image_bgr.shape[:2]
            size = int(min(w, h) * 0.32)
            face = (w // 2 - size // 2, h // 2 - size // 2, size, size)
        hair_mask = self.hair_mask(image_bgr, face)
        canvas = image_bgr.copy()
        selected = hair_mask > 0
        green = np.full_like(canvas, (78, 205, 68))
        canvas[selected] = cv2.addWeighted(canvas[selected], 0.36, green[selected], 0.64, 0)
        points = self._landmarks(image_bgr, face) if pose == "front" else None
        if points is not None:
            triangles = delaunay_triangles(points)
            canvas = draw_mesh(canvas, points, triangles, color=(80, 220, 255))
        _, _, yaw = self.transfer_pose(image_bgr)
        return canvas, pose, yaw

    def transfer_asset(self, image_bgr):
        _, face = self.detector.pose(image_bgr)
        if face is not None:
            self._transfer_face = face
        elif self._transfer_face is not None:
            face = self._transfer_face
        else:
            h, w = image_bgr.shape[:2]
            size = int(min(w, h) * 0.32)
            face = (w // 2 - size // 2, h // 2 - size // 2, size, size)
        mask = self.transfer_hair_mask(image_bgr, face)
        rows, cols = np.where(mask > 0)
        if len(rows) == 0:
            return None
        pad = max(12, int(face[2] * 0.12))
        y0, y1 = max(0, rows.min() - pad), min(image_bgr.shape[0], rows.max() + pad + 1)
        x0, x1 = max(0, cols.min() - pad), min(image_bgr.shape[1], cols.max() + pad + 1)
        alpha = cv2.GaussianBlur(mask[y0:y1, x0:x1], (0, 0), 2)
        asset = np.dstack((image_bgr[y0:y1, x0:x1], alpha))
        return asset

    def transfer_pose(self, image_bgr):
        pose, face = self.detector.pose(image_bgr)
        yaw = None
        if face is not None:
            points = self._landmarks(image_bgr, face)
            if points is not None and len(points) >= 48:
                left_eye = points[36:42].mean(axis=0)
                right_eye = points[42:48].mean(axis=0)
                nose = points[30]
                left_distance = np.linalg.norm(nose - left_eye)
                right_distance = np.linalg.norm(nose - right_eye)
                total = left_distance + right_distance
                if total > 1:
                    yaw = float(np.clip((left_distance - right_distance) / total * 115, -75, 75))
        if yaw is None:
            yaw = {"left": -82.0, "right": 82.0, "front": 0.0}.get(pose, 0.0)
        return pose, face, yaw

    def reconstruct_transfer_mesh(self, images_bgr, angles):
        masks = []
        colors = []
        textures = []
        views = []
        valid_angles = []
        for image_bgr, angle in zip(images_bgr, angles):
            _, face = self.detector.pose(image_bgr)
            if face is not None:
                self._transfer_face = face
            elif self._transfer_face is not None:
                face = self._transfer_face
            else:
                h, w = image_bgr.shape[:2]
                size = int(min(w, h) * 0.32)
                face = (w // 2 - size // 2, h // 2 - size // 2, size, size)
            mask = self.transfer_hair_mask(image_bgr, face)
            rows, cols = np.where(mask > 0)
            if len(rows) < 100:
                continue
            pad = max(8, int(face[2] * 0.08))
            y0, y1 = max(0, rows.min() - pad), min(mask.shape[0], rows.max() + pad + 1)
            x0, x1 = max(0, cols.min() - pad), min(mask.shape[1], cols.max() + pad + 1)
            crop = mask[y0:y1, x0:x1]
            normalized = cv2.GaussianBlur(crop, (0, 0), 1.2)
            normalized = cv2.resize(normalized, (96, 128), interpolation=cv2.INTER_AREA)
            masks.append(normalized > 127)
            textures.append(cv2.resize(image_bgr[y0:y1, x0:x1], (96, 128), interpolation=cv2.INTER_LINEAR))
            valid_angles.append(angle)
            rgba = cv2.cvtColor(image_bgr[y0:y1, x0:x1], cv2.COLOR_BGR2BGRA)
            rgba[:, :, 3] = cv2.GaussianBlur(crop, (0, 0), 1.5)
            success, encoded = cv2.imencode(".png", rgba)
            if success:
                views.append({
                    "angle": float(angle),
                    "image": "data:image/png;base64," + base64.b64encode(encoded.tobytes()).decode("ascii"),
                    "faceCenter": [
                        (face[0] + face[2] / 2 - x0) / face[2],
                        (face[1] + face[3] / 2 - y0) / face[3],
                    ],
                    "faceSize": [
                        (x1 - x0) / face[2],
                        (y1 - y0) / face[3],
                    ],
                })
            pixels = image_bgr[mask > 0]
            if len(pixels):
                colors.append(np.median(pixels, axis=0))
        if len(masks) < 3:
            raise ValueError("At least three valid hair silhouettes are required")

        view_index = int(np.argmin(np.abs(np.asarray(valid_angles))))
        silhouette = masks[view_index]
        grid_w, grid_h = 64, 88
        sampled = cv2.resize(silhouette.astype(np.uint8), (grid_w, grid_h), interpolation=cv2.INTER_AREA) > 0
        texture = cv2.resize(textures[view_index], (grid_w, grid_h), interpolation=cv2.INTER_LINEAR)
        vertices = []
        vertex_colors = []
        faces = []
        index = {}
        for iy in range(grid_h):
            for ix in range(grid_w):
                if not sampled[iy, ix]:
                    continue
                x = ix / (grid_w - 1) * 2 - 1
                y = iy / (grid_h - 1) * 2.3 - 1.15
                scalp = max(0.0, 1.0 - (x / 1.05) ** 2) * max(0.0, 1.0 - ((y + 0.42) / 1.22) ** 2)
                depth = 0.025 + 0.24 * scalp
                pixel = texture[iy, ix]
                rgb = [int(pixel[2]), int(pixel[1]), int(pixel[0])]
                index[(ix, iy, 1)] = len(vertices)
                vertices.append([x, y, depth])
                vertex_colors.append(rgb)
                index[(ix, iy, -1)] = len(vertices)
                vertices.append([x, y, -depth * 0.35])
                vertex_colors.append([int(value * 0.72) for value in rgb])
        for iy in range(grid_h - 1):
            for ix in range(grid_w - 1):
                corners = [(ix, iy), (ix + 1, iy), (ix + 1, iy + 1), (ix, iy + 1)]
                if not all(sampled[y, x] for x, y in corners):
                    continue
                front = [index[(x, y, 1)] for x, y in corners]
                back = [index[(x, y, -1)] for x, y in corners]
                faces.extend([[front[0], front[1], front[2]], [front[0], front[2], front[3]]])
                faces.extend([[back[2], back[1], back[0]], [back[3], back[2], back[0]]])
        for iy in range(grid_h):
            for ix in range(grid_w):
                if not sampled[iy, ix]:
                    continue
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nx_i, ny_i = ix + dx, iy + dy
                    if 0 <= nx_i < grid_w and 0 <= ny_i < grid_h and sampled[ny_i, nx_i]:
                        continue
                    x1, y1 = ix, iy
                    x2, y2 = (ix, iy + 1) if dx else (ix + 1, iy)
                    if (x2, y2, 1) not in index:
                        continue
                    a, b = index[(x1, y1, 1)], index[(x2, y2, 1)]
                    c, d = index[(x2, y2, -1)], index[(x1, y1, -1)]
                    faces.extend([[a, b, c], [a, c, d]])
        if len(faces) < 30:
            raise ValueError("The hair silhouette is too small. Keep your full hairstyle inside the guide.")
        color = np.median(np.asarray(colors), axis=0).astype(np.uint8) if colors else np.array([50, 50, 50], dtype=np.uint8)
        return {
            "vertices": vertices,
            "vertexColors": vertex_colors,
            "faces": faces,
            "color": [int(color[2]), int(color[1]), int(color[0])],
            "silhouettes": len(masks),
            "views": views,
        }
