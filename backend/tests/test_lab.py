import numpy as np
from fastapi.testclient import TestClient

from app.core.lab.avatar import AnchoredHead, _surface, oriented_triangles
from app.main import app


def synthetic_mesh():
    rng = np.random.default_rng(1)
    angle = rng.uniform(0, 2 * np.pi, 478)
    radius = np.sqrt(rng.uniform(0, 1, 478)) * 120
    x = 320 + radius * np.cos(angle)
    y = 240 + radius * np.sin(angle) * 1.3
    z = -np.sqrt(np.maximum(0, 160 ** 2 - radius ** 2)) + 60
    mesh = np.stack([x, y, z], axis=1)
    mesh[234] = [200.0, 240.0, 0.0]
    mesh[454] = [440.0, 240.0, 0.0]
    return mesh


def rotation(yaw):
    c, s = np.cos(yaw), np.sin(yaw)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def test_anchored_gaussians_follow_a_rigid_head_motion():
    mesh = synthetic_mesh()
    head = AnchoredHead(mesh, oriented_triangles(mesh))
    _surface(head, np.random.default_rng(0), 3000)
    pos0, cov0, facing0 = head.place(mesh)
    assert (facing0 < 0).mean() > 0.95
    R = rotation(0.4)
    center = mesh.mean(axis=0)
    moved = (mesh - center) @ R.T + center + np.array([15.0, -8.0, 4.0])
    pos1, cov1, _ = head.place(moved)
    expected = (pos0 - center) @ R.T + center + np.array([15.0, -8.0, 4.0])
    assert np.allclose(pos1, expected, atol=1e-6)
    assert np.allclose(cov1, np.einsum("ij,njk,lk->nil", R, cov0, R), atol=1e-6)


def test_lab_endpoints_without_face_or_model():
    client = TestClient(app)
    image = np.random.randint(0, 255, (240, 320, 3), np.uint8)
    import cv2

    ok, encoded = cv2.imencode(".jpg", image)
    files = [("frames", ("a.jpg", encoded.tobytes(), "image/jpeg"))]
    assert client.post("/api/lab/build", files=files, data={"beard": "none"}).status_code == 422
    assert client.post("/api/lab/build", files=files, data={"beard": "viking"}).status_code == 400
    response = client.post("/api/lab/mesh", files={"image": ("a.jpg", encoded.tobytes(), "image/jpeg")})
    assert response.status_code == 200
    assert response.json()["mesh"] is None
