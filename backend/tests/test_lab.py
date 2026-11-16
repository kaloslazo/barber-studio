import numpy as np
from fastapi.testclient import TestClient

from app.core.lab.avatar import COLOR_BOX, AnchoredHead, _surface, build_scanned_head, oriented_triangles, smooth_frames
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


def test_smooth_frames_agree_on_a_shared_edge():
    mesh = synthetic_mesh()
    tris = oriented_triangles(mesh)
    edge = {}
    pair = None
    for index, triangle in enumerate(tris):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            key = tuple(sorted((triangle[a], triangle[b])))
            if key in edge:
                pair = (edge[key], index, key)
                break
            edge[key] = index
        if pair:
            break
    first, second, (u, v) = pair

    def middle(tri_index):
        weights = np.array([0.5 if vertex in (u, v) else 0.0 for vertex in tris[tri_index]])
        return weights[None, :]

    normal_a = smooth_frames(mesh, tris, np.array([first]), middle(first))[0][:, 2]
    normal_b = smooth_frames(mesh, tris, np.array([second]), middle(second))[0][:, 2]
    assert np.allclose(normal_a, normal_b, atol=1e-9)


def test_lab_color_correction_stays_near_the_fused_color():
    rng = np.random.default_rng(3)
    mesh = synthetic_mesh()
    views = [np.clip(rng.normal(128, 40, (480, 640, 3)), 0, 255).astype(np.uint8) for _ in range(3)]
    meshes = [mesh + np.array([shift, 0.0, 0.0]) for shift in (-6.0, 0.0, 6.0)]
    fused, _ = build_scanned_head(views, meshes, budget=3000, iterations=0)
    optimized, _ = build_scanned_head(views, meshes, budget=3000, iterations=12)
    assert np.abs(optimized.color - fused.color).max() <= COLOR_BOX + 1e-6

