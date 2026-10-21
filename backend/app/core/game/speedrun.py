import cv2
import numpy as np

from app.core.compositing.beard import LiveAnchor, _extended_points, beard_mask
from app.core.compositing.beard_physics import BeardPhysics

TARGETS = ("goatee", "mustache", "chinstrap")


def target_mask(shape, pts, target):
    """Region the player must keep. Everything else has to be shaved."""
    face_w = float(np.linalg.norm(pts[16] - pts[0]))
    if target == "chinstrap":
        full = beard_mask(shape, pts, "full")
        jaw = np.zeros(shape[:2], np.uint8)
        cv2.polylines(jaw, [pts[:17].astype(np.int32)], False, 255, 1)
        dist = cv2.distanceTransform(255 - jaw, cv2.DIST_L2, 5)
        return np.where((full > 0) & (dist < face_w * 0.09), 255, 0).astype(np.uint8)
    return beard_mask(shape, pts, target)


def full_region(shape, pts):
    region = beard_mask(shape, pts, "full")
    hull = np.zeros(shape[:2], np.uint8)
    cv2.fillConvexPoly(hull, cv2.convexHull(pts).astype(np.int32), 255)
    region = cv2.bitwise_and(region, hull)
    region = cv2.add(region, beard_mask(shape, pts, "mustache"))
    return region


class SpeedrunGame:
    """Barber Speedrun: shave a full physics beard down to a target style.

    The beard is a BeardPhysics simulation whose strands are anchored to the
    live face mesh. The clipper (index fingertip or pointer) sweeps a capsule
    between frames and cuts every strand whose root it touches. The score is
    clean x keep: the fraction of off-target strands shaved times the fraction
    of target strands preserved (0 at the start, 1000 for a perfect cut).
    """

    def __init__(self, target="goatee"):
        self.reset(target)

    def reset(self, target="goatee"):
        if target not in TARGETS:
            raise ValueError(f"Unknown target: {target}")
        self.target = target
        self.anchor = None
        self.physics = None
        self.in_target = None
        self.target_ref = None
        self.prev_tool = None
        self.cuts = 0
        self.clock = None

    def _setup(self, pts, shape):
        self.anchor = LiveAnchor(pts, shape[:2], "full")
        self.anchor.update(pts)
        self.anchor.ensure_mesh()
        self.anchor.cur_ext = self.anchor.ref_ext.copy()
        face_w = float(np.linalg.norm(pts[16] - pts[0]))
        region = full_region(shape, pts)
        if not (region > 0).any():
            self.anchor = None
            return False
        self.physics = BeardPhysics(self.anchor, region, pts, face_w, length_scale=0.8)
        target = target_mask(shape, pts, self.target)
        roots = self.physics.roots_ref.astype(int)
        roots[:, 0] = np.clip(roots[:, 0], 0, shape[1] - 1)
        roots[:, 1] = np.clip(roots[:, 1], 0, shape[0] - 1)
        self.in_target = target[roots[:, 1], roots[:, 0]] > 0
        self.target_ref = target
        return True

    def stats(self):
        if self.physics is None:
            return {"score": 0, "clean": 0.0, "keep": 0.0, "iou": 0.0, "overcut": 0, "left": 0,
                    "total": 0, "cuts": 0}
        alive = self.physics.alive
        target = self.in_target
        outside = ~target
        clean = float((~alive & outside).sum()) / max(int(outside.sum()), 1)
        keep = float((alive & target).sum()) / max(int(target.sum()), 1)
        inter = int((alive & target).sum())
        union = int((alive | target).sum())
        return {
            "score": int(round(1000 * clean * keep)),
            "clean": round(clean, 4),
            "keep": round(keep, 4),
            "iou": round(inter / max(union, 1), 4),
            "overcut": int((~alive & target).sum()),
            "left": int((alive & outside).sum()),
            "total": int(target.sum()),
            "cuts": self.cuts,
        }

    def frame(self, image_bgr, pts, tool, tool_on, now, tint, density=1.0, bearded=None):
        """Advance one frame. `tool` is the clipper position in pixels (or None)."""
        if pts is None:
            self.prev_tool = None
            return image_bgr.copy(), False
        pts = np.asarray(pts, np.float32)
        shape = image_bgr.shape
        if self.physics is None:
            if not self._setup(pts, shape):
                return image_bgr.copy(), False
            self.clock = now
        self.anchor.update(pts)
        self.anchor.cur_ext = _extended_points(pts)
        dt = now - (self.clock if self.clock is not None else now)
        self.clock = now
        self.physics.step(self.anchor, dt)
        face_w = float(np.linalg.norm(pts[16] - pts[0]))
        radius = face_w * 0.05
        if tool is not None and tool_on:
            start = self.prev_tool if self.prev_tool is not None else tool
            hit = self.physics.cut(start, tool, radius)
            self.cuts += len(hit)
        self.prev_tool = tool if (tool is not None and tool_on) else None

        out = image_bgr.astype(np.float32)
        if bearded is not None:
            kept = self.physics.shadow(shape[:2], density)
            full = self.physics.shadow(shape[:2], density, alive_only=False)
            coverage = np.clip(kept / np.maximum(full, 1e-3), 0.0, 1.0)
            coverage = np.where(full > 0.02, coverage, 1.0)[..., None]
            out = out * (1.0 - coverage) + bearded.astype(np.float32) * coverage
            rgb, alpha = self.physics.render(shape[:2], tint, density, include_live=False)
        else:
            shadow = self.physics.shadow(shape[:2], density)[..., None] * 0.55
            mult = 0.35 + 0.65 * (np.asarray(tint, np.float32) / 255.0)
            out = out * (1.0 - shadow) + out * mult * shadow
            rgb, alpha = self.physics.render(shape[:2], tint, density)
        alpha = alpha[..., None] * 0.9
        out = out * (1.0 - alpha) + rgb * alpha
        out = np.clip(out, 0, 255).astype(np.uint8)
        self._draw_target(out, pts)
        if tool is not None:
            self._draw_tool(out, tool, radius, tool_on)
        return out, True

    def _draw_target(self, out, pts):
        target = target_mask(out.shape, pts, self.target)
        contours, _ = cv2.findContours(target, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        for contour in contours:
            points = contour[:, 0, :]
            for i in range(0, len(points), 10):
                a = tuple(int(v) for v in points[i])
                b = tuple(int(v) for v in points[min(i + 5, len(points) - 1)])
                cv2.line(out, a, b, (60, 220, 255), 2, cv2.LINE_AA)

    @staticmethod
    def _draw_tool(out, tool, radius, on):
        center = (int(tool[0]), int(tool[1]))
        color = (80, 220, 80) if on else (180, 180, 180)
        cv2.circle(out, center, int(radius), color, 2, cv2.LINE_AA)
        cv2.circle(out, center, 3, color, -1, cv2.LINE_AA)
