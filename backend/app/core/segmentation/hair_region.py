import cv2
import numpy as np


def provisional_hair_mask(image_bgr, face_box):
    """Rough hair region: dome prior above the face box, snapped to dark pixels.

    Provisional heuristic until YOLO segmentation replaces it: hair is usually
    darker than skin and background, so we keep only the dark pixels inside the
    dome using an Otsu threshold computed on the head region.
    """
    h, w = image_bgr.shape[:2]
    x, y, fw, fh = [int(v) for v in face_box]

    dome = np.zeros((h, w), np.uint8)
    center = (x + fw // 2, max(0, y - int(fh * 0.15)))
    axis_x = max(1, int(fw * 0.85))
    axis_y = max(1, int(fh * 0.65))
    cv2.ellipse(dome, center, (axis_x, axis_y), 0, 0, 360, 255, -1)
    dome[y + int(fh * 0.1):, :] = 0

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    x0 = max(0, x - fw // 2)
    x1 = min(w, x + fw + fw // 2)
    y0 = max(0, y - int(fh * 0.85))
    y1 = min(h, y + int(fh * 0.15))
    crop = gray[y0:y1, x0:x1]
    threshold, _ = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    dark = np.zeros((h, w), np.uint8)
    dark[y0:y1, x0:x1] = np.where(gray[y0:y1, x0:x1] < threshold, 255, 0).astype(np.uint8)

    mask = cv2.bitwise_and(dome, dark)
    kernel_open = np.ones((5, 5), np.uint8)
    kernel_close = np.ones((15, 15), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_open)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close)

    if (mask > 0).sum() < 0.05 * (dome > 0).sum():
        return dome
    return mask
