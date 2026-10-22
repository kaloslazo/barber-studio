import cv2
import numpy as np

from app.core.segmentation.mp_segmenter import BACKGROUND, FACE_SKIN
from app.core.segmentation.transfer_mask import head_window, scale_geometry, shift_geometry

WORK_FACE_WIDTH = 110.0
DEFAULT_SKIN_LAB = np.array([170.0, 140.0, 145.0], np.float32)


def _kernel(size):
    size = max(3, int(size) | 1)
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))


class BaldRenderer:
    """Removes person B's own hair before the peluca goes on.

    Hair inside the skull silhouette becomes shaded scalp skin sampled from
    the face; hair outside it (long hair, volume) is replaced by a background
    plate learned from previous frames, or inpainted where the plate has
    never seen the scene."""

    def __init__(self):
        self.plate = None
        self.plate_valid = None
        self.skin = None
        self._rng = np.random.default_rng(7)

    def reset(self):
        self.plate = None
        self.plate_valid = None
        self.skin = None

    def learn(self, image_bgr, probabilities):
        if probabilities is None:
            return
        if self.plate is None or self.plate.shape[:2] != image_bgr.shape[:2]:
            self.plate = image_bgr.astype(np.float32)
            self.plate_valid = np.zeros(image_bgr.shape[:2], bool)
        background = np.where(probabilities[BACKGROUND] > 0.92, 255, 0).astype(np.uint8)
        background = cv2.erode(background, _kernel(image_bgr.shape[1] * 0.025)) > 0
        fresh = background & ~self.plate_valid
        seen = background & self.plate_valid
        self.plate[fresh] = image_bgr[fresh]
        self.plate[seen] = 0.8 * self.plate[seen] + 0.2 * image_bgr[seen]
        self.plate_valid |= background

    def _skin_lab(self, image_bgr, geometry, face_skin):
        face = np.zeros(image_bgr.shape[:2], np.uint8)
        cv2.fillPoly(face, [geometry["polygon"]], 255)
        face = cv2.erode(face, _kernel(geometry["face_w"] * 0.08))
        if face_skin is not None:
            face[face_skin < 0.7] = 0
        pixels = image_bgr[face > 0]
        if len(pixels) >= 200:
            lab = cv2.cvtColor(pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
            lightness = lab[:, 0]
            lit = lab[(lightness > np.percentile(lightness, 25)) & (lightness < np.percentile(lightness, 90))]
            sample = np.median(lit if len(lit) > 50 else lab, axis=0)
            self.skin = sample if self.skin is None else 0.85 * self.skin + 0.15 * sample
        return self.skin if self.skin is not None else DEFAULT_SKIN_LAB

    @staticmethod
    def _skull(shape, geometry):
        h, w = shape
        cx, cy = geometry["center"]
        fw = geometry["face_w"]
        roll = geometry["roll"]
        cos, sin = np.cos(roll), np.sin(roll)
        center = np.array([cx + sin * 0.02 * fw, cy - cos * 0.02 * fw], np.float32)
        axes = (0.55 * fw, 0.84 * fw)
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        dx, dy = xs - center[0], ys - center[1]
        u = (dx * cos + dy * sin) / axes[0]
        v = (-dx * sin + dy * cos) / axes[1]
        dome = (u * u + v * v <= 1.0) & (v <= 0.15)
        sides = np.zeros(shape, np.uint8)
        cv2.fillPoly(sides, [geometry["polygon"]], 255)
        sides = cv2.dilate(sides, _kernel(fw * 0.12)) > 0
        sides &= v > -0.2
        z = np.sqrt(np.clip(1.0 - u * u - v * v, 0.0, 1.0))
        return dome | sides, u, v, z

    @staticmethod
    def _seam_offset(image_bgr, scalp, remove, skull, face_skin, fw):
        """Color offset measured on the real skin bordering the old hairline,
        spread smoothly over the scalp so the painted skin meets the forehead
        without a seam."""
        ring = cv2.dilate(remove, _kernel(fw * 0.08)) > 0
        ring &= (remove == 0) & skull
        if face_skin is not None:
            ring &= face_skin > 0.5
        if ring.sum() < 20:
            return 0.0
        weight = ring.astype(np.float32)
        difference = (image_bgr.astype(np.float32) - scalp) * weight[..., None]
        sigma = max(2.0, fw * 0.3)
        spread = cv2.GaussianBlur(difference, (0, 0), sigma)
        support = cv2.GaussianBlur(weight, (0, 0), sigma)[..., None]
        confidence = np.clip(support / (support.max() * 0.15 + 1e-6), 0.0, 1.0)
        local = spread / np.maximum(support, 1e-3)
        overall = difference.sum(axis=(0, 1)) / weight.sum()
        return np.clip(confidence * local + (1.0 - confidence) * overall, -45.0, 45.0)

    def _inpaint(self, image_bgr, region):
        h, w = image_bgr.shape[:2]
        scale = min(1.0, 320.0 / w)
        size = (max(1, int(w * scale)), max(1, int(h * scale)))
        small = cv2.resize(image_bgr, size, interpolation=cv2.INTER_AREA)
        small_mask = cv2.resize(region, size, interpolation=cv2.INTER_NEAREST)
        small_mask = cv2.dilate(small_mask, _kernel(3))
        filled = cv2.inpaint(small, small_mask, 4, cv2.INPAINT_TELEA)
        filled = cv2.GaussianBlur(filled, (0, 0), 1.2)
        return cv2.resize(filled, (w, h), interpolation=cv2.INTER_LINEAR)

    def render(self, image_bgr, hair_mask, geometry, probabilities=None):
        result = image_bgr.copy()
        layer = self.layer(image_bgr, hair_mask, geometry, probabilities)
        if layer is None:
            return result
        x0, y0, fill, alpha = layer
        window = (slice(y0, y0 + fill.shape[0]), slice(x0, x0 + fill.shape[1]))
        alpha = alpha[..., None]
        result[window] = np.clip(image_bgr[window] * (1.0 - alpha) + fill * alpha, 0, 255).astype(np.uint8)
        return result

    def layer(self, image_bgr, hair_mask, geometry, probabilities=None):
        """The bald scalp as a patch: (x0, y0, fill, alpha) over the head
        window, or None when there is no hair to remove."""
        x0, y0, x1, y1 = head_window(image_bgr.shape[:2], geometry, 1.1)
        rows, cols = np.nonzero(hair_mask)
        if len(rows):
            pad = int(geometry["face_w"] * 0.1)
            x0, y0 = max(0, min(x0, cols.min() - pad)), max(0, min(y0, rows.min() - pad))
            x1 = min(image_bgr.shape[1], max(x1, cols.max() + pad + 1))
            y1 = min(image_bgr.shape[0], max(y1, rows.max() + pad + 1))
        window = (slice(y0, y1), slice(x0, x1))
        crop = image_bgr[window]
        scale = min(1.0, WORK_FACE_WIDTH / geometry["face_w"])
        size = (max(8, int(round((x1 - x0) * scale))), max(8, int(round((y1 - y0) * scale))))

        def shrink(layer, interpolation=cv2.INTER_AREA):
            return layer if scale == 1.0 else cv2.resize(layer, size, interpolation=interpolation)

        plate = None
        if self.plate is not None:
            plate = (shrink(self.plate[window]), shrink(self.plate_valid[window].astype(np.uint8), cv2.INTER_NEAREST) > 0)
        fill, alpha = self._render_window(
            shrink(crop),
            np.where(shrink(hair_mask[window]) > 127, 255, 0).astype(np.uint8),
            scale_geometry(shift_geometry(geometry, -x0, -y0), scale),
            None if probabilities is None else shrink(probabilities[FACE_SKIN][window]),
            plate,
        )
        if alpha is None:
            return None
        if scale != 1.0:
            fill = cv2.resize(fill, (x1 - x0, y1 - y0), interpolation=cv2.INTER_LINEAR)
            alpha = cv2.resize(alpha, (x1 - x0, y1 - y0), interpolation=cv2.INTER_LINEAR)
        return x0, y0, fill, alpha

    def _render_window(self, image_bgr, hair_mask, geometry, face_skin, plate):
        fw = geometry["face_w"]
        remove = cv2.dilate(hair_mask, _kernel(fw * 0.06))
        face = np.zeros(hair_mask.shape, np.uint8)
        cv2.fillPoly(face, [geometry["polygon"]], 255)
        remove[cv2.erode(face, _kernel(fw * 0.04)) > 0] = 0
        if not remove.any():
            return None, None

        fill = image_bgr.astype(np.float32)
        hole = remove > 0
        if plate is not None:
            known = hole & plate[1]
            fill[known] = plate[0][known]
            hole &= ~plate[1]
        if hole.any():
            source = cv2.dilate(np.where(hole, 255, 0).astype(np.uint8), _kernel(fw * 0.05))
            filled = self._inpaint(image_bgr, source)
            fill[hole] = filled[hole]
        alpha = cv2.GaussianBlur(remove.astype(np.float32) / 255.0, (0, 0), max(0.8, fw * 0.012))

        skull, u, v, z = self._skull(hair_mask.shape, geometry)
        paint = np.where(skull & (remove > 0), 255, 0).astype(np.uint8)
        if paint.any():
            skin = self._skin_lab(image_bgr, geometry, face_skin)
            rows, cols = np.nonzero(paint)
            pad = int(fw * 0.08) + 2
            box = (
                slice(max(0, rows.min() - pad), rows.max() + pad + 1),
                slice(max(0, cols.min() - pad), cols.max() + pad + 1),
            )
            u, v, z = u[box], v[box], z[box]
            shade = 0.8 + 0.24 * np.power(z, 0.7)
            shade += 0.08 * np.exp(-((u + 0.2) ** 2 + (v + 0.55) ** 2) / 0.08)
            grain = cv2.GaussianBlur(self._rng.normal(0.0, 2.5, z.shape).astype(np.float32), (0, 0), 0.7)
            lab = np.empty(z.shape + (3,), np.float32)
            lab[..., 0] = np.clip(skin[0] * shade + grain, 0, 255)
            lab[..., 1] = 128.0 + (skin[1] - 128.0) * 0.9
            lab[..., 2] = 128.0 + (skin[2] - 128.0) * 0.9
            scalp = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR).astype(np.float32)
            scalp += self._seam_offset(image_bgr[box], scalp, remove[box], skull[box],
                                       None if face_skin is None else face_skin[box], fw)
            coverage = cv2.GaussianBlur(paint[box].astype(np.float32) / 255.0, (0, 0), max(1.0, fw * 0.015))
            silhouette = cv2.GaussianBlur(skull[box].astype(np.float32), (0, 0), max(1.0, fw * 0.01))
            coverage = np.minimum(coverage * 1.3, silhouette)
            fill[box] = fill[box] * (1.0 - coverage[..., None]) + scalp * coverage[..., None]
            alpha[box] = np.maximum(alpha[box], coverage)
        return fill, alpha
