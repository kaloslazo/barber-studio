from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.core.faces.blend import pyramid_blend
from app.core.faces.caricature import PRESETS, bulge, caricature, exaggerate
from app.core.faces.mesh import MESH_POINTS, face_triangles, fit_similarity, mean_face, mirror_index
from app.core.faces.warp import affine_maps, warp_mesh
from app.main import app

client = TestClient(app)
SAMPLE = Path(__file__).resolve().parents[2] / "frontend" / "assets" / "samples" / "ejemplo.jpg"


def upload(image, name="image"):
    success, encoded = cv2.imencode(".jpg", image)
    assert success
    return {name: (f"{name}.jpg", encoded.tobytes(), "image/jpeg")}


def sample():
    return cv2.imread(str(SAMPLE))


def face_in(size=400):
    reference = mean_face()
    return (reference * size * 0.18 + size / 2.0).astype(np.float32)


def test_mean_face_is_normalized():
    reference = mean_face()
    assert reference.shape == (MESH_POINTS, 2)
    assert np.allclose(reference.mean(axis=0), 0.0, atol=1e-4)
    assert abs(np.sqrt((reference ** 2).sum(axis=1).mean()) - 1.0) < 1e-3


def test_face_triangles_cover_every_point():
    triangles = face_triangles(False)
    assert len(np.unique(triangles)) == MESH_POINTS
    with_ring = face_triangles(True)
    assert with_ring.max() >= MESH_POINTS


def test_affine_maps_recover_a_known_transform():
    points = face_in()
    matrix = np.array([[1.1, 0.2], [-0.15, 0.9]])
    moved = points @ matrix.T + (5.0, -3.0)
    triangles = face_triangles(False)
    maps = affine_maps(points, moved, triangles)
    ones = np.ones((len(points), 1))
    for index in range(0, len(triangles), 97):
        corner = np.hstack([points[triangles[index]], ones[:3]])
        assert np.allclose(corner @ maps[index], moved[triangles[index]], atol=1e-6)


def test_warp_with_the_same_mesh_is_identity():
    rng = np.random.default_rng(0)
    image = cv2.GaussianBlur(rng.integers(0, 255, (400, 400, 3)).astype(np.uint8), (0, 0), 3)
    points = face_in()
    warped, covered = warp_mesh(image, points, points, face_triangles(False))
    inside = covered > 0
    assert inside.sum() > 10000
    assert np.abs(warped[inside] - image[inside].astype(np.float32)).max() < 1.0


def test_flat_triangles_are_skipped():
    image = np.full((60, 60, 3), 200, np.uint8)
    image[0, 0] = (0, 0, 255)
    points = np.array([[10.0, 10.0], [30.0, 30.0], [50.0, 50.0]], np.float32)
    warped, covered = warp_mesh(image, points, points, np.array([[0, 1, 2]]))
    assert covered.sum() == 0
    assert np.all(np.isfinite(warped))


def test_pyramid_blend_respects_the_mask():
    base = np.full((128, 128, 3), 40.0, np.float32)
    top = np.full((128, 128, 3), 200.0, np.float32)
    assert np.allclose(pyramid_blend(base, top, np.zeros((128, 128), np.float32)), base, atol=1e-3)
    assert np.allclose(pyramid_blend(base, top, np.ones((128, 128), np.float32)), top, atol=1e-3)


def test_bulge_only_moves_points_inside_the_radius():
    points = np.array([[0.0, 0.0], [5.0, 0.0], [50.0, 0.0]])
    moved = bulge(points, np.array([0.0, 0.0]), 10.0, 2.0)
    assert np.allclose(moved[0], [0.0, 0.0])
    assert moved[1, 0] > 5.0
    assert np.allclose(moved[2], points[2])


def test_the_average_face_has_nothing_to_exaggerate():
    points = face_in()
    assert np.allclose(exaggerate(points.astype(np.float64), 2.0), points, atol=1e-3)


def test_fit_similarity_maps_the_average_face_back():
    points = face_in()
    fit = fit_similarity(mean_face(), points)
    assert np.allclose(fit(mean_face()), points, atol=1e-3)


def test_caricature_with_zero_amount_keeps_the_photo():
    image = cv2.GaussianBlur(np.random.default_rng(1).integers(0, 255, (400, 400, 3)).astype(np.uint8), (0, 0), 3)
    for preset in PRESETS:
        result = caricature(image, [face_in()], preset, 0.0)
        assert np.abs(result.astype(int) - image.astype(int)).max() <= 1


def test_faces_live_without_face_returns_the_frame():
    image = np.random.randint(0, 255, (360, 640, 3), np.uint8)
    response = client.post("/api/faces/live", files=upload(image), data={"mode": "caricature"})
    assert response.status_code == 200
    assert response.headers["X-Faces"] == "0"


def test_faces_photo_without_face_returns_422():
    image = np.random.randint(0, 255, (360, 640, 3), np.uint8)
    response = client.post("/api/faces/photo", files=upload(image), data={"mode": "swap"})
    assert response.status_code == 422


def test_faces_rejects_unknown_mode_and_preset():
    assert client.post("/api/faces/photo", files=upload(sample()), data={"mode": "nope"}).status_code == 400
    response = client.post("/api/faces/photo", files=upload(sample()), data={"mode": "caricature", "preset": "nope"})
    assert response.status_code == 400


def test_swap_needs_two_faces():
    response = client.post("/api/faces/photo", files=upload(sample()), data={"mode": "swap"})
    assert response.status_code == 422
    assert "two faces" in response.json()["detail"]


def test_swap_two_people_changes_both_faces_only():
    photo = sample()
    pair = np.hstack([photo, cv2.flip(photo, 1)])
    response = client.post("/api/faces/photo", files=upload(pair), data={"mode": "swap"})
    assert response.status_code == 200
    assert response.headers["X-Faces"] == "2"
    result = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR)
    assert result.shape == pair.shape
    diff = np.abs(result.astype(int) - pair.astype(int)).sum(axis=2)
    w = photo.shape[1]
    assert diff[:, :w].mean() > 1.0 and diff[:, w:].mean() > 1.0
    assert diff[-40:, :].max() < 30


def test_caricature_moves_the_face_and_keeps_the_corners():
    photo = sample()
    response = client.post("/api/faces/photo", files=upload(photo), data={"mode": "caricature", "preset": "eyes", "amount": "1"})
    assert response.status_code == 200
    result = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR)
    diff = np.abs(result.astype(int) - photo.astype(int)).sum(axis=2)
    assert diff.mean() > 0.5
    assert diff[:30, :30].max() < 30


def test_wear_uses_the_saved_face():
    photo = sample()
    response = client.post("/api/faces/source", files=upload(photo))
    assert response.status_code == 200
    response = client.post("/api/faces/photo", files=upload(cv2.flip(photo, 1)), data={"mode": "wear"})
    assert response.status_code == 200
    assert response.headers["X-Faces"] == "1"


def test_fusion_returns_frames_between_two_photos():
    photo = sample()
    files = {**upload(photo), **upload(cv2.flip(photo, 1), "other")}
    response = client.post("/api/faces/fusion", files=files, data={"steps": "5"})
    assert response.status_code == 200
    frames = response.json()["frames"]
    assert len(frames) == 5
    assert all(frame.startswith("data:image/jpeg;base64,") for frame in frames)


def test_fusion_with_one_face_returns_422():
    response = client.post("/api/faces/fusion", files=upload(sample()))
    assert response.status_code == 422


def test_mirror_index_pairs_both_cheeks():
    mirror = mirror_index()
    reference = mean_face()
    assert mirror[1] == 1
    assert (mirror[mirror] == np.arange(MESH_POINTS)).all()
    assert reference[mirror[234], 0] > 0.5 and reference[mirror[454], 0] < -0.5
    reflected = reference[mirror] * (-1.0, 1.0)
    assert np.linalg.norm(reflected - reference, axis=1).mean() < 0.03


def test_tilted_head_still_gets_a_beard():
    photo = sample()
    h, w = photo.shape[:2]
    turn = cv2.getRotationMatrix2D((w / 2, h / 2), 32, 1.0)
    tilted = cv2.warpAffine(photo, turn, (w, h), borderMode=cv2.BORDER_REFLECT)
    response = client.post("/api/beard", files=upload(tilted), data={"style": "goatee"})
    assert response.status_code == 200


def test_small_second_face_is_found_in_tiles():
    photo = sample()
    room = np.full((720, 1280, 3), (110, 110, 115), np.uint8)
    room[100:500, 150:600] = cv2.resize(photo, (450, 400))
    room[300:500, 850:1075] = cv2.resize(cv2.flip(photo, 1), (225, 200))
    response = client.post("/api/faces/photo", files=upload(room), data={"mode": "swap"})
    assert response.status_code == 200
    assert response.headers["X-Faces"] == "2"


def test_profile_photo_asks_to_face_the_camera():
    from app.api.routes import pipeline

    pipeline.apply_beard(sample(), "full", 0.9)
    pipeline.landmark_detector.last_yaw = 70.0
    try:
        pipeline._require_front()
        assert False, "expected a ValueError"
    except ValueError as error:
        assert "Face turned" in str(error)
    pipeline.landmark_detector.last_yaw = 0.0



def test_fusion_mixes_only_the_face():
    from app.core.faces.morph import morph
    from app.core.faces.session import FaceStudio

    photo = sample()
    other = cv2.flip(photo, 1)
    other[:, :, 0] = 255
    studio = FaceStudio()
    face_a = studio.photo.detect(photo)[0]
    face_b = studio.photo.detect(other)[0]
    frames = morph(photo, face_a, other, face_b, 5, 240)
    start, middle = frames[0].astype(np.float32), frames[2].astype(np.float32)
    corner = (slice(0, 40), slice(0, 40))
    assert np.abs(middle[corner] - start[corner]).mean() < 3.0
    center = (slice(100, 140), slice(100, 140))
    assert np.abs(middle[center] - start[center]).mean() > 3.0
