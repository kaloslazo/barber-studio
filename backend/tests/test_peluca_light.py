import numpy as np

from app.core.splatting.hair3d import delight


def test_delight_removes_the_room_gradient_and_keeps_the_strands():
    rng = np.random.default_rng(3)
    h, w = 160, 200
    albedo = 90.0 + 25.0 * (rng.random((h, w)) > 0.5)
    room = np.tile(np.linspace(0.55, 1.45, w), (h, 1))
    image = np.repeat((albedo * room)[..., None], 3, axis=2).astype(np.uint8)
    alpha = np.ones((h, w), np.float32)
    flat = delight(image, alpha, 120.0).astype(np.float32).mean(axis=2)
    left, right = flat[:, :40].mean(), flat[:, -40:].mean()
    before = image.astype(np.float32).mean(axis=2)
    assert abs(right - left) < 0.5 * abs(before[:, -40:].mean() - before[:, :40].mean())
    assert flat.std() > 8.0


def test_delight_leaves_a_capture_without_hair_alone():
    image = np.full((40, 40, 3), 120, np.uint8)
    assert np.array_equal(delight(image, np.zeros((40, 40), np.float32), 50.0), image)


def test_delight_squashes_painted_highlights():
    image = np.full((80, 80, 3), 70, np.uint8)
    image[30:34, 30:50] = 250
    flat = delight(image, np.ones((80, 80), np.float32), 60.0)
    assert flat[30:34, 30:50].mean() < 0.55 * 250
    assert abs(float(flat[:20].mean()) - 70.0) < 8.0


def test_face_colour_loses_thin_seams_but_keeps_wide_features():
    from app.core.splatting.face3d import smooth_color

    ys, xs = np.mgrid[0:80, 0:80]
    pos = np.stack([xs.ravel() * 2.5, ys.ravel() * 2.5, np.zeros(6400)], axis=1)
    color = np.full((80, 80, 3), 0.55)
    color[:, 30] = 0.95
    color[:, 50:58] = 0.2
    out = smooth_color(pos, color.reshape(-1, 3)).reshape(80, 80, 3)
    assert out[:, 30].mean() < 0.68
    assert out[:, 52:56].mean() < 0.3


def test_face_colour_filter_never_turns_sparse_skin_black():
    from app.core.splatting.face3d import smooth_color

    rng = np.random.default_rng(1)
    pos = rng.random((3000, 3)) * [150.0, 190.0, 5.0]
    color = np.tile([0.75, 0.6, 0.5], (3000, 1)) + rng.normal(0, 0.01, (3000, 3))
    out = smooth_color(pos, color)
    assert out.mean(axis=1).min() > 0.45
    assert abs(out.mean() - color.mean()) < 0.03


def test_hull_never_widens_below_its_widest_section_and_drops_row_spikes():
    from app.core.splatting.hair3d import _median_rows, _no_flare

    radius = np.full((40, 6), 0.5)
    radius[10, :] = 0.7
    radius[25:, :] = np.linspace(0.5, 0.65, 15)[:, None]
    flat = _no_flare(radius)
    assert flat[10:].max() <= 0.7 + 1e-9 and flat[25:].max() <= 0.5 + 1e-9
    spiky = np.full((40, 4), 0.5)
    spiky[20, :] = 2.0
    assert _median_rows(spiky, 7).max() < 0.6


def test_face_fusion_ignores_hair_and_outliers_and_never_returns_black():
    from app.core.splatting import face3d

    class Head:
        tri = np.zeros(300, int)

        def place(self, mesh):
            xs, ys = np.meshgrid(np.arange(20) * 4.0 + 10, np.arange(15) * 4.0 + 10)
            pos = np.stack([xs.ravel(), ys.ravel(), np.zeros(300)], axis=1)
            return pos, None, np.full(300, -1.0)

    class View:
        def __init__(self, shade, hair=None):
            self.image = np.full((100, 100, 3), shade, np.uint8)
            self.hair = hair

    hair = np.zeros((100, 100), np.float32)
    hair[:, :50] = 1.0
    skin = View(190)
    hairy = View(20, hair)
    mesh = np.zeros((468, 3))
    mesh[face3d.FAR_EAR] = [90.0, 0.0, 0.0]
    mesh[face3d.NEAR_EAR] = [10.0, 0.0, 0.0]
    colors, under_hair = face3d.fuse_colors(Head(), [skin, hairy], [mesh, mesh], 0)
    assert colors.mean(axis=1).min() > 0.5
    assert under_hair.dtype == bool and under_hair.shape == (300,)


def test_spread_keeps_one_value_per_point_for_a_single_channel():
    from app.core.splatting.face3d import _spread

    rng = np.random.default_rng(0)
    xy = rng.random((5000, 2)) * 300
    values = (xy[:, :1] / 300)
    out, known = _spread(xy, values, np.ones(5000, bool), 40.0)
    assert out.shape == (5000, 1) and known.shape == (5000,)
    assert np.abs(out[:, 0] - values[:, 0]).mean() < 0.2


def test_hlg_video_is_converted_to_ordinary_colours():
    from app.core.splatting.hdr import hlg_to_sdr

    ramp = np.tile(np.linspace(0, 255, 64, dtype=np.uint8)[None, :, None], (4, 1, 3))
    out = hlg_to_sdr(ramp)
    assert out.shape == ramp.shape and out.dtype == np.uint8
    assert (np.diff(out[0, :, 0].astype(int)) >= 0).all()
    assert out[0, 0, 0] == 0 and out[0, -1, 0] <= 255
    skin = np.array([[[130, 145, 169]]], np.uint8)
    converted = hlg_to_sdr(skin)[0, 0]
    assert converted[2] > skin[0, 0, 2] and converted[2] - converted[0] > skin[0, 0, 2] - skin[0, 0, 0]


def test_hair_albedo_is_deepened_and_loses_part_of_its_cast():
    from app.core.splatting.hair3d import HAIR_CHROMA, HAIR_DEEPEN, deepen_hair

    grey_blue = np.array([[0.30, 0.32, 0.40], [0.45, 0.45, 0.45]])
    out = deepen_hair(grey_blue)
    assert 0.75 * grey_blue.mean() < out.mean() < 0.95 * grey_blue.mean()
    assert (out[0, 2] - out[0, 0]) < (grey_blue[0, 2] - grey_blue[0, 0])
    assert np.allclose(out[1], 0.45 * HAIR_DEEPEN)
