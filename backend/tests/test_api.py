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
    assert b"BarberStudio" in response.content


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
    assert response.headers["content-type"] == "image/png"


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


def test_haircut_disabled_style_returns_400():
    response = client.post(
        "/api/haircut",
        files=to_upload(make_test_image()),
        data={"style": "mid-fade"},
    )
    assert response.status_code == 400
    assert "disabled" in response.json()["detail"]


def _haircut_fixture():
    import cv2

    from app.core.compositing.haircut import apply_haircut

    rng = np.random.default_rng(3)
    image = rng.integers(0, 255, (240, 320, 3), dtype=np.uint8)
    mask = np.zeros((240, 320), np.uint8)
    mask[40:120, 110:210] = 255
    face_box = (90, 100, 140, 110)
    return image, mask, face_box, apply_haircut


def test_haircut_zero_strength_is_identity():
    image, mask, face_box, apply_haircut = _haircut_fixture()
    result = apply_haircut(image, mask, face_box, None, "low-fade", 0.0)
    assert np.array_equal(result, image)


def test_haircut_does_not_touch_pixels_outside_hair():
    image, mask, face_box, apply_haircut = _haircut_fixture()
    result = apply_haircut(image, mask, face_box, None, "low-fade", 1.0)
    far_outside = np.zeros_like(mask)
    far_outside[160:230, 10:80] = 255
    assert np.array_equal(result[far_outside > 0], image[far_outside > 0])


def test_haircut_fade_never_touches_face_hull():
    image, mask, face_box, apply_haircut = _haircut_fixture()
    from app.core.compositing.haircut import _face_guard

    result = apply_haircut(image, mask, face_box, None, "low-fade", 1.0)
    guard = _face_guard(image.shape, None, face_box)
    guard_area = guard > 0
    if guard_area.sum():
        assert np.array_equal(result[guard_area], image[guard_area])


def test_haircut_buzz_disabled_raises():
    image, mask, face_box, apply_haircut = _haircut_fixture()
    import pytest

    with pytest.raises(ValueError):
        apply_haircut(image, mask, face_box, None, "buzz", 1.0)
