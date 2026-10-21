import cv2
import numpy as np

from app.core.compositing.bald import BaldRenderer
from app.core.segmentation.mp_segmenter import BACKGROUND, HAIR
from app.core.segmentation.transfer_mask import follow_head, head_geometry, transfer_mask


def scene():
    image = np.full((480, 640, 3), (120, 140, 160), np.uint8)
    cv2.ellipse(image, (320, 250), (90, 120), 0, 0, 360, (140, 170, 210), -1)
    cv2.ellipse(image, (320, 170), (105, 85), 0, 180, 360, (30, 30, 35), -1)
    cv2.rectangle(image, (20, 20), (90, 460), (30, 30, 35), -1)
    hair = np.zeros(image.shape[:2], np.float32)
    hair[np.all(image == (30, 30, 35), axis=2)] = 1.0
    probabilities = np.zeros((6,) + image.shape[:2], np.float32)
    probabilities[HAIR] = hair
    probabilities[BACKGROUND] = 1.0 - hair
    return image, probabilities, head_geometry(face_box=(230, 150, 180, 220))


def test_transfer_mask_drops_dark_background_away_from_the_head():
    image, probabilities, geometry = scene()
    mask, alpha = transfer_mask(image, geometry, probabilities)
    assert mask[100, 320] == 255
    assert not mask[:, :100].any()
    assert alpha[100, 320] > 0.9 and alpha[300, 50] == 0


def test_follow_head_moves_segmentation_with_the_face():
    _, probabilities, geometry = scene()
    moved = dict(geometry, center=(geometry["center"][0] + 40, geometry["center"][1]))
    warped = follow_head(probabilities, geometry, moved)
    assert warped[HAIR, 100, 360] > 0.9
    assert warped[BACKGROUND, 5, 5] == 1.0


def test_bald_renderer_replaces_hair_with_skin():
    image, probabilities, geometry = scene()
    mask, _ = transfer_mask(image, geometry, probabilities)
    bald = BaldRenderer().render(image, mask, geometry, probabilities)
    assert bald[110, 320].mean() > 100
    assert np.array_equal(bald[300, 50], image[300, 50])
