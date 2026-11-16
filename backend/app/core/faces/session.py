import cv2
import numpy as np

from app.core.faces.caricature import PRESETS, caricature
from app.core.faces.gallery import catalog, into_portrait
from app.core.faces.mesh import FaceMeshes, face_width
from app.core.faces.morph import morph
from app.core.faces.swap import swap_faces, wear_face

MODES = ("swap", "wear", "caricature")
SOURCE_SIDE = 720


class FaceStudio:
    """The face games: swap faces between the people in a picture, wear a
    saved face, caricatures and the fusion morph. Keeps one detector for
    photos, one that tracks across camera frames, and the saved face."""

    def __init__(self):
        self.photo = FaceMeshes(max_faces=4)
        self.camera = FaceMeshes(live=True, max_faces=3)
        self.source = None

    def detect(self, image_bgr, live=False, wanted=1):
        return (self.camera if live else self.photo).detect(image_bgr, wanted)

    def set_source(self, image_bgr):
        """Saves the biggest face of the picture as the face to wear, cropped
        around the head so it does not keep a whole photo in memory."""
        faces = self.photo.detect(image_bgr)
        if not faces:
            return None
        points = max(faces, key=face_width)
        fw = face_width(points)
        h, w = image_bgr.shape[:2]
        x0, y0 = np.maximum(points.min(axis=0) - fw * 0.4, 0).astype(int)
        x1, y1 = np.minimum(points.max(axis=0) + fw * 0.4, (w, h)).astype(int)
        crop = image_bgr[y0:y1, x0:x1]
        points = points - (x0, y0)
        scale = min(1.0, SOURCE_SIDE / max(crop.shape[:2]))
        if scale < 1.0:
            crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            points = points * scale
        self.source = (crop, points.astype(np.float32))
        return crop

    def apply(self, image_bgr, mode, preset="caricature", amount=0.8, live=False, other=None):
        """Runs one mode on a picture. Returns the result and how many faces
        were found; the picture comes back untouched when the mode needs more
        faces than there are."""
        if mode not in MODES:
            raise ValueError(f"Unknown face mode: {mode}")
        if mode == "caricature" and preset not in PRESETS:
            raise ValueError(f"Unknown caricature preset: {preset}")
        wanted = 2 if mode == "swap" and other is None else 1
        faces = self.detect(image_bgr, live, wanted)
        if not faces:
            return image_bgr, 0
        if mode == "caricature":
            return caricature(image_bgr, faces, preset, float(np.clip(amount, 0.0, 1.0))), len(faces)
        if other is not None:
            donors = self.photo.detect(other)
            if not donors:
                raise ValueError("No face detected in the second photo")
            return wear_face(image_bgr, faces, other, max(donors, key=face_width)), len(faces)
        if mode == "wear":
            if self.source is None:
                raise LookupError("Choose a face to wear first")
            return wear_face(image_bgr, faces, *self.source), len(faces)
        if len(faces) < 2:
            return image_bgr, len(faces)
        return swap_faces(image_bgr, faces), len(faces)

    def fusion(self, image_bgr, other=None, steps=13):
        """Morph frames between two faces: the biggest face of each photo, or
        the two biggest faces of a single photo, left to right."""
        faces = self.photo.detect(image_bgr, 1 if other is not None else 2)
        if other is not None:
            donors = self.photo.detect(other)
            if not faces or not donors:
                raise ValueError("No face detected in one of the photos")
            return morph(image_bgr, max(faces, key=face_width), other, max(donors, key=face_width), steps)
        if len(faces) < 2:
            raise ValueError("Need two faces in the photo")
        pair = sorted(sorted(faces, key=face_width)[-2:], key=lambda points: float(points[:, 0].mean()))
        return morph(image_bgr, pair[0], image_bgr, pair[1], steps)

    def gallery(self, image_bgr, key=None):
        """The biggest face of the photo inside one portrait of the Galería,
        or inside all of them."""
        if key and key not in catalog():
            raise ValueError(f"Unknown portrait: {key}")
        faces = self.photo.detect(image_bgr)
        if not faces:
            raise ValueError("No face detected in the image")
        points = max(faces, key=face_width)
        keys = [key] if key else list(catalog())
        return [(name, into_portrait(image_bgr, points, name)) for name in keys]

