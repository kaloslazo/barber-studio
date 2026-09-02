"""Harvests real beard templates from CelebAMask-HQ into backend/app/assets/beards.

Selects bearded male photos via the attribute annotations, fits our landmark
pipeline (YuNet + LBF), cuts the lower-face beard texture with a feathered
alpha mask, and stores each template as a compact .npz containing the BGRA
crop, its 68 landmarks (crop-relative) and skin-tone statistics for matching.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.compositing.alpha import inside_feather
from app.core.compositing.beard import beard_mask
from app.core.detection.landmarks import LandmarkDetector

REPO = Path(__file__).resolve().parents[2]
ATTR_PATH = REPO / "data/celebamask-raw/CelebAMask-HQ/CelebAMask-HQ-attribute-anno.txt"
IMAGES_DIR = REPO / "data/celebamask-raw/CelebAMask-HQ/CelebA-HQ-img"
ANNO_DIR = REPO / "data/celebamask-raw/CelebAMask-HQ/CelebAMask-HQ-mask-anno"
OUT_DIR = Path(__file__).resolve().parents[1] / "app/assets/beards"

FACE_PARTS = ("skin", "nose", "mouth", "l_lip", "u_lip", "l_ear", "r_ear")


def load_part_masks(image_id, image_shape):
    """Face union (no neck) + neck + skin masks for a CelebAMask-HQ image."""
    bucket = ANNO_DIR / str(image_id // 2000)

    def read_part(part):
        path = bucket / f"{image_id:05d}_{part}.png"
        if not path.exists():
            return None
        mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if mask is not None and mask.shape != image_shape:
            mask = cv2.resize(mask, (image_shape[1], image_shape[0]), interpolation=cv2.INTER_NEAREST)
        return mask

    face = None
    for part in FACE_PARTS:
        mask = read_part(part)
        if mask is not None:
            face = mask if face is None else cv2.bitwise_or(face, mask)
    neck = read_part("neck")
    skin = read_part("skin")
    if face is None or skin is None:
        return None, None, None
    return face, neck, skin

ATTR_INDEX = {
    "5_o_Clock_Shadow": 0,
    "Black_Hair": 8,
    "Blurry": 10,
    "Brown_Hair": 11,
    "Goatee": 16,
    "Gray_Hair": 17,
    "Male": 20,
    "Mustache": 22,
    "No_Beard": 24,
    "Sideburns": 30,
    "Wearing_Hat": 35,
}


def load_candidates(limit_per_category=12):
    with open(ATTR_PATH) as file:
        lines = file.read().splitlines()
    categories = {"full": [], "goatee": [], "mustache": [], "stubble": []}
    for line in lines[2:]:
        parts = line.split()
        if len(parts) < 41:
            continue
        filename, attrs = parts[0], parts[1:]
        try:
            flags = {name: int(attrs[i]) for name, i in ATTR_INDEX.items()}
        except (ValueError, IndexError):
            continue
        if flags["Male"] != 1 or flags["Wearing_Hat"] == 1 or flags["Blurry"] == 1:
            continue
        if flags["Goatee"] == 1:
            categories["goatee"].append((flags["Mustache"] + flags["Sideburns"], filename))
        elif flags["Mustache"] == 1 and flags["No_Beard"] == 1:
            categories["mustache"].append((flags["Sideburns"], filename))
        elif flags["5_o_Clock_Shadow"] == 1 and flags["No_Beard"] == 1:
            categories["stubble"].append((flags["Sideburns"], filename))
        elif flags["No_Beard"] == -1:
            categories["full"].append((flags["Mustache"] + flags["Sideburns"], filename))
    candidates = []
    for category, entries in categories.items():
        taken = [name for _, name in sorted(entries, reverse=True)[:limit_per_category]]
        candidates += [(category, name) for name in taken]
    return candidates


def cheek_skin_ycrcb(image_bgr, points):
    pts = np.asarray(points, np.float32)
    nose_len = np.linalg.norm(pts[30] - pts[27])
    radius = max(3, int(nose_len * 0.28))
    samples = [
        pts[29],
        pts[27] + np.array([0.0, -nose_len * 0.55]),
    ]
    ycrcb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2YCrCb).astype(np.float32)
    values = []
    for center in samples:
        x, y = int(center[0]), int(center[1])
        patch = ycrcb[max(0, y - radius):y + radius, max(0, x - radius):x + radius]
        if patch.size:
            values.append(patch.reshape(-1, 3).mean(axis=0))
    return np.median(np.asarray(values), axis=0)


def build_template(image_bgr, points, detector, image_id, style):
    from app.core.compositing.beard import STYLES

    pts = np.asarray(points, np.float32)
    face_mask, neck_mask, skin_mask = load_part_masks(image_id, image_bgr.shape[:2])
    if face_mask is None or skin_mask is None:
        return None

    mask = beard_mask(image_bgr.shape, pts, style)
    if (mask > 0).mean() < 0.004:
        return None

    face_w = np.linalg.norm(pts[16] - pts[0])
    feather = max(3.0, min(14.0, face_w / 26.0))
    region_alpha = inside_feather(mask, feather)

    ycrcb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2YCrCb).astype(np.float32)
    skin_pixels = ycrcb[skin_mask > 0]
    if len(skin_pixels) < 200:
        return None
    skin = np.median(skin_pixels, axis=0)

    y_channel = ycrcb[..., 0]
    local_ref = cv2.GaussianBlur(y_channel, (0, 0), max(5.0, face_w / 6.0))
    hair_alpha = np.clip((local_ref - 10.0 - y_channel) / 14.0, 0.0, 1.0)
    hair_alpha = np.power(hair_alpha, 1.15)
    hair_alpha = cv2.GaussianBlur(hair_alpha, (0, 0), 1.4)
    valid_zone = (face_mask > 0)
    if neck_mask is not None:
        valid_zone = valid_zone | (neck_mask > 0)
    hair_alpha[~valid_zone] = 0.0

    blob = (hair_alpha > 0.3).astype(np.uint8)
    blob_dist = cv2.distanceTransform(blob, cv2.DIST_L2, 5)
    edge_falloff = np.clip(blob_dist / max(3.0, face_w / 70.0), 0.0, 1.0)
    hair_alpha = hair_alpha * edge_falloff

    center_x = int(pts[33][0])
    left_cov = (hair_alpha[:, :center_x] > 0.15).sum()
    right_cov = (hair_alpha[:, center_x:] > 0.15).sum()
    asym = abs(left_cov - right_cov) / max(left_cov + right_cov, 1)
    if asym > 0.25:
        return None

    region_px = (mask > 0) & valid_zone

    inside_region = (mask > 0) & valid_zone
    if inside_region.sum() < 1500:
        return None
    if skin[0] - y_channel[inside_region].mean() < STYLES[style]["min_contrast"]:
        return None
    min_coverage = 0.10 if style == "stubble" else 0.25
    if (hair_alpha[inside_region] > 0.5).mean() < min_coverage:
        return None

    alpha = (region_alpha * hair_alpha * 255).astype(np.uint8)
    if (alpha > 40).sum() < 2500:
        return None

    left_cov = (alpha[:, :center_x] > 40).sum()
    right_cov = (alpha[:, int(center_x):] > 40).sum()
    if abs(left_cov - right_cov) / max(left_cov + right_cov, 1) > 0.25:
        return None

    x0, y0 = pts[:, 0].min(), pts[:, 1].min()
    x1, y1 = pts[:, 0].max(), pts[:, 1].max()
    pad_x = int((x1 - x0) * 0.12)
    pad_y = int((y1 - y0) * 0.12)
    h, w = image_bgr.shape[:2]
    cx0, cy0 = max(0, int(x0) - pad_x), max(0, int(y0) - pad_y)
    cx1, cy1 = min(w, int(x1) + pad_x), min(h, int(y1) + pad_y)

    bgra = np.dstack([image_bgr[cy0:cy1, cx0:cx1], alpha[cy0:cy1, cx0:cx1]])
    crop_points = pts - np.array([cx0, cy0], np.float32)
    return bgra, crop_points.astype(np.float32), skin.astype(np.float32)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.npz"):
        old.unlink()

    detector = LandmarkDetector()
    candidates = load_candidates()
    print(f"candidates from attributes: {len(candidates)}")

    saved = {}
    for category, filename in candidates:
        if saved.get(category, 0) >= 5:
            continue
        path = IMAGES_DIR / filename
        image = cv2.imread(str(path))
        if image is None:
            continue
        try:
            image_id = int(filename.split(".")[0])
        except ValueError:
            continue
        points = detector.landmarks(image)
        if points is None:
            continue
        template = build_template(image, points, detector, image_id, category)
        if template is None:
            continue
        bgra, crop_points, skin = template
        count = saved.get(category, 0)
        out_path = OUT_DIR / f"beard_{category}_{count:02d}.npz"
        np.savez_compressed(out_path, bgra=bgra, points=crop_points, skin_ycrcb=skin)
        print(f"saved {out_path.name} from {filename} ({bgra.shape[1]}x{bgra.shape[0]})")
        saved[category] = count + 1

    print(f"done: {saved} templates in {OUT_DIR}")


if __name__ == "__main__":
    main()
