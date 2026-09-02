import cv2
import numpy as np

STYLES = {
    "low-fade": {"cut": 0.02, "margin": 0.10, "outside": 0.5},
    "mid-fade": {"cut": 0.06, "margin": 0.18, "outside": 0.7},
    "high-fade": {"cut": 0.12, "margin": 0.30, "outside": 0.9},
    "buzz": {"cut": 0.20, "margin": 0.55, "outside": 1.0, "blur": 3},
}


def _smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _head_dome(shape, face_box, points):
    """Anatomical skull region: ellipse over the face box landmarks."""
    h, w = shape[:2]
    x, y, fw, fh = [int(v) for v in face_box]
    if points is not None:
        pts = np.asarray(points, np.float32)
        brow_y = float((pts[19][1] + pts[24][1]) / 2.0)
        face_w = float(np.linalg.norm(pts[16] - pts[0])) or fw
    else:
        brow_y = y + fh * 0.30
        face_w = float(fw)
    dome_w = face_w * 1.35
    top_y = brow_y - fh * 1.35
    dome = np.zeros((h, w), np.uint8)
    center = (int(x + fw / 2), int((brow_y + top_y) / 2))
    axes = (max(2, int(dome_w / 2)), max(2, int((brow_y - top_y) / 2 + fh * 0.06)))
    cv2.ellipse(dome, center, axes, 0, 0, 360, 255, -1)
    return dome, brow_y


def _scalp_sample_pixels(image_bgr, face_box, points, hair_mask):
    """Reliable skin pixels: forehead and temple ROIs from landmarks,
    never the dilated ring (background contaminated)."""
    h, w = image_bgr.shape[:2]
    x, y, fw, fh = [int(v) for v in face_box]
    roi = np.zeros((h, w), np.uint8)
    if points is not None:
        pts = np.asarray(points, np.float32)
        nose_len = np.linalg.norm(pts[30] - pts[27])
        cx = (pts[19][0] + pts[24][0]) / 2
        forehead_center = (pts[27] + pts[28]) / 2 + np.array([0.0, -nose_len * 0.45])
        r = max(4, int(nose_len * 0.4))
        cv2.circle(roi, (int(forehead_center[0]), int(forehead_center[1])), r, 255, -1)
        for corner in (pts[36], pts[45]):
            temple = corner + np.array([np.sign(corner[0] - cx) * fw * 0.08, -fh * 0.02])
            cv2.circle(roi, (int(temple[0]), int(temple[1])), max(3, int(fw * 0.05)), 255, -1)
    else:
        cv2.rectangle(roi, (x + fw // 4, y + fh // 12), (x + 3 * fw // 4, y + fh // 4), 255, -1)
    roi = cv2.subtract(roi, (hair_mask > 0).astype(np.uint8) * 255)
    return roi


def _scalp_lighting_field(image_bgr, hair_mask, scalp_bgr):
    """Head lighting: hair pixels replaced by scalp tone, heavily smoothed."""
    replaced = image_bgr.astype(np.float32)
    replaced[hair_mask > 127] = scalp_bgr
    field = cv2.cvtColor(replaced.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
    field = cv2.GaussianBlur(field, (0, 0), max(8.0, image_bgr.shape[0] / 18.0))
    median = np.median(field[(hair_mask > 127)])
    if median <= 1:
        median = 128.0
    return field / median


def apply_haircut(image_bgr, hair_mask, face_box, points, style, strength):
    """Real silhouette reduction: hair outside the target mask is removed —
    inside the skull dome it becomes scalp, outside it is background-inpainted.
    The remaining hair keeps its original pixels (tone, texture, lighting)."""
    h, w = image_bgr.shape[:2]
    x, y, fw, fh = [int(v) for v in face_box]
    cfg = STYLES[style]
    density = float(np.clip(strength, 0.0, 1.0))
    if density <= 0.0:
        return image_bgr.copy()

    hair_soft = cv2.GaussianBlur(
        (hair_mask > 0).astype(np.float32), (0, 0), max(2.0, fw / 150.0)
    )

    dome, brow_y = _head_dome(image_bgr.shape, face_box, points)
    dist_inside = cv2.distanceTransform((dome > 0).astype(np.uint8), cv2.DIST_L2, 5)

    cut_t = cfg["cut"] * fh * (0.6 + 0.4 * density)
    softness = fh * 0.16
    keep_prob = _smoothstep((dist_inside - cut_t) / softness)
    keep_prob = np.clip(keep_prob, 0.0, 1.0)

    inside_dome = (dome > 0).astype(np.float32)
    scalp_alpha = np.clip(hair_soft * (1.0 - keep_prob) * inside_dome, 0.0, 1.0) * density

    margin_px = max(3, int(cfg["margin"] * fh))
    outside_zone = cv2.subtract(
        cv2.dilate(dome, np.ones((margin_px * 2 + 1, margin_px * 2 + 1), np.uint8)),
        dome,
    ).astype(np.float32)
    outside_alpha = hair_soft * outside_zone * density * cfg["outside"]
    keep_alpha = np.clip(hair_soft * np.minimum(keep_prob * inside_dome + (1.0 - inside_dome) * (1.0 - outside_zone), 1.0), 0.0, 1.0)

    scalp_roi = _scalp_sample_pixels(image_bgr, face_box, points, hair_mask)
    scalp_pixels = image_bgr[scalp_roi > 0]
    if len(scalp_pixels) < 100:
        region = image_bgr[y:y + fh, x:x + fw].reshape(-1, 3)
        scalp_pixels = region
    scalp_bgr = np.median(scalp_pixels, axis=0).astype(np.float32)

    out = image_bgr.astype(np.float32)

    if "blur" in cfg:
        k = (int(cfg["blur"]) * 2 + 1) | 1
        shortened = cv2.GaussianBlur(image_bgr, (k, k), 0).astype(np.float32)
        buzz_blend = keep_alpha * density * 0.8
        out = out * (1.0 - buzz_blend[..., None]) + shortened * buzz_blend[..., None]

    lighting = _scalp_lighting_field(image_bgr, hair_mask, scalp_bgr)
    rng = np.random.default_rng(4)
    follicle = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 1.0)
    stubble = (follicle > 0.62).astype(np.float32)
    scalp_layer = scalp_bgr[None, None, :] * (0.82 + 0.18 * lighting)[..., None]
    scalp_layer = scalp_layer * (1.0 - 0.35 * stubble * density)[..., None]

    out = out * (1.0 - scalp_alpha[..., None]) + scalp_layer * scalp_alpha[..., None]
    out = np.clip(out, 0, 255).astype(np.uint8)

    inpaint_mask = (outside_alpha > 0.35).astype(np.uint8) * 255
    inpaint_mask = cv2.dilate(inpaint_mask, np.ones((3, 3), np.uint8))
    if (inpaint_mask > 0).sum() > 120:
        out = cv2.inpaint(out, inpaint_mask, 5, cv2.INPAINT_TELEA)
    return out


def debug_masks(image_bgr, hair_mask, face_box, points, style, strength=0.9):
    """The six intermediate masks as a labeled sheet, for visual inspection."""
    h, w = image_bgr.shape[:2]
    x, y, fw, fh = [int(v) for v in face_box]
    cfg = STYLES[style]
    density = float(np.clip(strength, 0.0, 1.0))
    hair_soft = cv2.GaussianBlur((hair_mask > 0).astype(np.float32), (0, 0), max(2.0, fw / 150.0))
    dome, _ = _head_dome(image_bgr.shape, face_box, points)
    dist_inside = cv2.distanceTransform((dome > 0).astype(np.uint8), cv2.DIST_L2, 5)
    cut_t = cfg["cut"] * fh * (0.6 + 0.4 * density)
    keep_prob = np.clip(_smoothstep((dist_inside - cut_t) / (fh * 0.16)), 0.0, 1.0)
    margin_px = max(3, int(cfg["margin"] * fh))
    outside_zone = cv2.subtract(
        cv2.dilate(dome, np.ones((margin_px * 2 + 1, margin_px * 2 + 1), np.uint8)),
        dome,
    ).astype(np.float32)
    removed = np.clip(
        hair_soft * ((1.0 - keep_prob) * (dome > 0) + outside_zone),
        0.0,
        1.0,
    )
    scalp_roi = _scalp_sample_pixels(image_bgr, face_box, points, hair_mask)
    outside = hair_soft * outside_zone * cfg["outside"]

    panels = [
        ("1 hair mask", (hair_mask > 0).astype(np.float32)),
        ("2 skull dome", (dome > 0).astype(np.float32)),
        ("3 keep (target)", hair_soft * keep_prob),
        ("4 removed", removed),
        ("5 scalp sample px", (scalp_roi > 0).astype(np.float32)),
        ("6 bg inpaint zone", outside),
    ]
    cell = 360
    tiles = []
    for label, mask in panels:
        m = (np.clip(mask, 0, 1) * 255).astype(np.uint8)
        tile = cv2.cvtColor(cv2.resize(m, (cell, cell)), cv2.COLOR_GRAY2BGR)
        cv2.rectangle(tile, (0, 0), (cell, 42), (250, 250, 250), -1)
        cv2.putText(tile, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (15, 15, 15), 2)
        tiles.append(tile)
    return np.vstack([np.hstack(tiles[:3]), np.hstack(tiles[3:])])
