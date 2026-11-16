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


def test_hair_splats_wrap_the_head_from_one_photo():
    from app.core.splatting.hair3d import HairView, build_hair_splats

    image, probabilities, geometry = scene()
    _, alpha = transfer_mask(image, geometry, probabilities)
    face = np.zeros(alpha.shape, np.uint8)
    cv2.fillPoly(face, [geometry["polygon"]], 255)
    rows, meta = build_hair_splats([HairView(image, alpha, face, geometry, 0.0)], budget=8000, mannequin=500)
    hair = rows[:meta["hair"]]
    assert meta["mannequin"] == 500 and rows.shape[1] == 13
    assert (hair[:, 2] > 0.05).any() and (hair[:, 2] < -0.05).any()
    assert np.isfinite(rows).all()


def test_hair_splats_keep_the_colour_of_the_hair():
    from app.core.splatting.hair3d import HairView, build_hair_splats

    image, probabilities, geometry = scene()
    rng = np.random.default_rng(2)
    hair = np.all(image == (30, 30, 35), axis=2)
    brown = np.clip(np.array([40, 70, 110]) * rng.uniform(0.8, 1.2, (hair.sum(), 1)), 0, 255).astype(np.uint8)
    image[hair] = brown
    _, alpha = transfer_mask(image, geometry, probabilities)
    face = np.zeros(alpha.shape, np.uint8)
    cv2.fillPoly(face, [geometry["polygon"]], 255)
    rows, meta = build_hair_splats([HairView(image, alpha, face, geometry, 0.0)], budget=8000, mannequin=0)
    source = image[hair].mean(axis=0)[::-1] / 255.0
    colour = rows[:meta["hair"], 9:12].mean(axis=0)
    assert 0.75 < colour.mean() / source.mean() < 1.0
    assert colour[0] > colour[2]


def test_hair_splats_from_several_angles_form_one_closed_peluca():
    from app.core.splatting.hair3d import HairView, build_hair_splats

    image, probabilities, geometry = scene()
    _, alpha = transfer_mask(image, geometry, probabilities)
    face = np.zeros(alpha.shape, np.uint8)
    cv2.fillPoly(face, [geometry["polygon"]], 255)
    views = [HairView(image, alpha, face, geometry, yaw) for yaw in (-60, -30, 0, 30, 60)]
    rows, meta = build_hair_splats(views, budget=6000, mannequin=0)
    hair = rows[:meta["hair"]]
    assert meta["views"] == 5 and np.isfinite(rows).all()
    assert (hair[:, 2] > 0.1).any() and (hair[:, 2] < -0.1).any()
    assert (hair[:, 0] > 0.1).any() and (hair[:, 0] < -0.1).any()


def test_hair_splats_keep_both_heads_and_dress_the_body():
    from app.core.splatting.hair3d import HairView, _mannequin, build_hair_splats

    image, probabilities, geometry = scene()
    _, alpha = transfer_mask(image, geometry, probabilities)
    face = np.zeros(alpha.shape, np.uint8)
    cv2.fillPoly(face, [geometry["polygon"]], 255)
    view = HairView(image, alpha, face, geometry, 0.0, clothes=(200, 40, 20))
    head = lambda axes: _mannequin(300, np.random.default_rng(1), axes)
    rows, meta = build_hair_splats([view], budget=6000, mannequin=400, head=head, both=True, torso=500)
    hair, faces, mannequin, body = meta["hair"], meta["face"], meta["mannequin"], meta["body"]
    assert (faces, mannequin, body) == (300, 400, 500) and len(rows) == hair + faces + mannequin + body
    torso = rows[hair + faces + mannequin:]
    assert torso[:, 1].mean() < rows[:hair, 1].mean() - 0.3
    assert torso[:, 0].max() - torso[:, 0].min() > rows[:hair, 0].max() - rows[:hair, 0].min()
    assert torso[:, 11].mean() > 2 * torso[:, 9].mean()
    assert np.isfinite(rows).all()
