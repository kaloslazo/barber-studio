import cv2
import numpy as np

from app.core.geometry.delaunay import delaunay_triangles
from app.core.geometry.warp import warp_template

try:
    from pathlib import Path
    ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets/haircuts"
except ImportError:
    ASSETS_DIR = None

STYLES = {
    "low-fade": {"side_start": 0.50, "side_full": 0.85},
}
DISABLED_STYLES = ("mid-fade", "high-fade", "buzz")


def _smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def hair_virtual_points(points, hair_mask, face_box):
    """14 observed hair anchors: 7 hairline samples, 5 crown samples, 2 ears.
    Built identically on donors and users from their own masks/landmarks."""
    x, y, fw, fh = [float(v) for v in face_box]
    pts68 = np.asarray(points, np.float32)
    hair = (hair_mask > 0).astype(np.uint8)
    h, w = hair.shape
    brow_y = float((pts68[19][1] + pts68[24][1]) / 2.0)
    virtuals = []

    def column_band(px, radius=10):
        w0 = max(0, int(px) - radius)
        w1 = min(w, int(px) + radius)
        return hair[:, w0:w1]

    for t in np.linspace(0.15, 0.85, 7):
        px = int(x + t * fw)
        band = column_band(px)
        rows = np.where(band.any(axis=1))[0]
        if len(rows):
            virtuals.append((px, float(rows.min()) - 2.0))
        else:
            virtuals.append((px, brow_y - fh * 0.40))

    for t in np.linspace(0.30, 0.70, 5):
        px = int(x + t * fw)
        band = column_band(px)
        rows = np.where(band.any(axis=1))[0]
        if len(rows):
            virtuals.append((px, float(rows.max()) + 2.0))
        else:
            virtuals.append((px, y - fh * 0.60))

    ear_l = (float(pts68[0][0]) - fw * 0.03, float(pts68[0][1]) - fh * 0.28)
    ear_r = (float(pts68[16][0]) + fw * 0.03, float(pts68[16][1]) - fh * 0.28)
    virtuals.extend([ear_l, ear_r])
    return np.vstack([pts68, np.asarray(virtuals, np.float32)])


def _face_guard(shape, points, face_box, hair_mask=None):
    """Face protection: the CONCAVE face oval (jaw arc + brow arc) so the
    sideburn/hair zone beside the jaw stays reachable, plus the forehead
    strip up to the observed hairline."""
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


def _side_zone(shape, hair_soft, face_box, points):
    """Template application zone: temples, sides and sideburns."""
    h, w = shape[:2]
    x, y, fw, fh = [float(v) for v in face_box]
    cfg = STYLES["low-fade"]
    if points is not None:
        pts68 = np.asarray(points, np.float32)
        brow_y = float((pts68[19][1] + pts68[24][1]) / 2.0)
        ear_y = float((pts68[0][1] + pts68[16][1]) / 2.0) - fh * 0.28
        jaw_y = float(pts68[8][1])
    else:
        brow_y = y + fh * 0.30
        ear_y = y + fh * 0.45
        jaw_y = y + fh
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    lateral = np.abs(xs - (x + fw / 2.0)) / max(fw * 0.62, 1.0)
    w_side = _smoothstep((lateral - cfg["side_start"]) / (cfg["side_full"] - cfg["side_start"]))
    w_below = _smoothstep((ear_y - ys) / (fh * 0.35)) * _smoothstep((lateral - 0.30) / 0.30)
    zone = np.maximum(w_side, w_below)
    return np.clip(zone * hair_soft, 0.0, 1.0)


def _lab_stats(pixels_bgr):
    lab_pixels = cv2.cvtColor(
        pixels_bgr.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2LAB
    ).astype(np.float32).reshape(-1, 3)
    return np.stack([lab_pixels.mean(0), lab_pixels.std(0)], axis=1)


def _match_lab(warped_rgb, warped_alpha, donor_lab, user_lab):
    """Match donor hair luminance mean/std to the user's hair, keep hue close."""
    visible = warped_alpha > 0.3
    if not visible.any():
        return warped_rgb
    lab = cv2.cvtColor(
        np.clip(warped_rgb, 0, 255).astype(np.uint8), cv2.COLOR_BGR2LAB
    ).astype(np.float32)
    k = np.clip(user_lab[:, 1] / np.maximum(donor_lab[:, 1], 1.0), 0.6, 1.6)
    for channel in range(3):
        gain = k[channel] if channel == 0 else 0.7
        lab[..., channel] = np.clip(
            (lab[..., channel] - donor_lab[channel, 0]) * gain + user_lab[channel, 0],
            0,
            255,
        )
    matched = cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
    out = warped_rgb.copy()
    out[visible] = matched[visible].astype(np.float32)
    return out


def load_hair_templates():
    templates = []
    if ASSETS_DIR is None:
        return templates
    for path in sorted(ASSETS_DIR.glob("*.npz")):
        data = np.load(path)
        templates.append(
            {
                "name": path.stem,
                "bgra": data["bgra"],
                "points": data["points"],
                "lab": data["lab"],
            }
        )
    return templates


def apply_haircut(image_bgr, hair_mask, face_box, points, style, strength, templates=None):
    """Low fade via a real short-hair template warped with Delaunay:
    top hair preserved, template only on temples/sides/sideburns, external
    hanging locks inpainted. Falls back to the untouched original when the
    template data is missing or geometry is unreliable."""
    if style not in STYLES:
        raise ValueError(f"Style '{style}' is temporarily disabled")
    density = float(np.clip(strength, 0.0, 1.0))
    if density <= 0.0:
        return image_bgr.copy()
    if not templates or points is None:
        return image_bgr.copy()

    h, w = image_bgr.shape[:2]
    fw, fh = float(face_box[2]), float(face_box[3])
    template = templates[0]

    hair_soft = cv2.GaussianBlur(
        (hair_mask > 0).astype(np.float32), (0, 0), max(2.0, fw / 150.0)
    )
    face_guard = _face_guard(image_bgr.shape, points, face_box, hair_mask)
    guard_soft = cv2.GaussianBlur(
        (face_guard > 0).astype(np.float32), (0, 0), max(2.0, fh / 90.0)
    )

    src_points = template["points"]
    dst_points = hair_virtual_points(points, hair_mask, face_box)
    triangles = delaunay_triangles(dst_points)
    warped = warp_template(template["bgra"], src_points, dst_points, triangles, (h, w))
    warped_rgb = warped[..., :3]
    warped_alpha = warped[..., 3] / 255.0

    hair_pixels = image_bgr[hair_mask > 0]
    if len(hair_pixels) < 100:
        return image_bgr.copy()
    user_lab = _lab_stats(hair_pixels)
    matched_rgb = _match_lab(warped_rgb, warped_alpha, template["lab"], user_lab)

    side = _side_zone(image_bgr.shape, hair_soft, face_box, points)
    alpha = np.clip(warped_alpha * side * density * (1.0 - guard_soft), 0.0, 1.0)
    alpha[face_guard > 0] = 0.0

    warped_binary = (warped_alpha > 0.3).astype(np.uint8)
    external_hair = ((hair_mask > 0) & (cv2.dilate(warped_binary, np.ones((51, 51), np.uint8)) == 0)).astype(np.uint8)
    external_hair[face_guard > 0] = 0
    inpaint_mask = (external_hair > 0).astype(np.uint8) * 255
    inpaint_mask = cv2.dilate(inpaint_mask, np.ones((5, 5), np.uint8))
    safe = (inpaint_mask & face_guard).sum() == 0 and (inpaint_mask > 0).sum() < 0.12 * h * w
    base = image_bgr.copy()
    if safe and (inpaint_mask > 0).sum() > 150:
        base = cv2.inpaint(base, inpaint_mask, 5, cv2.INPAINT_TELEA)

    out = base.astype(np.float32)
    out = out * (1.0 - alpha[..., None]) + matched_rgb * alpha[..., None]

    top_keep = np.clip(1.0 - side, 0.0, 1.0) * hair_soft
    out = out * (1.0 - top_keep[..., None]) + image_bgr.astype(np.float32) * top_keep[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)


def debug_sheet(image_bgr, hair_mask, face_box, points, style, strength=0.9, templates=None):
    hair_soft = cv2.GaussianBlur(
        (hair_mask > 0).astype(np.float32), (0, 0), max(2.0, float(face_box[2]) / 150.0)
    )
    face_guard = _face_guard(image_bgr.shape, points, face_box, hair_mask)
    side = _side_zone(image_bgr.shape, hair_soft, face_box, points)
    warped_alpha = np.zeros_like(hair_soft)
    if templates and points is not None:
        template = templates[0]
        dst_points = hair_virtual_points(points, hair_mask, face_box)
        triangles = delaunay_triangles(dst_points)
        warped = warp_template(
            template["bgra"], template["points"], dst_points, triangles, image_bgr.shape
        )
        warped_alpha = warped[..., 3] / 255.0
    warped_binary = (warped_alpha > 0.3).astype(np.uint8)
    external = ((hair_mask > 0) & (cv2.dilate(warped_binary, np.ones((51, 51), np.uint8)) == 0)).astype(np.float32)
    alpha = np.clip(warped_alpha * side * float(strength), 0.0, 1.0)
    alpha[face_guard > 0] = 0.0
    result = apply_haircut(image_bgr, hair_mask, face_box, points, style, strength, templates)

    def overlay(mask, color):
        canvas = image_bgr.astype(np.float32)
        m = np.clip(mask, 0, 1)[..., None]
        return (canvas * (1.0 - 0.55 * m) + np.array(color, np.float32) * (0.55 * m)).astype(np.uint8)

    panels = [
        (overlay(hair_soft, (80, 220, 80)), "1 user hair"),
        (overlay((face_guard > 0).astype(np.float32), (60, 60, 240)), "2 face guard"),
        (overlay(warped_alpha, (220, 120, 60)), "3 template mask"),
        (overlay(external, (60, 200, 240)), "4 old external"),
        (overlay(np.clip(1.0 - side, 0, 1) * hair_soft, (120, 220, 120)), "5 top keep"),
        (overlay(alpha, (40, 140, 255)), "6 final alpha"),
        (result, "7 result"),
    ]
    bar = np.full((56, image_bgr.shape[1], 3), 245, np.uint8)
    tiles = []
    for img_p, label in panels:
        b = bar.copy()
        cv2.putText(b, label, (14, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (15, 15, 15), 3)
        tiles.append(np.vstack([b, img_p]))
    return np.hstack(tiles)
