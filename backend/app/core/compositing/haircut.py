import cv2
import numpy as np

STYLES = {
    "low-fade": {
        "ear_reach": 0.38,
        "nape_reach": 0.22,
        "min_length": 0.08,
    },
    "buzz": {"uniform": 0.12, "crown_length": 0.30},
}
DISABLED_STYLES = ("mid-fade", "high-fade")


def _smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _anchors(points, face_box):
    x, y, fw, fh = [float(v) for v in face_box]
    cx = x + fw / 2.0
    if points is not None:
        pts = np.asarray(points, np.float32)
        brow_y = float((pts[19][1] + pts[24][1]) / 2.0)
        jaw_y = float(pts[8][1])
        ear_l = np.array([float(pts[0][0]) - fw * 0.04, float(pts[0][1]) - fh * 0.28])
        ear_r = np.array([float(pts[16][0]) + fw * 0.04, float(pts[16][1]) - fh * 0.28])
    else:
        brow_y = y + fh * 0.30
        jaw_y = y + fh
        ear_l = np.array([x, y + fh * 0.45])
        ear_r = np.array([x + fw, y + fh * 0.45])
    ear_y = float((ear_l[1] + ear_r[1]) / 2.0)
    return cx, fw, fh, brow_y, jaw_y, ear_l, ear_r, ear_y


def _face_guard(shape, points, face_box):
    h, w = shape[:2]
    guard = np.zeros((h, w), np.uint8)
    if points is not None:
        hull = cv2.convexHull(np.asarray(points, np.float32).astype(np.int32))
        cv2.fillPoly(guard, [hull], 255)
    else:
        x, y, fw, fh = [int(v) for v in face_box]
        cv2.rectangle(guard, (x, y), (x + fw, y + fh), 255, -1)
    grow = max(5, int(face_box[3] * 0.07))
    return cv2.dilate(guard, np.ones((grow * 2 + 1, grow * 2 + 1), np.uint8))


def _head_support(hair_soft, face_guard, anchors):
    """Observed skull envelope: the hair mask minus the hanging side/neck
    locks (below the ear line at the sides, below the jaw anywhere)."""
    h, w = hair_soft.shape
    cx, fw, fh, brow_y, jaw_y, ear_l, ear_r, ear_y = anchors
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    side_band = np.abs(xs - cx) > fw * 0.45
    external_zone = ((ys > ear_y + fh * 0.05) & side_band) | (ys > jaw_y + fh * 0.15)
    support = hair_soft * (1.0 - external_zone.astype(np.float32))
    support[face_guard > 0] = 0.0
    return support, external_zone


def _length_field(shape, hair_soft, anchors, style, cfg):
    """Continuous hair length in [0,1]: 1 = original, ~0.1 = almost shaved."""
    h, w = shape[:2]
    cx, fw, fh, brow_y, jaw_y, ear_l, ear_r, ear_y = anchors
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)

    if "uniform" in cfg:
        crown = _smoothstep((ear_y - ys) / (fh * 0.9))
        length = cfg["uniform"] + (cfg["crown_length"] - cfg["uniform"]) * crown
        return np.clip(length, 0.0, 1.0) * hair_soft

    d_ear = np.minimum(
        np.hypot(xs - ear_l[0], ys - ear_l[1]),
        np.hypot(xs - ear_r[0], ys - ear_r[1]),
    )
    nape = np.array([cx, jaw_y + fh * 0.18])
    d_nape = np.hypot(xs - nape[0], ys - nape[1])
    reach_ear = cfg["ear_reach"] * fh
    reach_nape = cfg["nape_reach"] * fh
    width = fh * 0.28

    short_ear = _smoothstep((reach_ear - d_ear) / width)
    short_nape = _smoothstep((reach_nape - d_nape) / width)
    shortness = np.maximum(short_ear, short_nape)
    length = 1.0 - (1.0 - cfg["min_length"]) * shortness
    return np.clip(length, 0.0, 1.0) * hair_soft


def _scalp_samples(image_bgr, face_box, points, hair_mask):
    h, w = image_bgr.shape[:2]
    x, y, fw, fh = [int(v) for v in face_box]
    roi = np.zeros((h, w), np.uint8)
    if points is not None:
        pts = np.asarray(points, np.float32)
        nose_len = np.linalg.norm(pts[30] - pts[27])
        forehead = (pts[27] + pts[28]) / 2 + np.array([0.0, -nose_len * 0.45])
        cv2.circle(roi, (int(forehead[0]), int(forehead[1])), max(4, int(nose_len * 0.4)), 255, -1)
        cx = (pts[19][0] + pts[24][0]) / 2
        for corner in (pts[36], pts[45]):
            temple = corner + np.array([np.sign(corner[0] - cx) * fw * 0.08, -fh * 0.02])
            cv2.circle(roi, (int(temple[0]), int(temple[1])), max(3, int(fw * 0.05)), 255, -1)
    else:
        cv2.rectangle(roi, (x + fw // 4, y + fh // 12), (x + 3 * fw // 4, y + fh // 4), 255, -1)
    roi = cv2.subtract(roi, (hair_mask > 0).astype(np.uint8) * 255)
    return roi


def _lighting_field(image_bgr, hair_mask, fill_bgr):
    replaced = image_bgr.astype(np.float32)
    replaced[hair_mask > 127] = fill_bgr
    field = cv2.cvtColor(replaced.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
    field = cv2.GaussianBlur(field, (0, 0), max(8.0, image_bgr.shape[0] / 16.0))
    zone = field[hair_mask > 127]
    median = np.median(zone) if zone.size else 128.0
    return field / max(median, 1.0)


def apply_haircut(image_bgr, hair_mask, face_box, points, style, strength):
    """Multi-layer clipper renderer.

    background_clean = original with external hanging hair inpainted
    result = blend(background_clean, short_hair_layer, fade_alpha)
    result = blend(result, original_top_hair, top_alpha)
    """
    if style not in STYLES:
        raise ValueError(f"Style '{style}' is temporarily disabled")
    h, w = image_bgr.shape[:2]
    fw, fh = float(face_box[2]), float(face_box[3])
    density = float(np.clip(strength, 0.0, 1.0))
    if density <= 0.0:
        return image_bgr.copy()

    hair_soft = cv2.GaussianBlur(
        (hair_mask > 0).astype(np.float32), (0, 0), max(2.0, fw / 150.0)
    )
    face_guard = _face_guard(image_bgr.shape, points, face_box)
    anchors = _anchors(points, face_box)
    head_support, external_zone = _head_support(hair_soft, face_guard, anchors)
    length = _length_field(image_bgr.shape, hair_soft, anchors, style, STYLES[style])

    external_hair = hair_soft * external_zone
    inpaint_mask = (external_hair > 0.4).astype(np.uint8) * 255
    inpaint_mask = cv2.dilate(inpaint_mask, np.ones((5, 5), np.uint8))
    inpaint_mask[face_guard > 0] = 0
    safe_to_inpaint = (
        (inpaint_mask > 0).sum() < 0.12 * h * w
        and (inpaint_mask & face_guard).sum() == 0
    )
    base = image_bgr.copy()
    if safe_to_inpaint and (inpaint_mask > 0).sum() > 150:
        base = cv2.inpaint(base, inpaint_mask, 5, cv2.INPAINT_TELEA)

    hair_pixels = image_bgr[hair_mask > 0]
    hair_color = (
        np.median(hair_pixels, axis=0).astype(np.float32)
        if len(hair_pixels) > 100
        else np.array([60.0, 55.0, 50.0])
    )
    roi = _scalp_samples(image_bgr, face_box, points, hair_mask)
    scalp_pixels = image_bgr[roi > 0]
    scalp_bgr = (
        np.median(scalp_pixels, axis=0).astype(np.float32)
        if len(scalp_pixels) > 100
        else np.array([150.0, 140.0, 130.0])
    )

    lighting = _lighting_field(image_bgr, hair_mask, scalp_bgr)
    rng = np.random.default_rng(6)
    fine = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 1.0) - 0.5

    short_layer = hair_color[None, None, :] * (0.70 + 0.30 * lighting)[..., None]
    short_layer = short_layer + (fine[..., None] * 10.0)
    scalp_layer = scalp_bgr[None, None, :] * (0.85 + 0.15 * lighting)[..., None]
    near_skin = np.clip((0.18 - length) / 0.18, 0.0, 0.7)
    layer = short_layer * (1.0 - near_skin[..., None]) + scalp_layer * near_skin[..., None]

    guard_soft = cv2.GaussianBlur(
        (face_guard > 0).astype(np.float32), (0, 0), max(2.0, fh / 90.0)
    )
    fade_alpha = np.clip(1.0 - length, 0.0, 1.0) * hair_soft * density * (1.0 - guard_soft)
    fade_alpha[face_guard > 0] = 0.0

    out = base.astype(np.float32)
    out = out * (1.0 - fade_alpha[..., None]) + layer * fade_alpha[..., None]

    top_alpha = np.clip((length - 0.75) / 0.25, 0.0, 1.0) * (1.0 - guard_soft)
    top_alpha = np.clip(top_alpha, 0.0, 1.0)
    out = out * (1.0 - top_alpha[..., None]) + image_bgr.astype(np.float32) * top_alpha[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)


def debug_sheet(image_bgr, hair_mask, face_box, points, style, strength=0.9):
    """Seven-panel diagnostic over the original photo."""
    hair_soft = cv2.GaussianBlur(
        (hair_mask > 0).astype(np.float32), (0, 0), max(2.0, float(face_box[2]) / 150.0)
    )
    face_guard = _face_guard(image_bgr.shape, points, face_box)
    anchors = _anchors(points, face_box)
    head_support, external_zone = _head_support(hair_soft, face_guard, anchors)
    length = _length_field(image_bgr.shape, hair_soft, anchors, style, STYLES[style])
    fade_alpha = np.clip(1.0 - length, 0.0, 1.0) * float(strength)
    fade_alpha[face_guard > 0] = 0.0
    result = apply_haircut(image_bgr, hair_mask, face_box, points, style, strength)

    def overlay(mask, color, label):
        canvas = image_bgr.astype(np.float32)
        m = np.clip(mask, 0, 1)[..., None]
        canvas = canvas * (1.0 - 0.55 * m) + np.array(color, np.float32) * (0.55 * m)
        return canvas.astype(np.uint8), label

    panels = [
        overlay(hair_soft, (80, 220, 80), "1 hair"),
        overlay((face_guard > 0).astype(np.float32), (60, 60, 240), "2 face guard"),
        overlay(head_support, (220, 120, 60), "3 head support"),
        overlay(hair_soft * external_zone, (60, 200, 240), "4 external hair"),
        overlay(np.clip(1.0 - length, 0, 1), (200, 60, 200), "5 short region"),
        overlay(fade_alpha, (40, 140, 255), "6 fade alpha"),
        (result, "7 result"),
    ]

    h_img, w_img = image_bgr.shape[:2]
    bar = np.full((56, w_img, 3), 245, np.uint8)
    tiles = []
    for img_p, label in panels:
        b = bar.copy()
        cv2.putText(b, label, (14, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (15, 15, 15), 3)
        tiles.append(np.vstack([b, img_p]))
    return np.hstack(tiles)
