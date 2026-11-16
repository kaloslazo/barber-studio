import cv2
import numpy as np

from app.core.splatting import turntable
from app.core.splatting.turn_session import TurnSession

SIZE, RADIUS = 240, 90.0


def sphere(texture, yaw_degrees):
    ys, xs = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    u, v = (xs - SIZE / 2) / RADIUS, (ys - SIZE / 2) / RADIUS
    inside = u * u + v * v < 1.0
    z = np.sqrt(np.clip(1.0 - u * u - v * v, 0.0, 1.0))
    t = np.radians(yaw_degrees)
    x_rot = u * np.cos(t) - z * np.sin(t)
    z_rot = u * np.sin(t) + z * np.cos(t)
    lon = np.arctan2(x_rot, z_rot)
    lat = np.arcsin(np.clip(-v, -1, 1))
    h, w = texture.shape
    map_x = ((lon + np.pi) / (2 * np.pi) * (w - 1)).astype(np.float32)
    map_y = ((0.5 - lat / np.pi) * (h - 1)).astype(np.float32)
    image = cv2.remap(texture, map_x, map_y, cv2.INTER_LINEAR)
    image[~inside] = 0
    return image, inside.astype(np.uint8)


def texture():
    rng = np.random.default_rng(4)
    noise = rng.random((256, 512)).astype(np.float32)
    fine = cv2.GaussianBlur(noise, (0, 0), 0.8)
    return np.clip(255 * (fine - fine.min()) / np.ptp(fine), 0, 255).astype(np.uint8)


def test_tracker_measures_the_turn_of_a_textured_sphere():
    tex = texture()
    tracker = turntable.HeadTracker()
    total, truth = 0.0, 150.0
    for yaw in np.arange(0.0, truth + 1, 6.0):
        image, mask = sphere(tex, yaw)
        step = tracker.step(image, mask)
        assert step is not None
        total += step["delta"]
    assert abs(abs(total) - truth) < 0.15 * truth


def test_solve_yaw_pins_the_drift_with_the_face_and_closes_the_turn():
    rng = np.random.default_rng(2)
    n = 60
    truth = np.arange(n) * 6.0
    deltas = np.concatenate([[0.0], np.full(n - 1, 6.0 * 1.05) + rng.normal(0, 0.6, n - 1)])
    wrapped = turntable.wrap(truth)
    face_ok = np.abs(wrapped) < 45
    face_yaw = np.where(face_ok, wrapped + rng.normal(0, 2.0, n), 0.0)
    solved = turntable.solve_yaw(deltas, np.ones(n), face_yaw, face_ok)
    error = np.abs(turntable.wrap(solved - truth))
    assert error.max() < 9.0
    integrated = np.cumsum(deltas)
    assert error.mean() < np.abs(integrated - truth).mean()


def test_pick_views_takes_the_sharpest_frame_of_every_bin():
    yaw = np.arange(0, 360, 4.0)
    quality = np.where(yaw % 12 == 4, 5.0, 1.0)
    picks = turntable.pick_views(yaw, quality)
    assert len(picks) == 30
    assert all(quality[i] == 5.0 for i in picks)
    fraction, bins = turntable.coverage(yaw[picks])
    assert fraction == 1.0 and len(bins) == 30


def test_session_keeps_the_running_yaw_and_unwraps_the_face():
    session = TurnSession()
    for index in range(30):
        yaw = index * 12.0
        face = float(turntable.wrap(yaw)) if abs(turntable.wrap(yaw)) < 40 else None
        session.add({"delta": 12.0 if index else 0.0, "weight": 1.0}, face, 1.0)
    solved, picks, fraction, bins = session.solve()
    assert fraction > 0.9 and len(picks) >= 28
    assert abs(solved[-1] - solved[0] - 29 * 12.0) < 12.0


def test_turn_store_keeps_frames_and_angles(tmp_path):
    from app.core.splatting import turn_store

    folder = turn_store.save([b"a", b"b"], [0.0, -12.5], root=tmp_path)
    assert sorted(path.name for path in folder.iterdir()) == ["00_+0000.0.jpg", "01_-0012.5.jpg", "angles.json"]


def test_turn_store_never_fails_when_the_disk_cannot_be_written(tmp_path):
    from app.core.splatting import turn_store

    blocked = tmp_path / "blocked"
    blocked.write_bytes(b"")
    assert turn_store.save([b"a"], [0.0], root=blocked) is None


def test_video_endpoint_rejects_a_file_that_is_not_a_video():
    from fastapi.testclient import TestClient

    from app.main import app

    response = TestClient(app).post("/api/turn/video", files={"video": ("nada.mp4", b"no es un video", "video/mp4")})
    assert response.status_code == 422


def test_one_direction_limits_steps_against_a_full_revolution_only():
    steady = np.concatenate([[0.0], np.full(40, 9.0)])
    steady[10] = -12.0
    limited = turntable.one_direction(steady)
    assert limited[10] == turntable.REVERSE_LIMIT and limited[11] == 9.0
    short = np.concatenate([[0.0], np.full(5, 9.0)])
    short[2] = -12.0
    assert np.array_equal(turntable.one_direction(short), short)


def test_measured_turn_is_rescaled_between_two_face_anchors():
    deltas = np.concatenate([[0.0], np.full(20, 8.0)])
    targets = np.zeros(21)
    targets[20] = 200.0
    out = turntable.rescale_between_anchors(deltas, np.array([0, 20]), targets)
    assert abs(out[1:].sum() - 200.0) < 1e-6
    wild = turntable.rescale_between_anchors(deltas, np.array([0, 20]), np.r_[np.zeros(20), 900.0])
    assert np.array_equal(wild, deltas)


def test_splat_endpoint_accepts_a_mirrored_webcam_face(monkeypatch):
    import cv2
    from fastapi.testclient import TestClient

    from app.api import routes
    from app.main import app

    seen = {}

    def fake(images, angles, mannequin, faces, face_key, both=False):
        seen["face"] = faces[0].copy()
        return np.zeros((4, 13), np.float32), {"count": 4, "hair": 2, "views": len(images)}

    monkeypatch.setattr(routes.pipeline, "hair3d_turn", fake)
    image = np.zeros((40, 40, 3), np.uint8)
    image[:, :20] = 255
    ok, encoded = cv2.imencode(".jpg", image)
    data = encoded.tobytes()
    files = [("frames", ("a.jpg", data, "image/jpeg")), ("face_frames", ("f.jpg", data, "image/jpeg"))]
    response = TestClient(app).post("/api/transfer/splat", data={"angles": "0", "turn": "true", "head": "face", "face_mirror": "true"}, files=files)
    assert response.status_code == 200
    assert seen["face"][:, :20].mean() < 60 and seen["face"][:, 20:].mean() > 200
