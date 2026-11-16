import cv2
import numpy as np
import pytest

from app.core.compositing import beard_mesh
from app.core.compositing.beard_mesh import MeshBeard, face_triangles

LON, LAT, RADIUS, CENTRE = 18, 26, 150.0, np.array([260.0, 240.0])
SHAPE = (480, 520)


def dome(turn_degrees=0.0):
    lon = np.radians(np.linspace(-80, 80, LON))
    lat = np.radians(np.linspace(-60, 60, LAT))
    lo, la = np.meshgrid(lon, lat, indexing="ij")
    xyz = np.stack([RADIUS * np.cos(la) * np.sin(lo), RADIUS * np.sin(la), -RADIUS * np.cos(la) * np.cos(lo)], axis=-1).reshape(-1, 3)
    t = np.radians(turn_degrees)
    x = xyz[:, 0] * np.cos(t) + xyz[:, 2] * np.sin(t)
    z = -xyz[:, 0] * np.sin(t) + xyz[:, 2] * np.cos(t)
    return np.stack([x + CENTRE[0], xyz[:, 1] + CENTRE[1], z], axis=1)


def dome_triangles():
    index = np.arange(LON * LAT).reshape(LON, LAT)
    a, b, c, d = index[:-1, :-1], index[1:, :-1], index[:-1, 1:], index[1:, 1:]
    return np.concatenate([np.stack([a, b, c], -1).reshape(-1, 3), np.stack([b, d, c], -1).reshape(-1, 3)])


@pytest.fixture
def lower_half(monkeypatch):
    def region(shape, points, style, live=False):
        mask = np.zeros(shape, np.uint8)
        mask[int(CENTRE[1]) + 1:] = 255
        return mask

    monkeypatch.setattr(beard_mesh, "style_region", region)
    monkeypatch.setattr(beard_mesh, "mouth_hole_mask", lambda shape, points, live=False: np.zeros(shape, np.uint8))


def landmarks():
    points = np.zeros((68, 2), np.float32)
    points[16] = (100.0, 0.0)
    return points


def coverage(mesh, triangles):
    out = np.zeros(SHAPE, np.uint8)
    for tri in triangles:
        cv2.fillConvexPoly(out, np.round(mesh[tri, :2]).astype(np.int32), 255)
    return out > 0


def test_face_triangles_come_from_the_mediapipe_tessellation():
    triangles = face_triangles()
    assert 800 <= len(triangles) <= 900
    assert triangles.max() < 468
    assert (np.diff(np.sort(triangles, axis=1), axis=1) > 0).all()


def test_frontal_region_is_the_reference_texture(lower_half):
    mesh, triangles = dome(), dome_triangles()
    beard = MeshBeard(mesh, landmarks(), SHAPE, triangles)
    region = beard.region(mesh, "full", (0, 0), SHAPE, landmarks()) > 0
    expected = coverage(mesh, triangles) & (np.arange(SHAPE[0])[:, None] > CENTRE[1])
    assert (region & expected).sum() / (region | expected).sum() > 0.97


def test_turned_region_follows_the_vertices_and_hides_the_far_side(lower_half):
    beard = MeshBeard(dome(), landmarks(), SHAPE, dome_triangles())
    turned = dome(60.0)
    region = beard.region(turned, "full", (0, 0), SHAPE, landmarks())
    front = np.unique(beard.triangles[beard.visible(turned)])
    xy = np.round(turned[front, :2]).astype(int)
    inside = (xy[:, 0] >= 0) & (xy[:, 0] < SHAPE[1]) & (xy[:, 1] >= 0) & (xy[:, 1] < SHAPE[0])
    lower = turned[front, 1] > CENTRE[1] + 8
    upper = turned[front, 1] < CENTRE[1] - 8
    sampled = region[xy[:, 1].clip(0, SHAPE[0] - 1), xy[:, 0].clip(0, SHAPE[1] - 1)]
    assert (sampled[inside & lower] > 0).mean() > 0.95
    assert (sampled[inside & upper] == 0).all()
    assert 0.25 < (region > 0).sum() / (beard.region(dome(), "full", (0, 0), SHAPE, landmarks()) > 0).sum() < 0.75


def test_back_of_the_mesh_draws_nothing(lower_half):
    beard = MeshBeard(dome(), landmarks(), SHAPE, dome_triangles())
    assert beard.region(dome(180.0), "full", (0, 0), SHAPE, landmarks()).sum() == 0


def test_region_is_cropped_with_its_origin_and_grown(lower_half):
    mesh = dome()
    beard = MeshBeard(mesh, landmarks(), SHAPE, dome_triangles())
    full = beard.region(mesh, "full", (0, 0), SHAPE, landmarks()) > 0
    crop = beard.region(mesh, "full", (100, 120), (200, 300), landmarks()) > 0
    assert (crop != full[120:320, 100:400]).mean() < 0.001
    grown = beard.region(mesh, "full", (0, 0), SHAPE, landmarks(), grow=4) > 0
    assert grown.sum() > full.sum() and (grown & full).sum() == full.sum()


def test_grazing_surface_gets_more_gain_than_a_facing_one(lower_half):
    beard = MeshBeard(dome(), landmarks(), SHAPE, dome_triangles())
    vertex = 9 * LAT + 18

    def gain_at_the_vertex(turn):
        mesh = dome(turn)
        x, y = np.round(mesh[vertex, :2]).astype(int)
        return beard.view(mesh, "full", (0, 0), SHAPE, landmarks())["gain"][y, x]

    assert gain_at_the_vertex(0.0) < 1.25
    assert 1.4 < gain_at_the_vertex(60.0) <= beard_mesh.GAIN_MAX + 1e-3


def test_strands_are_pinned_to_the_surface_and_hidden_with_it(lower_half):
    from app.core.compositing.beard import LiveAnchor

    mesh = dome()
    beard = MeshBeard(mesh, landmarks(), SHAPE, dome_triangles())
    anchor = LiveAnchor(landmarks(), SHAPE, "full")
    view = beard.view(mesh, "full", (0, 0), SHAPE, landmarks())
    anchor.bind(beard, view["xy"], view["front"])
    anchor.build_strands(view["region"], "full")
    assert anchor.strand_valid.mean() > 0.2
    here = anchor.map_origins(len(anchor.strands["origins"]))
    valid = anchor.strand_valid
    assert np.allclose(here[valid], anchor.strands["origins"][valid] + beard.origin, atol=3.0)
    turned = beard.view(dome(180.0), "full", (0, 0), SHAPE, landmarks())
    anchor.bind(beard, turned["xy"], turned["front"])
    assert (anchor.map_origins(len(anchor.strands["origins"])) < -1000).all()


def test_neck_skirt_hangs_below_the_jaw_and_behind_the_chin(lower_half):
    mesh = dome()
    for vertex, position in {10: (260, 90, -150), 152: (260, 390, -150), 4: (260, 240, -150), 234: (110, 240, 0), 454: (410, 240, 0)}.items():
        mesh[vertex] = position
    beard = MeshBeard(mesh, landmarks(), SHAPE)
    skirt = beard.extended(mesh)[beard_mesh.FACE_VERTICES:]
    jaw = mesh[beard_mesh.JAW_LOOP]
    assert skirt.shape == jaw.shape
    assert (skirt[:, 1] > jaw[:, 1]).all() and (skirt[:, 2] > jaw[:, 2]).all()
    assert len(beard.triangles) == beard.face_triangles + 2 * (len(beard_mesh.JAW_LOOP) - 1)


def test_template_detail_carries_no_colour():
    from app.core.compositing.beard import _gradient_detail

    texture = np.zeros((40, 40, 3), np.float32)
    texture[:, 20:] = (200.0, 40.0, 10.0)
    detail = _gradient_detail(texture, 140.0)
    assert detail.shape[-1] == 1 and np.abs(detail).max() > 1.0
