import cv2
import numpy as np

STYLES = {
    "low-fade": {
        "ear_reach": 0.50,
        "temple_reach": 0.30,
        "ear_short": 0.95,
        "temple_short": 0.60,
    },
}
DISABLED_STYLES = ("mid-fade", "high-fade", "buzz")


def _smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _face_guard(shape, points, face_box, hair_mask=None):
    h, w = shape[:2]
    guard = np.zeros((h, w), np.uint8)
    if points is not None:
        pts68 = np.asarray(points, np.float32)
        oval = np.vstack([pts68[0:17], pts68[26:16:-1]]).astype(np.int32)
        cv2.fillPoly(guard, [oval], 255)
        for ring in (pts68[36:42], pts68[42:48], pts68[48:60], pts68[17:22], pts68[22:27]):
            cv2.fillPoly(guard, [ring.astype(np.int32)], 255)
        x, y, fw, fh = [float(v) for v in face_box]
        brow_y = float((pts68[19][1] + pts68[24][1]) / 2.0)
        hairline_y = None
        if hair_mask is not None:
            hair = (hair_mask > 0).astype(np.uint8)
            cx_col = int(x + fw * 0.5)
            band = hair[:, max(0, cx_col - 8):cx_col + 8]
            rows = np.where(band.any(axis=1))[0]
            window = rows[(rows > brow_y - 1.3 * fh) & (rows < brow_y)]
            if len(window):
                hairline_y = float(window.max())
        top = hairline_y if hairline_y is not None else brow_y - fh * 0.35
        cv2.rectangle(
            guard,
            (int(x + fw * 0.10), int(brow_y - fh * 0.08)),
            (int(x + fw * 0.90), int(top)),
            255,
            -1,
        )
    else:
        x, y, fw, fh = [int(v) for v in face_box]
        cv2.rectangle(guard, (x, y), (x + fw, y + fh), 255, -1)
    grow = max(4, int(face_box[3] * 0.04))
    guard = cv2.dilate(guard, np.ones((grow * 2 + 1, grow * 2 + 1), np.uint8))
    if hair_mask is not None:
        hair_zone = cv2.dilate((hair_mask > 0).astype(np.uint8), np.ones((11, 11), np.uint8))
        guard[hair_zone > 0] = 0
    return guard


def _head_envelope(shape, hair_mask, face_box, points):
    """Observed head envelope: bounded above by the REAL top contour of the
    hair mask, on the sides by ear landmarks, below by the jaw line."""
    h, w = shape[:2]
    hair = (hair_mask > 0).astype(np.uint8)
    pts68 = np.asarray(points, np.float32)
    x, y, fw, fh = [float(v) for v in face_box]
    x0 = max(0, int(float(pts68[0][0]) - fw * 0.10))
    x1 = min(w - 1, int(float(pts68[16][0]) + fw * 0.10))
    jaw_y = float(pts68[8][1])
    bottom = int(jaw_y + fh * 0.10)

    top_row = np.full(w, -1.0)
    for col in range(x0, x1 + 1):
        rows = np.where(hair[:, col] > 0)[0]
        if len(rows):
            top_row[col] = float(rows.min())
    valid = np.where(top_row >= 0)[0]
    if len(valid) < 5:
        return np.zeros((h, w), np.float32)
    top_row = np.interp(np.arange(w), valid, top_row[valid])
    kernel = np.ones(21)
    top_row = np.convolve(top_row, kernel / kernel.sum(), mode="same")

    ys, xs = np.mgrid[0:h, 0:w]
    head = (ys >= top_row[None, :]) & (ys <= bottom) & (xs >= x0) & (xs <= x1)
    head = cv2.morphologyEx(
        head.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8)
    )
    return head.astype(np.float32)


def _shortness_field(shape, hair_soft, face_box, points):
    """Continuous shortness in [0,1]: 0 top-center, medium at temples,
    high at ears/sideburns/lower sides. Symmetric, no forehead stripe."""
    h, w = shape[:2]
    cfg = STYLES["low-fade"]
    pts68 = np.asarray(points, np.float32)
    x, y, fw, fh = [float(v) for v in face_box]
    cx = x + fw / 2.0
    brow_y = float((pts68[19][1] + pts68[24][1]) / 2.0)
    ear_l = np.array([float(pts68[0][0]), float(pts68[0][1]) - fh * 0.28])
    ear_r = np.array([float(pts68[16][0]), float(pts68[16][1]) - fh * 0.28])
    temple_l = np.array([float(pts68[17][0]), float(pts68[17][1]) - fh * 0.22])
    temple_r = np.array([float(pts68[26][0]), float(pts68[26][1]) - fh * 0.22])

    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    d_ear = np.minimum(np.hypot(xs - ear_l[0], ys - ear_l[1]), np.hypot(xs - ear_r[0], ys - ear_r[1]))
    d_temple = np.minimum(
        np.hypot(xs - temple_l[0], ys - temple_l[1]),
        np.hypot(xs - temple_r[0], ys - temple_r[1]),
    )
    short_ear = cfg["ear_short"] * _smoothstep((cfg["ear_reach"] * fh - d_ear) / (0.30 * fh))
    short_temple = cfg["temple_short"] * _smoothstep((cfg["temple_reach"] * fh - d_temple) / (0.25 * fh))
    lateral = np.abs(xs - cx) / max(fw, 1.0)
    below_ear = 0.9 * _smoothstep((ear_l[1] + 0.05 * fh - ys) * -1.0 / (0.35 * fh)) * _smoothstep((lateral - 0.32) / 0.18)
    central_kill = _smoothstep((lateral - 0.18) / 0.15)

    shortness = np.maximum.reduce([short_ear, short_temple, below_ear])
    shortness = shortness * central_kill * hair_soft
    return np.clip(shortness, 0.0, 1.0)


def _scalp_roi(image_bgr, face_box, points, hair_mask):
    h, w = image_bgr.shape[:2]
    pts68 = np.asarray(points, np.float32)
    x, y, fw, fh = [int(v) for v in face_box]
    roi = np.zeros((h, w), np.uint8)
    nose_len = np.linalg.norm(pts68[30] - pts68[27])
    forehead = (pts68[27] + pts68[28]) / 2 + np.array([0.0, -nose_len * 0.45])
    cv2.circle(roi, (int(forehead[0]), int(forehead[1])), max(4, int(nose_len * 0.4)), 255, -1)
    cx = (pts68[19][0] + pts68[24][0]) / 2
    for corner in (pts68[36], pts68[45]):
        temple = corner + np.array([np.sign(corner[0] - cx) * fw * 0.08, -fh * 0.02])
        cv2.circle(roi, (int(temple[0]), int(temple[1])), max(3, int(fw * 0.05)), 255, -1)
    roi = cv2.subtract(roi, (hair_mask > 0).astype(np.uint8) * 255)
    return roi


def _lab_median(pixels_bgr):
    if len(pixels_bgr) == 0:
        return np.array([0.0, 128.0, 128.0], np.float32)
    lab = cv2.cvtColor(pixels_bgr.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2LAB)
    return np.median(lab.reshape(-1, 3), axis=0).astype(np.float32)


def _background_plate(image_bgr, hair_mask, face_guard, face_box, points):
    """Clean plate from reliable background: samples far from hair, face and
    the neck/shoulder band. Returns None when the background is not uniform."""
    h, w = image_bgr.shape[:2]
    far = 1 - (
        cv2.dilate((hair_mask > 0).astype(np.uint8), np.ones((81, 81), np.uint8)) > 0
    ).astype(np.uint8)
    far[face_guard > 0] = 0
    far = cv2.dilate(far, np.ones((9, 9), np.uint8))
    if points is not None:
        pts68 = np.asarray(points, np.float32)
        fh = float(face_box[3])
        cv2.rectangle(far, (0, int(pts68[8][1] - fh * 0.1)), (w - 1, h - 1), 0, -1)
    if (far > 0).sum() < 2000:
        return None
    pixels = image_bgr[far > 0]
    lab = cv2.cvtColor(pixels.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2LAB).reshape(-1, 3)
    if float(lab[:, 0].std()) > 22.0:
        return None
    return np.median(pixels, axis=0).astype(np.float32)


def apply_haircut(image_bgr, hair_mask, face_box, points, style, strength, templates=None):
    """Low-fade layered renderer (template-free):
    M_side gets synthetic short hair, M_external locks are cleaned with a
    background plate, M_top keeps the original pixels."""
    if style not in STYLES:
        raise ValueError(f"Style '{style}' is temporarily disabled")
    density = float(np.clip(strength, 0.0, 1.0))
    if density <= 0.0:
        return image_bgr.copy()
    if points is None:
        return image_bgr.copy()

    h, w = image_bgr.shape[:2]
    fw, fh = float(face_box[2]), float(face_box[3])
    hair_soft = cv2.GaussianBlur(
        (hair_mask > 0).astype(np.float32), (0, 0), max(2.0, fw / 150.0)
    )
    face_guard = _face_guard(image_bgr.shape, points, face_box, hair_mask)
    head = _head_envelope(image_bgr.shape, hair_mask, face_box, points)

    m_external = (hair_soft > 0.4) * (1.0 - head)
    m_external[face_guard > 0] = 0.0

    shortness = _shortness_field(image_bgr.shape, hair_soft, face_box, points)
    m_side = shortness * head * hair_soft
    m_side[face_guard > 0] = 0.0

    bg_plate = _background_plate(image_bgr, hair_mask, face_guard, face_box, points)
    background_clean = image_bgr.copy()
    if bg_plate is not None:
        locks = (m_external > 0.5).astype(np.uint8)
        if locks.sum() > 100:
            background_clean[locks > 0] = bg_plate.astype(np.uint8)
            edges = cv2.dilate(locks, np.ones((9, 9), np.uint8)) - locks
            background_clean = cv2.inpaint(
                background_clean, edges * 255, 3, cv2.INPAINT_TELEA
            )

    hair_pixels = image_bgr[hair_mask > 0]
    hair_lab = _lab_median(hair_pixels)
    scalp_pixels = image_bgr[_scalp_roi(image_bgr, face_box, points, hair_mask) > 0]
    scalp_lab = _lab_median(scalp_pixels)

    replaced = image_bgr.astype(np.float32)
    replaced[hair_mask > 127] = scalp_pixels.reshape(-1, 3).mean(axis=0).astype(np.uint8) if len(scalp_pixels) else 0
    lighting_gray = cv2.cvtColor(replaced.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
    lighting_gray = cv2.GaussianBlur(lighting_gray, (0, 0), max(8.0, h / 16.0))
    zone = lighting_gray[m_side > 0.3]
    light_norm = lighting_gray / max(np.median(zone) if zone.size else 128.0, 1.0)

    dist_inside = cv2.distanceTransform((hair_soft > 0.5).astype(np.uint8), cv2.DIST_L2, 5)
    coverage = np.clip(dist_inside / (0.22 * fh), 0.0, 1.0)
    pigment_mix = 0.45 + 0.45 * coverage

    lab_layer = np.empty((h, w, 3), np.float32)
    for channel in range(3):
        base = scalp_lab[channel] * (1.0 - pigment_mix) + hair_lab[channel] * pigment_mix
        lab_layer[..., channel] = base
    lab_layer[..., 0] = np.clip(lab_layer[..., 0] * (0.55 + 0.45 * light_norm), 0, 255)

    layer_bgr = cv2.cvtColor(np.clip(lab_layer, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR).astype(np.float32)
    hair_gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    detail = hair_gray - cv2.GaussianBlur(hair_gray, (0, 0), 3.0)
    rng = np.random.default_rng(7)
    fine = (cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 1.0) - 0.5) * 8.0
    layer_bgr += (0.30 * detail[..., None]) + fine[..., None]

    alpha = np.clip(m_side, 0.0, 1.0) * density
    out = background_clean.astype(np.float32)
    out = out * (1.0 - alpha[..., None]) + np.clip(layer_bgr, 0, 255) * alpha[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)


def debug_sheet(image_bgr, hair_mask, face_box, points, style, strength=0.9, templates=None):
    hair_soft = cv2.GaussianBlur(
        (hair_mask > 0).astype(np.float32), (0, 0), max(2.0, float(face_box[2]) / 150.0)
    )
    face_guard = _face_guard(image_bgr.shape, points, face_box, hair_mask)
    head = _head_envelope(image_bgr.shape, hair_mask, face_box, points)
    shortness = _shortness_field(image_bgr.shape, hair_soft, face_box, points)
    m_side = shortness * head * hair_soft
    m_external = (hair_soft > 0.4) * (1.0 - head)
    result = apply_haircut(image_bgr, hair_mask, face_box, points, style, strength)

    def overlay(mask, color):
        canvas = image_bgr.astype(np.float32)
        m = np.clip(mask, 0, 1)[..., None]
        return (canvas * (1.0 - 0.55 * m) + np.array(color, np.float32) * (0.55 * m)).astype(np.uint8)

    panels = [
        (overlay(hair_soft, (80, 220, 80)), "1 hair"),
        (overlay((face_guard > 0).astype(np.float32), (60, 60, 240)), "2 face guard"),
        (overlay(head, (220, 120, 60)), "3 head env"),
        (overlay(m_side, (200, 60, 200)), "4 side zone"),
        (overlay(m_external, (60, 200, 240)), "5 external"),
        (overlay(np.clip(m_side, 0, 1) * float(strength), (40, 140, 255)), "6 alpha"),
        (result, "7 result"),
    ]
    bar = np.full((56, image_bgr.shape[1], 3), 245, np.uint8)
    tiles = []
    for img_p, label in panels:
        b = bar.copy()
        cv2.putText(b, label, (14, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (15, 15, 15), 3)
        tiles.append(np.vstack([b, img_p]))
    return np.hstack(tiles)
