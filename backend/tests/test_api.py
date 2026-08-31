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
