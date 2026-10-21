import base64

import cv2
import numpy as np

from app.core.compositing.beard import beard_mask
from app.core.lab.avatar import SIDE_A, SIDE_B, MeshTracker, build_scanned_head, face_width

FLIP = np.diag([1.0, -1.0, -1.0])


class LabSession:
    """3D Lab (beta): scan a head from several webcam views (B) and drive it live (D).

    Kept apart from the rest of the app: own trackers, own state, own endpoints.
    """

    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.scan_tracker = MeshTracker(live=False)
        self.live_tracker = MeshTracker(live=True)
        self.head = None
        self.center = None

    def _normalize(self, mesh):
        return ((mesh.astype(np.float64) - self.center) @ FLIP.T) / self.head.fw

    def build(self, images_bgr, beard_style=None):
        views, meshes = [], []
        for image in images_bgr:
            h, w = image.shape[:2]
            if w > 1024:
                image = cv2.resize(image, (1024, int(round(h * 1024 / w))), interpolation=cv2.INTER_AREA)
            mesh = self.scan_tracker.mesh(image)
            if mesh is not None:
                views.append(image)
                meshes.append(mesh)
        if not views:
            return None
        yaw = [abs(float((m[1, 0] - 0.5 * (m[SIDE_A, 0] + m[SIDE_B, 0])) / max(face_width(m), 1.0))) for m in meshes]
        ref = int(np.argmin(yaw))
        texture, region = None, None
        if beard_style:
            bearded = self.pipeline.apply_beard(views[ref], beard_style, 0.9)
            detector = self.pipeline.landmark_detector
            points = detector.landmarks(views[ref]) if detector is not None else None
            if bearded is not None and points is not None:
                texture = bearded
                region = beard_mask(views[ref].shape, points, beard_style)
        head, metrics = build_scanned_head(views, meshes, texture, region, beard_style)
        self.head = head
        self.center = meshes[ref].astype(np.float64).mean(axis=0)
        rows = head.pack()
        return {
            "count": int(len(rows)),
            "beard": int(head.is_beard.sum()),
            "triangles": head.tris.ravel().astype(int).tolist(),
            "mesh": self._normalize(meshes[ref]).astype(np.float32).ravel().tolist(),
            "gaussians": base64.b64encode(rows.tobytes()).decode("ascii"),
            "metrics": metrics,
            "yaw": [round(v, 3) for v in yaw],
        }

    def live_mesh(self, image_bgr):
        if self.head is None:
            return None
        mesh = self.live_tracker.mesh(image_bgr)
        if mesh is None:
            return None
        centered = ((mesh.astype(np.float64) - mesh.astype(np.float64).mean(axis=0)) @ FLIP.T) / self.head.fw
        return centered.astype(np.float32).ravel().tolist()
