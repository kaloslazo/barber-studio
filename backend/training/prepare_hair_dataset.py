"""Converts Figaro1k + CelebAMask-HQ into one merged YOLO segmentation dataset.

Reads raw datasets from data/ (already unzipped) and builds:
    data/yolo-hair/
        images/{train,val}
        labels/{train,val}
        hair.yaml

Class 0 = hair. Masks are binarized and traced into polygons (YOLO-seg format).
Images without a hair mask (e.g. bald subjects in CelebA) are optionally kept
as empty-label negatives to reduce false positives.
"""
import argparse
import shutil
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"

FIGARO_ROOT = DATA / "figaro1k" / "Figaro1k"
CELEBA_ROOT = DATA / "celebamask-raw" / "CelebAMask-HQ"

MIN_AREA_RATIO = 0.0005
EPSILON_RATIO = 0.002


def mask_to_polygons(mask):
    binary = np.where(mask > 127, 255, 0).astype(np.uint8)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = binary.shape
    polygons = []
    for contour in contours:
        if cv2.contourArea(contour) < h * w * MIN_AREA_RATIO:
            continue
        epsilon = EPSILON_RATIO * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        if len(approx) < 3:
            continue
        points = approx.reshape(-1, 2).astype(float)
        points[:, 0] /= w
        points[:, 1] /= h
        polygons.append(points)
    return polygons


def write_sample(out_images, out_labels, image_path, polygons):
    image_path = Path(image_path)
    label_path = out_labels / f"{image_path.stem}.txt"
    lines = []
    for poly in polygons:
        coords = " ".join(f"{x:.6f} {y:.6f}" for x, y in poly)
        lines.append(f"0 {coords}")
    label_path.write_text("\n".join(lines) + ("\n" if lines else ""))
    shutil.copy2(image_path, out_images / image_path.name)


def convert_figaro(out_images, out_labels, split):
    src_images = FIGARO_ROOT / "Original" / split
    src_masks = FIGARO_ROOT / "GT" / split
    count = 0
    for image_path in sorted(src_images.glob("*-org.jpg")):
        mask_path = src_masks / image_path.name.replace("-org.jpg", "-gt.pbm")
        if not mask_path.exists():
            continue
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if mask is None:
            continue
        write_sample(out_images, out_labels, image_path, mask_to_polygons(mask))
        count += 1
    return count


def convert_celeba(out_images, out_labels, limit, negatives_ratio=0.05):
    image_dir = CELEBA_ROOT / "CelebA-HQ-img"
    anno_dir = CELEBA_ROOT / "CelebAMask-HQ-mask-anno"
    converted = 0
    negatives = 0
    max_negatives = int(limit * negatives_ratio)
    for idx in range(30000):
        if converted >= limit and negatives >= max_negatives:
            break
        image_path = image_dir / f"{idx}.jpg"
        mask_path = anno_dir / str(idx // 2000) / f"{idx:05d}_hair.png"
        if not image_path.exists():
            continue
        if mask_path.exists():
            if converted >= limit:
                continue
            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            if mask is None or not (mask > 127).any():
                continue
            write_sample(out_images, out_labels, image_path, mask_to_polygons(mask))
            converted += 1
        else:
            if negatives >= max_negatives:
                continue
            write_sample(out_images, out_labels, image_path, [])
            negatives += 1
    return converted, negatives


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DATA / "yolo-hair"))
    parser.add_argument("--celeba-limit", type=int, default=8000)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    args = parser.parse_args()

    out = Path(args.out)
    for split in ("train", "val"):
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)

    figaro_train = convert_figaro(out / "images" / "train", out / "labels" / "train", "Training")
    figaro_val = convert_figaro(out / "images" / "val", out / "labels" / "val", "Testing")
    print(f"figaro: train={figaro_train} val={figaro_val}")

    temp_train_images = out / "images" / "train"
    temp_train_labels = out / "labels" / "train"
    celeba_total, celeba_neg = convert_celeba(temp_train_images, temp_train_labels, args.celeba_limit)
    print(f"celeba: hair={celeba_total} negatives={celeba_neg}")

    total = figaro_train + celeba_total + celeba_neg
    n_val = int(round((figaro_train + celeba_total + celeba_neg) * args.val_ratio)) - figaro_val
    moved = 0
    label_dir = out / "labels" / "train"
    image_dir_train = out / "images" / "train"
    for label_path in sorted(label_dir.glob("*.txt")):
        if moved >= max(0, n_val):
            break
        image_path = image_dir_train / f"{label_path.stem}.jpg"
        if not image_path.exists():
            continue
        shutil.move(str(image_path), out / "images" / "val" / image_path.name)
        shutil.move(str(label_path), out / "labels" / "val" / label_path.name)
        moved += 1
    print(f"moved {moved} extra samples to val")

    yaml_path = out / "hair.yaml"
    yaml_path.write_text(
        f"path: {out.resolve()}\n"
        "train: images/train\n"
        "val: images/val\n"
        "names:\n"
        "  0: hair\n"
    )
    print(f"dataset ready at {out} ({total} samples, yaml at {yaml_path})")


if __name__ == "__main__":
    main()
