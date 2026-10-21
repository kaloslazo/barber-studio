import numpy as np

from app.core.compositing.beard import LiveAnchor, beard_mask, load_templates
from app.core.compositing.beard_physics import BeardPhysics
from app.core.splatting.gaussian_image import fit_gaussians, render_gaussians


def smooth_image():
    ys, xs = np.mgrid[0:96, 0:96].astype(np.float32)
    image = np.stack([xs / 96 * 255, ys / 96 * 255, (xs + ys) / 192 * 255], axis=-1)
    image[30:60, 30:60] = (20, 200, 40)
    return image.astype(np.uint8)


def test_more_gaussians_fit_better():
    image = smooth_image()
    few = fit_gaussians(image, 10, fit_size=64, iterations=60)
    many = fit_gaussians(image, 120, fit_size=64, iterations=60)
    assert many["psnr"] > few["psnr"]
    assert render_gaussians(many, 128).shape == (128, 128, 3)


def face_points():
    template = [t for t in load_templates() if t["category"] == "full"][0]
    pts = np.asarray(template["points"], np.float32)
    scale = 170 / (pts[16, 0] - pts[0, 0])
    return (pts - pts.mean(axis=0)) * scale + np.array([320, 240], np.float32)


def make_physics(pts):
    anchor = LiveAnchor(pts, (480, 640), "full")
    anchor.update(pts)
    anchor.ensure_mesh()
    anchor.cur_ext = anchor.ref_ext.copy()
    region = beard_mask((480, 640), pts, "full")
    face_w = float(np.linalg.norm(pts[16] - pts[0]))
    return anchor, BeardPhysics(anchor, region, pts, face_w)


def test_physics_settles_when_still_and_lags_when_moving():
    pts = face_points()
    anchor, physics = make_physics(pts)
    for _ in range(30):
        physics.step(anchor, 0.1)
    still_lag = physics.tip_lag(anchor)
    shift = np.array([40.0, 0.0], np.float32)
    anchor.update(pts + shift)
    anchor.cur_ext = anchor.ref_ext + shift
    physics.step(anchor, 0.1)
    moving_lag = physics.tip_lag(anchor)
    assert moving_lag > still_lag + 2.0
    for _ in range(40):
        physics.step(anchor, 0.1)
    assert physics.tip_lag(anchor) < moving_lag


def test_physics_render_respects_density():
    pts = face_points()
    anchor, physics = make_physics(pts)
    physics.step(anchor, 0.1)
    _, dense = physics.render((480, 640), (40, 35, 30), 1.0)
    _, sparse = physics.render((480, 640), (40, 35, 30), 0.3)
    assert dense.sum() > sparse.sum() > 0


def test_physics_cut_uses_swept_capsule_and_spawns_debris():
    pts = face_points()
    anchor, physics = make_physics(pts)
    physics.step(anchor, 0.1)
    roots = physics.pos[:, 0]
    left, right = roots[:, 0].min() - 5, roots[:, 0].max() + 5
    y = float(np.median(roots[:, 1]))
    hit = physics.cut((left, y), (right, y), 6.0)
    assert len(hit) > 0
    assert not physics.alive[hit].any()
    assert len(physics.debris_age) == len(hit)
    for _ in range(20):
        physics.step(anchor, 0.1)
    assert len(physics.debris_age) == 0


def test_speedrun_score_rewards_shaving_off_target_only():
    import cv2

    from app.core.game.speedrun import SpeedrunGame, target_mask

    pts = face_points()
    image = np.full((480, 640, 3), 170, np.uint8)
    game = SpeedrunGame("goatee")
    _, found = game.frame(image, pts, None, False, 0.0, (40, 35, 30))
    assert found
    assert game.stats()["score"] == 0
    keep_zone = cv2.dilate(target_mask(image.shape, pts, "goatee"), np.ones((41, 41), np.uint8))
    roots = game.physics.pos[:, 0]
    outside = [r for r in roots if keep_zone[int(r[1]), int(r[0])] == 0]
    for i, root in enumerate(outside):
        game.frame(image, pts, root, True, 0.1 * (i + 1), (40, 35, 30))
        game.prev_tool = None
    stats = game.stats()
    assert stats["clean"] > 0.6
    assert stats["keep"] > 0.95
    assert stats["score"] > 550


def test_speedrun_does_not_cut_when_tool_is_off():
    from app.core.game.speedrun import SpeedrunGame

    pts = face_points()
    image = np.full((480, 640, 3), 170, np.uint8)
    game = SpeedrunGame("mustache")
    game.frame(image, pts, None, False, 0.0, (40, 35, 30))
    for k, root in enumerate(game.physics.pos[:, 0][::5]):
        game.frame(image, pts, root, False, 0.1 * (k + 1), (40, 35, 30))
    assert game.stats()["cuts"] == 0


def synthetic_mesh():
    rng = np.random.default_rng(0)
    angle = rng.uniform(0, 2 * np.pi, 478)
    radius = np.sqrt(rng.uniform(0, 1, 478)) * 120
    x = 320 + radius * np.cos(angle)
    y = 240 + radius * np.sin(angle) * 1.3
    z = -np.sqrt(np.maximum(0, 160 ** 2 - radius ** 2)) + 60
    return np.stack([x, y, z], axis=1).astype(np.float32)


def test_head3d_builds_valid_gaussians():
    from app.core.splatting.head3d import build_head_splats

    image = np.full((480, 640, 3), 140, np.uint8)
    region = np.zeros((480, 640), np.uint8)
    region[300:380, 230:410] = 255
    rows, meta = build_head_splats(image, synthetic_mesh(), region, "full", budget=4000)
    assert rows.shape == (meta["count"], 13)
    assert np.isfinite(rows).all()
    assert meta["face"] > 3000 and meta["backdrop"] > 0 and meta["beard"] > 0
    a, b, c, d, e, f = (rows[:, k] for k in range(3, 9))
    cov = np.stack([np.stack([a, b, c], -1), np.stack([b, d, e], -1), np.stack([c, e, f], -1)], -2)
    assert np.linalg.eigvalsh(cov).min() > -1e-7
    assert ((rows[:, 9:12] >= 0) & (rows[:, 9:12] <= 1)).all()


def test_ply_export_round_trips_covariance():
    from app.core.splatting.head3d import build_head_splats, to_ply

    image = np.full((480, 640, 3), 140, np.uint8)
    rows, meta = build_head_splats(image, synthetic_mesh(), budget=2000)
    blob = to_ply(rows)
    header, body = blob.split(b"end_header\n", 1)
    assert f"element vertex {meta['count']}".encode() in header
    data = np.frombuffer(body, "<f4").reshape(meta["count"], 17)
    scales = np.exp(data[:, 10:13].astype(np.float64))
    w, x, y, z = (data[:, k].astype(np.float64) for k in range(13, 17))
    R = np.stack([
        np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], -1),
        np.stack([2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], -1),
        np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], -1),
    ], -2)
    rebuilt = np.einsum("nij,nj,nkj->nik", R, scales ** 2, R)
    a, b, c, d, e, f = (rows[:, k] for k in range(3, 9))
    original = np.stack([np.stack([a, b, c], -1), np.stack([b, d, e], -1), np.stack([c, e, f], -1)], -2)
    assert np.allclose(rebuilt, original, atol=1e-6, rtol=1e-3)


def test_speedrun_survives_face_outside_the_frame():
    from app.core.game.speedrun import SpeedrunGame

    pts = face_points() + np.array([2000.0, 2000.0], np.float32)
    image = np.full((480, 640, 3), 170, np.uint8)
    game = SpeedrunGame("goatee")
    out, found = game.frame(image, pts, (10.0, 10.0), True, 0.0, (40, 35, 30))
    assert out.shape == image.shape
    assert found is False
    assert game.stats()["score"] == 0


def test_splat_strands_cover_the_strand_and_nothing_else():
    from app.core.compositing.beard_physics import splat_strands

    curve = np.array([[[20.0, 32.0], [30.0, 32.0], [40.0, 32.0]]], np.float32)
    rgb, alpha = splat_strands(curve, np.array([0.6]), np.array([[0.9, 0.9]]), np.array([[30.0, 25.0, 20.0]]), (64, 64))
    assert 0.0 <= alpha.min() and alpha.max() < 1.0
    assert alpha[32, 30] > 0.5
    assert alpha[10, 30] < 1e-3 and alpha[32, 5] < 1e-3
    assert np.allclose(rgb[32, 30], [30.0, 25.0, 20.0], atol=1e-3)
