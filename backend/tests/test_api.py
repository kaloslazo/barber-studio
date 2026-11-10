import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def make_test_image():
    return np.random.randint(0, 255, (480, 640, 3), np.uint8)


def to_upload(image):
    success, encoded = cv2.imencode(".jpg", image)
    assert success
    return {"image": ("photo.jpg", encoded.tobytes(), "image/jpeg")}


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_serves_frontend():
    response = client.get("/")
    assert response.status_code == 200
    assert b"Fresh" in response.content


def test_preview_returns_image():
    response = client.post("/api/preview", files=to_upload(make_test_image()))
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    decoded = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR)
    assert decoded is not None


def test_dye_without_face_returns_422():
    response = client.post(
        "/api/dye", files=to_upload(make_test_image()), data={"color": "#7a3ba8"}
    )
    assert response.status_code == 422
    assert "No face detected" in response.json()["detail"]


def test_dye_invalid_color_returns_400():
    response = client.post(
        "/api/dye", files=to_upload(make_test_image()), data={"color": "nope"}
    )
    assert response.status_code == 400


def test_beard_without_face_returns_422():
    response = client.post(
        "/api/beard",
        files=to_upload(make_test_image()),
        data={"style": "full", "strength": "0.9"},
    )
    assert response.status_code == 422
    assert "No face" in response.json()["detail"] or "landmark" in response.json()["detail"]


def test_beard_invalid_style_returns_400():
    response = client.post(
        "/api/beard",
        files=to_upload(make_test_image()),
        data={"style": "alien", "strength": "0.9"},
    )
    assert response.status_code == 400


def test_live_returns_image_even_without_face():
    response = client.post(
        "/api/live",
        files=to_upload(make_test_image()),
        data={"mode": "dye", "color": "#7a3ba8", "strength": "0.75"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"


def test_live_invalid_mode_returns_400():
    response = client.post(
        "/api/live",
        files=to_upload(make_test_image()),
        data={"mode": "alien"},
    )
    assert response.status_code == 400


def test_haircut_without_face_returns_422():
    response = client.post(
        "/api/haircut",
        files=to_upload(make_test_image()),
        data={"style": "low-fade", "strength": "0.9"},
    )
    assert response.status_code == 422


def test_haircut_invalid_style_returns_400():
    response = client.post(
        "/api/haircut",
        files=to_upload(make_test_image()),
        data={"style": "mohawk"},
    )
    assert response.status_code == 400


def test_haircut_all_styles_are_enabled():
    for style in ("low-fade", "mid-fade", "high-fade", "buzz"):
        response = client.post(
            "/api/haircut",
            files=to_upload(make_test_image()),
            data={"style": style},
        )
        assert response.status_code == 422


def _haircut_fixture():
    from app.core.compositing.haircut import apply_haircut
    from app.core.segmentation.transfer_mask import head_geometry

    rng = np.random.default_rng(3)
    image = rng.integers(0, 255, (240, 320, 3), dtype=np.uint8)
    mask = np.zeros((240, 320), np.uint8)
    mask[40:120, 110:210] = 255
    geometry = head_geometry(None, (90, 100, 140, 110))
    return image, mask, geometry, apply_haircut


def test_haircut_zero_strength_is_identity():
    image, mask, geometry, apply_haircut = _haircut_fixture()
    result = apply_haircut(image, mask, geometry, "low-fade", 0.0)
    assert np.array_equal(result, image)


def test_haircut_does_not_touch_pixels_far_from_hair():
    image, mask, geometry, apply_haircut = _haircut_fixture()
    result = apply_haircut(image, mask, geometry, "buzz", 1.0)
    assert np.array_equal(result[160:230, 10:80], image[160:230, 10:80])


def test_haircut_never_touches_the_face():
    import cv2

    image, mask, geometry, apply_haircut = _haircut_fixture()
    face = np.zeros(mask.shape, np.uint8)
    cv2.fillPoly(face, [geometry["polygon"]], 255)
    face = cv2.erode(face, np.ones((9, 9), np.uint8))
    for style in ("low-fade", "buzz"):
        result = apply_haircut(image, mask, geometry, style, 1.0)
        assert np.array_equal(result[face > 0], image[face > 0])


def test_haircut_buzz_changes_the_hair():
    image, mask, geometry, apply_haircut = _haircut_fixture()
    result = apply_haircut(image, mask, geometry, "buzz", 1.0)
    changed = np.abs(result.astype(int) - image.astype(int)).sum(axis=2) > 0
    assert changed[mask > 0].mean() > 0.5


def test_haircut_unknown_style_raises():
    import pytest

    image, mask, geometry, apply_haircut = _haircut_fixture()
    with pytest.raises(ValueError):
        apply_haircut(image, mask, geometry, "mohawk", 1.0)


def test_live_physics_returns_image_even_without_face():
    response = client.post(
        "/api/live",
        files=to_upload(make_test_image()),
        data={"mode": "physics", "strength": "0.8"},
    )
    assert response.status_code == 200
    assert response.headers["X-Face-Found"] == "0"


def test_gaussians_returns_renders():
    image = cv2.GaussianBlur(make_test_image(), (0, 0), 6)
    response = client.post(
        "/api/gaussians",
        files=to_upload(image),
        data={"count": "30", "face_crop": "false", "beard": "none"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 30
    assert data["render"].startswith("data:image/jpeg;base64,")
    assert data["ellipses"].startswith("data:image/jpeg;base64,")
    assert data["psnr"] > 0


def test_gaussians_rejects_bad_count():
    response = client.post(
        "/api/gaussians", files=to_upload(make_test_image()), data={"count": "9"},
    )
    assert response.status_code == 400


def test_game_rejects_unknown_target():
    response = client.post("/api/game/start", data={"target": "mohawk"})
    assert response.status_code == 400


def test_game_frame_without_face_returns_state():
    client.post("/api/game/start", data={"target": "goatee"})
    response = client.post(
        "/api/game/frame",
        files=to_upload(make_test_image()),
        data={"pointer_x": "0.5", "pointer_y": "0.5", "pointer_down": "true", "use_hand": "false"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["face"] is False
    assert data["image"].startswith("data:image/jpeg;base64,")
    assert data["target"] == "goatee"


def test_head3d_without_face_returns_422():
    response = client.post("/api/head3d", files=to_upload(make_test_image()), data={"beard": "none"})
    assert response.status_code == 422


def test_head3d_rejects_unknown_beard():
    response = client.post("/api/head3d", files=to_upload(make_test_image()), data={"beard": "viking"})
    assert response.status_code == 400
