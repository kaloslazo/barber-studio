import cv2
import numpy as np

from app.core.compositing.beard import mouth_hole_mask, style_region

FACE_VERTICES = 468
REFERENCE_MARGIN = 0.12
GAIN_FLOOR = 0.6
GAIN_MAX = 1.6
JAW_LOOP = [172, 136, 150, 149, 176, 148, 152, 377, 400, 378, 379, 365, 397]
NECK_STYLES = ("full", "stubble")
NECK_DROP = 0.03
NECK_BACK = 0.5
NECK_CHROMA = (0.45, 6.0, 18.0)

_triangles = None


def face_triangles():
    """Triangles of MediaPipe's face mesh: the 3-cliques of its tessellation
    edges."""
    global _triangles
    if _triangles is None:
        from mediapipe.tasks.python import vision

        edges = {tuple(sorted((c.start, c.end))) for c in vision.FaceLandmarksConnections.FACE_LANDMARKS_TESSELATION}
        neighbours = {}
        for a, b in edges:
            neighbours.setdefault(a, set()).add(b)
            neighbours.setdefault(b, set()).add(a)
        _triangles = np.array(sorted({tuple(sorted((a, b, c))) for a, b in edges for c in neighbours[a] & neighbours[b]}), np.int32)
    return _triangles


class MeshBeard:
    """The beard region as a texture on the 3D face mesh.

    The 2D region of a style is drawn once on a frontal reference frame; each
    mesh vertex remembers where it sat in that frame (its UV). Every frame
    the front-facing triangles are rasterised far to near, which hides what
    is behind the nose and the cheek, and the reference region is sampled
    through the interpolated UVs. The region follows the head in 3D instead
    of being redrawn from 68 projected points that collapse when it turns."""

    def __init__(self, mesh, points, shape, triangles=None):
        self.neck = triangles is None
        base = face_triangles() if triangles is None else np.asarray(triangles, np.int32)
        self.shape = tuple(shape)
        self.points = np.asarray(points, np.float32)
        if self.neck:
            strip = []
            for k in range(len(JAW_LOOP) - 1):
                a, b, c, d = JAW_LOOP[k], JAW_LOOP[k + 1], FACE_VERTICES + k, FACE_VERTICES + k + 1
                strip += [(a, b, c), (b, d, c)]
            self.triangles = np.vstack([base, np.array(strip, np.int32)])
        else:
            self.triangles = base
        self.face_triangles = len(base)
        xyz = self.extended(mesh)
        face_w = float(np.linalg.norm(self.points[16] - self.points[0]))
        corners = self.points.min(axis=0), self.points.max(axis=0)
        margin = REFERENCE_MARGIN * face_w
        self.origin = np.floor(np.minimum(xyz[:, :2].min(axis=0), corners[0]) - margin).astype(int)
        end = np.ceil(np.maximum(xyz[:, :2].max(axis=0), corners[1]) + margin).astype(int)
        self.size = (int(end[1] - self.origin[1]), int(end[0] - self.origin[0]))
        self.uv = (xyz[:, :2] - self.origin).astype(np.float32)
        face = xyz[:FACE_VERTICES]
        centre = np.array([face[:, 0].mean(), face[:, 1].mean(), face[:, 2].max() + 0.35 * np.ptp(face[:, 2])])
        corners3 = xyz[self.triangles]
        normals = np.cross(corners3[:, 1] - corners3[:, 0], corners3[:, 2] - corners3[:, 0])
        self.winding = np.where(((corners3.mean(axis=1) - centre) * normals).sum(axis=1) >= 0, 1.0, -1.0)
        self.textures = {}
        self.reference_ids = None

    def extended(self, mesh):
        """The face vertices plus a neck skirt: the lower jaw copied down the
        axis from brow to chin and back towards the nape (the neck sits behind
        the chin), tapering to the jaw angles, so a full beard can continue
        under the chin."""
        xyz = np.asarray(mesh, np.float64)[:FACE_VERTICES]
        if not self.neck:
            return xyz
        down = xyz[152] - xyz[10]
        length = float(np.linalg.norm(down))
        down = down / max(length, 1e-9)
        forward = xyz[4] - 0.5 * (xyz[234] + xyz[454])
        forward = forward - (forward @ down) * down
        back = -forward / max(float(np.linalg.norm(forward)), 1e-9)
        t = (np.arange(len(JAW_LOOP)) + 0.5) / len(JAW_LOOP)
        step = NECK_DROP * length * (np.sin(np.pi * t) ** 0.5)[:, None] * (down + NECK_BACK * back)
        return np.vstack([xyz, xyz[JAW_LOOP] + step])

    def texture(self, style):
        if style not in self.textures:
            full = style_region(self.shape, self.points, style, live=True)
            if self.neck and style in NECK_STYLES:
                reference = self.uv + self.origin
                for tri in self.triangles[self.face_triangles:]:
                    cv2.fillConvexPoly(full, np.round(reference[tri] * 16).astype(np.int32), 255, lineType=cv2.LINE_8, shift=4)
            texture = np.zeros(self.size, np.uint8)
            x0, y0 = self.origin
            h, w = self.shape
            sy0, sx0 = max(y0, 0), max(x0, 0)
            sy1, sx1 = min(y0 + self.size[0], h), min(x0 + self.size[1], w)
            if sy1 > sy0 and sx1 > sx0:
                texture[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = full[sy0:sy1, sx0:sx1]
            self.textures[style] = texture
        return self.textures[style]

    def facing(self, mesh):
        """Front-facing triangles ordered far to near, and the cosine between
        every triangle normal and the viewing direction."""
        corners3 = self.extended(mesh)[self.triangles]
        normals = np.cross(corners3[:, 1] - corners3[:, 0], corners3[:, 2] - corners3[:, 0]) * self.winding[:, None]
        cosine = -normals[:, 2] / np.maximum(np.linalg.norm(normals, axis=1), 1e-9)
        front = np.nonzero(cosine > 0)[0]
        return front[np.argsort(-corners3[front, :, 2].mean(axis=1))], cosine

    def visible(self, mesh):
        return self.facing(mesh)[0]

    def locate(self, points):
        """Reference triangle and barycentric weights of points given in
        texture coordinates (used to pin strands to the surface)."""
        if self.reference_ids is None:
            ids = np.full(self.size, -1, np.int32)
            fixed = np.round(self.uv * 16).astype(np.int32)
            for index, tri in enumerate(self.triangles):
                cv2.fillConvexPoly(ids, fixed[tri], index, lineType=cv2.LINE_8, shift=4)
            self.reference_ids = ids
        points = np.asarray(points, np.float64)
        x = np.clip(np.round(points[:, 0]).astype(int), 0, self.size[1] - 1)
        y = np.clip(np.round(points[:, 1]).astype(int), 0, self.size[0] - 1)
        tri = self.reference_ids[y, x]
        valid = tri >= 0
        tri = np.where(valid, tri, 0)
        a, b, c = (self.uv[self.triangles[tri, k]].astype(np.float64) for k in range(3))
        denom = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
        denom = np.where(np.abs(denom) < 1e-9, 1e-9, denom)
        l1 = ((b[:, 1] - c[:, 1]) * (points[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (points[:, 1] - c[:, 1])) / denom
        l2 = ((c[:, 1] - a[:, 1]) * (points[:, 0] - c[:, 0]) + (a[:, 0] - c[:, 0]) * (points[:, 1] - c[:, 1])) / denom
        weights = np.clip(np.stack([l1, l2, 1.0 - l1 - l2], axis=1), 0.0, 1.0)
        return tri, weights / (weights.sum(axis=1, keepdims=True) + 1e-12), valid

    def region(self, mesh, style, origin, shape, points, grow=0):
        return self.view(mesh, style, origin, shape, points, grow)["region"]

    def view(self, mesh, style, origin, shape, points, grow=0, image=None):
        """The beard on the current frame for a crop whose top-left corner is
        `origin` in the frame of `mesh`; `points` are the 68 landmarks in crop
        coordinates and `grow` widens the region by that many pixels. Returns
        the uint8 region, a gain map for the base tint (a surface seen at a
        grazing angle covers more hair per pixel: 1 / cosine, capped), the mask of front-facing
        triangles and the mesh in crop coordinates. With the crop `image`, the
        neck skirt only keeps pixels whose chroma is that of the face skin: in
        profile part of the skirt lies over the wall behind the chin."""
        h, w = shape
        xyz = self.extended(mesh)
        xy = xyz[:, :2] - np.asarray(origin, np.float64)
        order, cosine = self.facing(mesh)
        fixed = np.round(xy * 16).astype(np.int32)
        ids = np.full((h, w), -1, np.int32)
        for index in order:
            cv2.fillConvexPoly(ids, fixed[self.triangles[index]], int(index), lineType=cv2.LINE_8, shift=4)
        front = np.zeros(len(self.triangles), bool)
        front[order] = True
        out = np.zeros((h, w), np.uint8)
        gain = np.ones((h, w), np.float32)
        ys, xs = np.nonzero(ids >= 0)
        if len(xs):
            tri = self.triangles[ids[ys, xs]]
            a, b, c = xy[tri[:, 0]], xy[tri[:, 1]], xy[tri[:, 2]]
            denom = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
            denom = np.where(np.abs(denom) < 1e-9, 1e-9, denom)
            px, py = xs.astype(np.float64), ys.astype(np.float64)
            l1 = ((b[:, 1] - c[:, 1]) * (px - c[:, 0]) + (c[:, 0] - b[:, 0]) * (py - c[:, 1])) / denom
            l2 = ((c[:, 1] - a[:, 1]) * (px - c[:, 0]) + (a[:, 0] - c[:, 0]) * (py - c[:, 1])) / denom
            weights = np.clip(np.stack([l1, l2, 1.0 - l1 - l2], axis=1), 0.0, 1.0)
            weights /= weights.sum(axis=1, keepdims=True) + 1e-12
            uv = (weights[:, :, None] * self.uv[tri]).sum(axis=1)
            map_x = np.full((h, w), -1.0, np.float32)
            map_y = np.full((h, w), -1.0, np.float32)
            map_x[ys, xs], map_y[ys, xs] = uv[:, 0], uv[:, 1]
            out = cv2.remap(self.texture(style), map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            gain[ys, xs] = np.clip(1.0 / np.maximum(cosine[ids[ys, xs]], GAIN_FLOOR), 1.0, GAIN_MAX)
            gain = cv2.GaussianBlur(gain, (0, 0), 3.0)
            neck = ids >= self.face_triangles
            if image is not None and self.neck and neck.any():
                chroma = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)[..., 1:].astype(np.float32)
                skin = (ids >= 0) & (ids < self.face_triangles) & (out == 0)
                if skin.sum() > 200:
                    centre = np.median(chroma[skin], axis=0)
                    share, low, high = NECK_CHROMA
                    tolerance = float(np.clip(share * np.linalg.norm(centre - 128.0), low, high))
                    out[neck & (np.linalg.norm(chroma - centre, axis=2) > tolerance)] = 0
        if grow > 0:
            out = cv2.dilate(out, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * grow + 1, 2 * grow + 1)))
        region = cv2.subtract(out, mouth_hole_mask((h, w), np.asarray(points, np.float32), live=True))
        return {"region": region, "gain": gain, "front": front, "xy": xy.astype(np.float32)}
