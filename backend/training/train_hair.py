"""Trains the hair segmentation model (YOLOv8n-seg fine-tuning).

Usage (from backend/ with venv active):
    venv/bin/python training/train_hair.py --epochs 60 --device mps

Devices: mps (Apple Silicon), cuda (NVIDIA/Colab), cpu (slow, fallback).
Weights start from pretrained yolov8n-seg.pt (COCO) and are specialized on
our Figaro1k + CelebAMask-HQ dataset (see prepare_hair_dataset.py).
"""
import argparse
from pathlib import Path

from ultralytics import YOLO

REPO = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description="Train YOLO hair segmentation")
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="mps")
    parser.add_argument("--name", default="hair-v1")
    args = parser.parse_args()

    model = YOLO("yolov8n-seg.pt")
    model.train(
        data=str(REPO / "data" / "yolo-hair" / "hair.yaml"),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=str(Path(__file__).resolve().parent / "runs"),
        name=args.name,
    )


if __name__ == "__main__":
    main()
