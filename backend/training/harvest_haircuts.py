"""Harvests short-hair templates from CelebAMask-HQ into backend/app/assets/haircuts.

Selection: male subjects with a SMALL hair mask (short hair), no hats/blur.
Each template stores the BGRA hair crop (CelebA hair mask as alpha), the 68
landmarks PLUS 14 observed hair anchors (hairline, crown, ears), and Lab
color statistics. No face or donor background is included.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.compositing.alpha import inside_feather
from app.core.compositing.haircut import hair_virtual_points
from app.core.detection.landmarks import LandmarkDetector

REPO = Path(__file__).resolve().parents[2]
ATTR_PATH = REPO / "data/celebamask-raw/CelebAMask-HQ/CelebAMask-HQ-attribute-anno.txt"
IMAGES_DIR = REPO / "data/celebamask-raw/CelebAMask-HQ/CelebA-HQ-img"
ANNO_DIR = REPO / "data/celebamask-raw/CelebAMask-HQ/CelebAMask-HQ-mask-anno"
OUT_DIR = Path(__file__).resolve().parents[1] / "app/assets/haircuts"

ATTR_INDEX = {"Bald": 4, "Blurry": 10, "Male": 20, "Wearing_Hat": 35}


def load_hair_mask(image_id, shape):
    path = ANNO_DIR / str(image_id // 2000) / f"{image_id:05d}_hair.png"
    if not path.exists():
        return None
    mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if mask is not None and mask.shape != shape:
        mask = cv2.resize(mask, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
    return mask


def main(target=4):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.npz"):
        old.unlink()

    with open(ATTR_PATH) as file:
        lines = file.read().splitlines()

    detector = LandmarkDetector()
    candidates = []
    for line in lines[2:]:
        parts = line.split()
        if len(parts) < 41:
            continue
        filename, attrs = parts[0], parts[1:]
        try:
            flags = {name: int(attrs[i]) for name, i in ATTR_INDEX.items()}
        except (ValueError, IndexError):
            continue
        if flags["Male"] != 1 or flags["Bald"] == 1 or flags["Wearing_Hat"] == 1 or flags["Blurry"] == 1:
            continue
        candidates.append(filename)

    print(f"male candidates: {len(candidates)}")
    saved = 0
    for filename in candidates:
        if saved >= target:
            break
        image_id = int(filename.split(".")[0])
        image = cv2.imread(str(IMAGES_DIR / filename))
        if image is None:
            continue
        hair = load_hair_mask(image_id, image.shape[:2])
        if hair is None:
            continue
        area_ratio = (hair > 0).mean()
        if not (0.025 <= area_ratio <= 0.065):
            continue
        points = detector.landmarks(image)
        if points is None:
            continue
        hair_box = cv2.boundingRect((hair > 0).astype(np.uint8))
        hx, hy, hw, hh = hair_box
        if hw < 200 or hh < 150:
            continue

        face_box = (
            float(points[:, 0].min()),
            float(points[19:27, 1].min() - (points[8][1] - points[19][1])),
            float(np.linalg.norm(points[16] - points[0])),
            float(points[8][1] - points[19][1]),
        )
        full_points = hair_virtual_points(points, hair, face_box)
        pad = int(max(hw, hh) * 0.06)
        cx0 = max(0, hx - pad)
        cy0 = max(0, hy - pad)
        cx1 = min(image.shape[1], hx + hw + pad)
        cy1 = min(image.shape[0], hy + hh + pad)

        alpha = cv2.GaussianBlur((hair > 0).astype(np.float32), (0, 0), 2.0)
        alpha = alpha * inside_feather((hair > 0).astype(np.uint8) * 255, 8.0)
        bgra = np.dstack([image[cy0:cy1, cx0:cx1], (alpha[cy0:cy1, cx0:cx1] * 255).astype(np.uint8)])
        crop_points = full_points - np.array([cx0, cy0], np.float32)

        hair_pixels = image[hair > 0]
        lab_pixels = cv2.cvtColor(
            hair_pixels.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2LAB
        ).astype(np.float32).reshape(-1, 3)
        lab = np.stack([lab_pixels.mean(0), lab_pixels.std(0)], axis=1).astype(np.float32)

        out_path = OUT_DIR / f"hair_{saved:02d}.npz"
        np.savez_compressed(out_path, bgra=bgra, points=crop_points, lab=lab)
        print(f"saved {out_path.name} from {filename} (hair {100*area_ratio:.1f}%)")
        saved += 1

    print(f"done: {saved} hair templates in {OUT_DIR}")


if __name__ == "__main__":
    main()
