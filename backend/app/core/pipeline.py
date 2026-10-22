import base64
import threading
import time
from collections import OrderedDict

import cv2
import numpy as np

from app.core.coloring.dye import apply_dye, hex_to_hsv
from app.core.compositing.beard import apply_beard as render_beard
from app.core.compositing.beard import LiveAnchor, apply_real_beard, beard_mask, load_templates
from app.core.compositing.beard_physics import BeardPhysics
from app.core.detection.hands import FingerTracker, draw_hand
from app.core.game.speedrun import SpeedrunGame
from app.core.compositing.haircut import STYLES as HAIRCUT_STYLES
from app.core.compositing.haircut import apply_haircut
from app.core.detection.face_detector import FaceDetector
from app.core.detection.landmarks import LandmarkDetector
from app.core.detection.one_euro import OneEuroFilter
from app.core.geometry.delaunay import delaunay_triangles, draw_mesh
from app.core.segmentation.hair_region import provisional_hair_mask
from app.core.segmentation.mask_refiner import refine_hair_mask
from app.core.segmentation.transfer_mask import head_geometry, head_window, transfer_mask
from app.core.splatting.gaussian_image import draw_ellipses, fit_gaussians, render_gaussians
from app.core.splatting.face3d import FaceView, face_splats, scan_face
from app.core.splatting.hair3d import HairView, build_hair_splats
from app.core.splatting.head3d import build_head_splats

try:
    from app.core.segmentation.yolo_segmenter import HairSegmenter
except ImportError:
    HairSegmenter = None

try:
    from app.core.segmentation.mp_segmenter import FACE_SKIN, HAIR, MultiClassSegmenter
except ImportError:
    MultiClassSegmenter = None


class StylePipeline:
    def __init__(self):
        self.detector = FaceDetector()
        self.segmenter = self._load_segmenter()
        self.landmark_detector = None
        self.live_landmark_detector = None
        self._live_hair_color = None
        self._live_anchor = None
        self._physics = None
        self._live_last_points = None
        self._live_misses = 0
        self._live_last_gray = None
        self.game = None
        self.finger_tracker = FingerTracker()
        self._physics_clock = None
        self.beard_templates = load_templates()
        self._live_crop = None
        self._transfer_face = None
        self.part_segmenter = None
        self._part_segmenter_failed = False
        self._tryon_filters = None
        self._tryon_width = None
        self._hair_views = OrderedDict()
        self._face_scans = OrderedDict()
        self._vision_lock = threading.RLock()

    @staticmethod
    def _load_segmenter():
        if HairSegmenter is None:
            return None
        try:
            return HairSegmenter()
        except FileNotFoundError:
            return None

    def _landmarks(self, image_bgr, face, live=False):
        if live:
            if self.live_landmark_detector is None:
                try:
                    self.live_landmark_detector = LandmarkDetector(live=True)
                except FileNotFoundError:
                    return None
            return self.live_landmark_detector.landmarks(image_bgr, face)
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

    def _part_probabilities(self, image_bgr, geometry=None):
        if self._part_segmenter_failed or MultiClassSegmenter is None:
            return None
        if self.part_segmenter is None:
            try:
                self.part_segmenter = MultiClassSegmenter()
            except (FileNotFoundError, ImportError, RuntimeError):
                self._part_segmenter_failed = True
                return None
        box = head_window(image_bgr.shape[:2], geometry) if geometry is not None else None
        return self.part_segmenter.probabilities(image_bgr, box)

    def _head_geometry(self, points, face, live=False):
        detector = self.live_landmark_detector if live else self.landmark_detector
        width = detector.last_head_width if points is not None and detector is not None else None
        return head_geometry(points, face, width)

    def transfer_hair_mask(self, image_bgr, face, points=None, probabilities=None, soft=False, face_visible=True, geometry=None):
        geometry = dict(geometry) if geometry is not None else self._head_geometry(points, face)
        geometry["face_visible"] = face_visible
        if probabilities is None:
            probabilities = self._part_probabilities(image_bgr, geometry)
        fallback = None if probabilities is not None else self.hair_mask(image_bgr, face)
        mask, alpha = transfer_mask(image_bgr, geometry, probabilities, fallback)
        return (mask, alpha) if soft else mask

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
        hair_mask = self.transfer_hair_mask(image_bgr, face, points)
        return apply_haircut(
            image_bgr, hair_mask, face, points, style, strength,
        )

    def _live_points(self, image_bgr):
        points = self._landmarks(image_bgr, None, live=True)
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        if points is None and self._live_last_points is not None and self._live_misses < 3:
            self._live_misses += 1
            points = self._live_last_points + self._face_shift(self._live_last_gray, gray, self._live_last_points)
            self._live_last_points = points
        elif points is not None:
            self._live_misses = 0
            self._live_last_points = points
        else:
            self._live_last_points = None
        self._live_last_gray = gray
        return points

    @staticmethod
    def _face_shift(previous, current, points):
        if previous is None or previous.shape != current.shape:
            return np.zeros(2, np.float32)
        h, w = current.shape
        x0, y0 = np.floor(points.min(axis=0)).astype(int)
        x1, y1 = np.ceil(points.max(axis=0)).astype(int)
        pad_x, pad_y = (x1 - x0) // 2, (y1 - y0) // 2
        x0, y0 = max(0, x0 - pad_x), max(0, y0 - pad_y)
        x1, y1 = min(w, x1 + pad_x), min(h, y1 + pad_y)
        if x1 - x0 < 16 or y1 - y0 < 16:
            return np.zeros(2, np.float32)
        window = cv2.createHanningWindow((x1 - x0, y1 - y0), cv2.CV_32F)
        (dx, dy), response = cv2.phaseCorrelate(previous[y0:y1, x0:x1], current[y0:y1, x0:x1], window)
        if response < 0.05:
            return np.zeros(2, np.float32)
        return np.array([dx, dy], np.float32)

    @staticmethod
    def _box_from_landmarks(points):
        x0, x1 = float(points[:, 0].min()), float(points[:, 0].max())
        brow = float(points[17:27, 1].min())
        chin = float(points[8, 1])
        top = brow - 0.2 * (chin - brow)
        return int(x0), int(top), max(1, int(x1 - x0)), max(1, int(chin - top))

    def apply_beard(self, image_bgr, style="full", strength=0.9, live=False, detail=True):
        if live:
            points = self._live_points(image_bgr)
            if points is None:
                self._live_anchor = None
                return None
            face = self._box_from_landmarks(points)
        else:
            face = self.detector.largest_face(image_bgr)
            if face is None:
                return None
            points = self._landmarks(image_bgr, face)
            if points is None:
                return None
        anchor = None
        if live:
            current = self._live_anchor
            if (
                current is None
                or current.stale
                or current.style != style
                or current.shape != image_bgr.shape[:2]
            ):
                current = LiveAnchor(points, image_bgr.shape[:2], style)
                self._live_anchor = current
            anchor = current
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
                    hair_yccrb[1] = max(hair_yccrb[1], 136.0)
                    hair_yccrb[2] = min(hair_yccrb[2], 121.0)
                if live and hair_yccrb is not None:
                    if self._live_hair_color is not None:
                        hair_yccrb = 0.9 * self._live_hair_color + 0.1 * hair_yccrb
                    self._live_hair_color = hair_yccrb
                return apply_real_beard(
                    image_bgr, points, style, strength, self.beard_templates,
                    hair_yccrb=hair_yccrb, anchor=anchor, live_detail=detail,
                )
            except Exception:
                pass
        return render_beard(image_bgr, points, style, strength)

    def _live_tint(self):
        if self._live_hair_color is None:
            return np.array([45, 37, 30], np.float32)
        ycc = self._live_hair_color.copy()
        ycc[0] *= 0.8
        bgr = cv2.cvtColor(np.clip(ycc, 0, 255).astype(np.uint8).reshape(1, 1, 3), cv2.COLOR_YCrCb2BGR)
        return bgr[0, 0].astype(np.float32)

    def start_game(self, target):
        self.game = SpeedrunGame(target)

    def game_frame(self, image_bgr, pointer=None, use_hand=True, now=None, pointer_down=True):
        if self.game is None:
            self.game = SpeedrunGame()
        now = time.monotonic() if now is None else now
        points = self._live_points(image_bgr)
        if points is not None and self._live_hair_color is None:
            face = self._box_from_landmarks(points)
            hair_mask = self.hair_mask(image_bgr, face)
            pixels = image_bgr[hair_mask > 0]
            if len(pixels) > 200:
                ycc = cv2.cvtColor(np.median(pixels, axis=0).reshape(1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2YCrCb)[0, 0]
                ycc = ycc.astype(np.float32)
                ycc[1] = max(ycc[1], 136.0)
                ycc[2] = min(ycc[2], 121.0)
                self._live_hair_color = ycc
        tool, tool_on, source = None, False, "none"
        if use_hand:
            tip = self.finger_tracker.fingertip(image_bgr)
            if tip is not None:
                tool, tool_on, source = tip[0], tip[1], "hand"
        if tool is None and pointer is not None:
            tool, tool_on, source = np.asarray(pointer, np.float32), bool(pointer_down), "pointer"
        bearded = None
        if points is not None and self.beard_templates:
            hair = self._live_hair_estimate(image_bgr, self._box_from_landmarks(points))
            anchor = getattr(self, "_game_anchor", None)
            if anchor is None or anchor.stale or anchor.shape != image_bgr.shape[:2] or self.game.physics is None:
                anchor = LiveAnchor(points, image_bgr.shape[:2], "full")
                self._game_anchor = anchor
            try:
                bearded = apply_real_beard(
                    image_bgr, points, "full", 0.9, self.beard_templates,
                    hair_yccrb=hair, anchor=anchor,
                )
            except Exception:
                bearded = None
        out, found = self.game.frame(image_bgr, points, tool, tool_on, now, self._live_tint(), bearded=bearded)
        if source == "hand" and self.finger_tracker.last_hand is not None:
            draw_hand(out, self.finger_tracker.last_hand, tool_on)
        stats = self.game.stats()
        stats["face"] = bool(found)
        stats["tool"] = source
        stats["target"] = self.game.target
        return out, stats

    def _live_hair_estimate(self, image_bgr, face):
        hair_mask = self.hair_mask(image_bgr, face)
        pixels = image_bgr[hair_mask > 0]
        if len(pixels) > 200:
            ycc = cv2.cvtColor(
                np.median(pixels, axis=0).reshape(1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2YCrCb,
            )[0, 0].astype(np.float32)
            ycc[1] = max(ycc[1], 136.0)
            ycc[2] = min(ycc[2], 121.0)
            if self._live_hair_color is not None:
                ycc = 0.9 * self._live_hair_color + 0.1 * ycc
            self._live_hair_color = ycc
        return self._live_hair_color

    def apply_beard_live_hd(self, image_bgr, style="full", strength=0.9, work_width=640):
        """Live beard rendered at the camera's full resolution, but only inside
        a fixed-size crop around the face. Landmarks run on a small copy (fast);
        the beard is painted on the high-resolution crop (sharp hair, like photo
        mode). The crop keeps a constant size so the face-anchored textures
        (no jitter) survive while the crop window follows the face."""
        h, w = image_bgr.shape[:2]
        scale = min(1.0, work_width / w)
        small = cv2.resize(image_bgr, (int(round(w * scale)), int(round(h * scale))), interpolation=cv2.INTER_AREA) if scale < 1 else image_bgr
        points = self._live_points(small)
        if points is None:
            self._live_anchor = None
            return None
        hair = self._live_hair_estimate(small, self._box_from_landmarks(points))
        pts = points / scale
        face_w = float(np.linalg.norm(pts[16] - pts[0]))
        wanted = (int(min(w, face_w * 1.45)) // 8 * 8, int(min(h, face_w * 1.35)) // 8 * 8)
        size = getattr(self, "_hd_size", None)
        if size is None or abs(wanted[0] - size[0]) > 0.25 * size[0] or size[0] > w or size[1] > h:
            size = wanted
            self._hd_size = size
            self._live_anchor = None
        cw, ch = size
        cx = float(0.5 * (pts[0, 0] + pts[16, 0]))
        top = float(min(pts[0, 1], pts[16, 1], pts[29, 1])) - 0.08 * face_w
        x0 = int(np.clip(cx - cw / 2, 0, w - cw))
        y0 = int(np.clip(top, 0, h - ch))
        crop = image_bgr[y0:y0 + ch, x0:x0 + cw]
        local = (pts - np.array([x0, y0], np.float32)).astype(np.float32)
        current = self._live_anchor
        if current is None or current.stale or current.style != style or current.shape != (ch, cw):
            current = LiveAnchor(local, (ch, cw), style)
            self._live_anchor = current
        try:
            painted = apply_real_beard(
                crop, local, style, strength, self.beard_templates,
                hair_yccrb=hair, anchor=current,
            )
        except Exception:
            painted = None
        if painted is None:
            painted = render_beard(crop, local, style, strength)
        result = image_bgr.copy()
        result[y0:y0 + ch, x0:x0 + cw] = painted
        return result

    def apply_beard_physics(self, image_bgr, strength=0.9, now=None, length=1.0):
        base = self.apply_beard(image_bgr, "full", strength, live=True, detail=False)
        anchor = self._live_anchor
        if base is None or anchor is None or getattr(anchor, "cur_ext", None) is None:
            self._physics = None
            return base
        points = anchor.cur_ext[:68]
        face_w = float(np.linalg.norm(points[16] - points[0]))
        now = time.monotonic() if now is None else now
        physics = self._physics
        if physics is None or physics[0] is not anchor or abs(physics[1].length_scale - length) > 1e-3:
            region = beard_mask(image_bgr.shape, points, "full")
            hull = np.zeros(region.shape, np.uint8)
            cv2.fillConvexPoly(hull, cv2.convexHull(points).astype(np.int32), 255)
            region = cv2.bitwise_and(region, hull)
            if not (region > 0).any():
                return base
            self._physics = (anchor, BeardPhysics(anchor, region, points, face_w, length_scale=length))
            self._physics_clock = now
        simulation = self._physics[1]
        dt = now - (self._physics_clock if self._physics_clock is not None else now)
        self._physics_clock = now
        simulation.step(anchor, dt)
        tint = self._live_tint()
        strand_rgb, strand_alpha = simulation.render(image_bgr.shape[:2], tint, strength)
        out = base.astype(np.float32)
        alpha = strand_alpha[..., None] * 0.85
        out = out * (1.0 - alpha) + strand_rgb * alpha
        return np.clip(out, 0, 255).astype(np.uint8)

    def head3d(self, image_bgr, beard_style=None):
        h, w = image_bgr.shape[:2]
        if w > 1024:
            image_bgr = cv2.resize(image_bgr, (1024, int(round(h * 1024 / w))), interpolation=cv2.INTER_AREA)
        if self.landmark_detector is None:
            self.landmark_detector = LandmarkDetector()
        mesh = self.landmark_detector.mesh3d(image_bgr)
        if mesh is None:
            return None, None
        textured, region, tint = image_bgr, None, (0.16, 0.13, 0.11)
        if beard_style:
            bearded = self.apply_beard(image_bgr, beard_style, 0.9)
            points = self.landmark_detector.landmarks(image_bgr)
            if bearded is not None and points is not None:
                textured = bearded
                region = beard_mask(image_bgr.shape, points, beard_style)
                pixels = bearded[region > 0]
                if len(pixels) > 50:
                    tint = tuple(float(v) for v in np.median(pixels, axis=0)[::-1] / 255.0 * 0.8)
        return build_head_splats(textured, mesh, region, beard_style, tint)

    def _face_crop(self, image_bgr):
        face = self.detector.largest_face(image_bgr)
        if face is None:
            return image_bgr
        h, w = image_bgr.shape[:2]
        x, y, fw, fh = face
        side = int(max(fw, fh) * 1.9)
        cx, cy = x + fw / 2, y + fh * 0.58
        x0 = int(np.clip(cx - side / 2, 0, max(0, w - side)))
        y0 = int(np.clip(cy - side / 2, 0, max(0, h - side)))
        return image_bgr[y0:y0 + side, x0:x0 + side]

    def gaussian_portrait(self, image_bgr, count, face_crop=True, beard_style=None, out_width=480):
        source = image_bgr
        if beard_style:
            bearded = self.apply_beard(source, beard_style, 0.9)
            if bearded is not None:
                source = bearded
        if face_crop:
            source = self._face_crop(source)
        params = fit_gaussians(source, count)
        return {
            "render": render_gaussians(params, out_width),
            "ellipses": draw_ellipses(params, out_width),
            "target": cv2.resize(source, (out_width, int(round(out_width * source.shape[0] / source.shape[1])))),
            "psnr": params["psnr"],
            "seconds": params["seconds"],
            "iterations": params["iterations"],
        }

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

    def _transfer_head(self, image_bgr):
        pose, face = self.detector.pose(image_bgr)
        points = self._landmarks(image_bgr, face)
        if points is not None:
            face = self._box_from_landmarks(points)
            pose = "front" if pose == "unknown" else pose
        visible = face is not None
        if face is not None:
            self._transfer_face = face
        elif self._transfer_face is not None:
            face = self._transfer_face
        else:
            h, w = image_bgr.shape[:2]
            size = int(min(w, h) * 0.32)
            face = (w // 2 - size // 2, h // 2 - size // 2, size, size)
        return pose, face, points, visible

    def _scan_yaw(self, points, pose):
        """Like _yaw, but once the face disappears after a clear turn (the
        back of the head is towards the camera) the turn is taken as a full
        profile on the same side instead of dropping back to 0."""
        now = time.monotonic()
        yaw = self._yaw(points, pose)
        if points is not None or pose in ("left", "right"):
            self._scan_turn = (yaw, now)
            return pose, yaw
        last = getattr(self, "_scan_turn", None)
        if last is not None and abs(last[0]) >= 40 and now - last[1] < 3.0:
            return ("left" if last[0] < 0 else "right"), float(np.sign(last[0]) * 90.0)
        return pose, yaw

    def _yaw(self, points, pose, live=False):
        """Head yaw in real degrees from MediaPipe's head pose (negative when
        the face turns to the image left); full profiles, where the face mesh
        is lost, fall back to the profile cascade."""
        detector = self.live_landmark_detector if live else self.landmark_detector
        if points is not None and detector is not None and detector.last_yaw is not None:
            return detector.last_yaw
        return {"left": -82.0, "right": 82.0, "front": 0.0}.get(pose, 0.0)

    @staticmethod
    def _remember(cache, key, value, size):
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > size:
            cache.popitem(last=False)

    def _hair_view(self, image_bgr, key=None):
        """Everything the peluca needs from one capture: hair alpha, face
        mask, head geometry and the measured yaw (None when the face mesh is
        lost). Live scan frames are analysed once and kept by `key`, so
        building the peluca afterwards does not segment them again."""
        with self._vision_lock:
            return self._analyse_hair(image_bgr, key)

    def _analyse_hair(self, image_bgr, key):
        if key is not None and key in self._hair_views:
            self._hair_views.move_to_end(key)
            return self._hair_views[key]
        h, w = image_bgr.shape[:2]
        if w > 900:
            image_bgr = cv2.resize(image_bgr, (900, int(round(h * 900 / w))), interpolation=cv2.INTER_AREA)
        pose, face, points, visible = self._transfer_head(image_bgr)
        measured = self._yaw(points, pose) if points is not None else None
        geometry = self._head_geometry(points, face)
        probabilities = self._part_probabilities(image_bgr, geometry)
        mask, alpha = self.transfer_hair_mask(image_bgr, face, points, probabilities, soft=True, face_visible=visible, geometry=geometry)
        face_mask = np.zeros(mask.shape, np.uint8)
        if visible:
            cv2.fillPoly(face_mask, [geometry["polygon"]], 255)
        if visible and probabilities is not None:
            grow = int(geometry["face_w"] * 0.3) | 1
            near = cv2.dilate(face_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (grow, grow)))
            face_mask[(probabilities[FACE_SKIN] > 0.5) & (near > 0)] = 255
        face_mask[mask > 0] = 0
        result = {
            "image": image_bgr, "mask": mask, "alpha": alpha, "face_mask": face_mask, "geometry": geometry,
            "points": points, "pose": pose, "yaw": measured,
        }
        if key is not None:
            self._remember(self._hair_views, key, result, 90)
        return result

    def transfer_scan(self, image_bgr, key=None):
        """Transparent overlay for the live scan preview: selected hair in
        green and, on frontal views, the landmark mesh."""
        analysed = self._hair_view(image_bgr, key)
        image_bgr, points, geometry = analysed["image"], analysed["points"], analysed["geometry"]
        overlay = np.zeros(image_bgr.shape[:2] + (4,), np.uint8)
        overlay[analysed["mask"] > 0] = (68, 205, 78, 165)
        pose = analysed["pose"]
        if points is not None and pose == "front":
            lines = draw_mesh(np.zeros_like(image_bgr), points, delaunay_triangles(points), color=(80, 220, 255))
            drawn = lines.any(axis=2)
            overlay[drawn, :3] = lines[drawn]
            overlay[drawn, 3] = 255
        pose, yaw = self._scan_yaw(points, pose)
        anchor = {
            "center": [float(geometry["center"][0]), float(geometry["center"][1])],
            "faceWidth": float(geometry["face_w"]),
            "roll": float(np.degrees(geometry["roll"])),
            "tracked": points is not None,
        }
        return overlay, pose, yaw, anchor

    def transfer_asset(self, image_bgr):
        _, face, points, visible = self._transfer_head(image_bgr)
        mask, alpha = self.transfer_hair_mask(image_bgr, face, points, soft=True, face_visible=visible)
        rows, cols = np.where(mask > 0)
        if len(rows) == 0:
            return None
        pad = max(12, int(face[2] * 0.12))
        y0, y1 = max(0, rows.min() - pad), min(image_bgr.shape[0], rows.max() + pad + 1)
        x0, x1 = max(0, cols.min() - pad), min(image_bgr.shape[1], cols.max() + pad + 1)
        alpha = (alpha[y0:y1, x0:x1] * 255).astype(np.uint8)
        return np.dstack((image_bgr[y0:y1, x0:x1], alpha))

    def _smooth_tryon(self, values, now):
        if self._tryon_filters is None:
            self._tryon_filters = [
                OneEuroFilter(min_cutoff=2.0, beta=0.05),
                OneEuroFilter(min_cutoff=0.6, beta=0.01),
                OneEuroFilter(min_cutoff=1.0, beta=0.05),
                OneEuroFilter(min_cutoff=0.7, beta=0.05),
            ]
        center, scale, roll, yaw = values
        return (
            self._tryon_filters[0](center, now),
            float(self._tryon_filters[1](scale, now)),
            float(self._tryon_filters[2](roll, now)),
            float(self._tryon_filters[3](yaw, now)),
        )

    def reset_tryon(self):
        self._tryon_filters = None
        self._tryon_width = None

    def transfer_tryon(self, image_bgr, now=None):
        """Smoothed head anchor for the peluca. The browser tracks the head
        itself and uses this only when its own tracker loses the face (full
        profiles)."""
        now = time.monotonic() if now is None else now
        points = self._landmarks(image_bgr, None, live=True)
        pose = "front"
        if points is None:
            pose, face = self.detector.pose(image_bgr)
            if face is None:
                return {"pose": "unknown"}
        else:
            face = self._box_from_landmarks(points)
        geometry = self._head_geometry(points, face, live=True)
        if points is not None:
            self._tryon_width = geometry["face_w"]
        elif self._tryon_width is not None:
            geometry = head_geometry(None, face, self._tryon_width)
        yaw = self._yaw(points, pose, live=True)
        center, scale, roll, yaw = self._smooth_tryon(
            (np.asarray(geometry["center"], np.float32), np.float32(geometry["face_w"]),
             np.float32(np.degrees(geometry["roll"])), np.float32(yaw)),
            now,
        )
        return {
            "pose": pose,
            "yaw": yaw,
            "roll": roll,
            "center": [float(center[0]), float(center[1])],
            "faceWidth": scale,
        }

    def face3d_views(self, images_bgr):
        if self.landmark_detector is None:
            self.landmark_detector = LandmarkDetector()
        views = []
        for image_bgr in images_bgr:
            h, w = image_bgr.shape[:2]
            if w > 1024:
                image_bgr = cv2.resize(image_bgr, (1024, int(round(h * 1024 / w))), interpolation=cv2.INTER_AREA)
            mesh = self.landmark_detector.mesh3d(image_bgr)
            if mesh is None:
                continue
            probabilities = self._part_probabilities(image_bgr)
            view = FaceView(image_bgr, mesh, None if probabilities is None else probabilities[HAIR])
            if abs(view.yaw) <= 75:
                views.append(view)
        return views

    def face_scan(self, images_bgr, key=None):
        """The slow part of "Use my face" (the 3D Mirror reconstruction),
        kept by `key` so it is built once per face scan."""
        if key is not None and key in self._face_scans:
            return self._face_scans[key]
        with self._vision_lock:
            faces = self.face3d_views(images_bgr)
        if not faces:
            raise ValueError("No face found in the face captures")
        scan = scan_face(faces)
        if key is not None:
            self._remember(self._face_scans, key, scan, 4)
        return scan

    def hair3d(self, images_bgr, angles, mannequin=True, face_images=None, keys=None, face_key=None):
        head = None
        if face_images is not None:
            scan = self.face_scan(face_images, face_key)
            head = lambda axes: face_splats(scan, axes)
        views = []
        keys = keys or [None] * len(images_bgr)
        for image_bgr, angle, key in zip(images_bgr, angles, keys):
            analysed = self._hair_view(image_bgr, key)
            if not analysed["mask"].any():
                continue
            yaw = analysed["yaw"] if analysed["yaw"] is not None else angle
            views.append(HairView(analysed["image"], analysed["alpha"], analysed["face_mask"], analysed["geometry"], yaw,
                                  tracked=analysed["points"] is not None))
        if not views:
            return None, None
        return build_hair_splats(views, mannequin=9000 if mannequin else 0, head=head)

    def reconstruct_transfer_mesh(self, images_bgr, angles):
        masks = []
        colors = []
        textures = []
        views = []
        valid_angles = []
        for image_bgr, angle in zip(images_bgr, angles):
            _, face, points, visible = self._transfer_head(image_bgr)
            geometry = self._head_geometry(points, face)
            mask, alpha = self.transfer_hair_mask(image_bgr, face, points, soft=True, face_visible=visible, geometry=geometry)
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
            rgba[:, :, 3] = (alpha[y0:y1, x0:x1] * 255).astype(np.uint8)
            success, encoded = cv2.imencode(".png", rgba)
            if success:
                views.append({
                    "angle": float(angle),
                    "image": "data:image/png;base64," + base64.b64encode(encoded.tobytes()).decode("ascii"),
                    "faceCenter": [
                        (geometry["center"][0] - x0) / geometry["face_w"],
                        (geometry["center"][1] - y0) / geometry["face_w"],
                    ],
                    "faceSize": [
                        (x1 - x0) / geometry["face_w"],
                        (y1 - y0) / geometry["face_w"],
                    ],
                    "roll": float(np.degrees(geometry["roll"])),
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
