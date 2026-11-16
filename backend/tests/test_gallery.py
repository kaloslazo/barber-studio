from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.core.faces.gallery import GALLERY_DIR, catalog, into_portrait, is_monochrome, portrait
from app.core.faces.mesh import FaceMeshes, MESH_POINTS
from app.core.faces.paint import kuwahara
from app.main import app

client = TestClient(app)
SAMPLE = Path(__file__).resolve().parents[2] / "frontend" / "assets" / "samples" / "ejemplo.jpg"


def upload(image):
    success, encoded = cv2.imencode(".jpg", image)
    assert success
    return {"image": ("photo.jpg", encoded.tobytes(), "image/jpeg")}


def test_catalog_has_the_seven_portraits_with_their_files():
    assert list(catalog()) == ["lincoln", "marx", "twain", "douglass", "vangogh", "einstein", "nietzsche"]
    for key, entry in catalog().items():
        assert (GALLERY_DIR / f"{key}.jpg").exists()
        assert (GALLERY_DIR / f"{key}-vello.png").exists()
        assert len(entry["points"]) == MESH_POINTS
        assert entry["source"].startswith("https://commons.wikimedia.org/")


def test_old_photos_are_monochrome_and_the_painting_is_not():
    assert is_monochrome(portrait("lincoln")[0])
    assert not is_monochrome(portrait("vangogh")[0])


def test_kuwahara_keeps_flat_areas_and_sharp_edges():
    image = np.zeros((40, 40, 3), np.float32)
    image[:, 20:] = 200.0
    painted = kuwahara(image, 4)
    assert np.allclose(painted[:, :16], 0.0)
    assert np.allclose(painted[:, 24:], 200.0)
    assert set(np.unique(painted[:, 19:21])) <= {0.0, 200.0}


def test_the_portrait_beard_stays_on_top():
    photo = cv2.imread(str(SAMPLE))
    points = FaceMeshes(max_faces=1).detect(photo)[0]
    picture, _, hair = portrait("marx")
    result = into_portrait(photo, points, "marx").astype(int)
    beard = hair > 0.95
    assert beard.sum() > 1000
    assert np.abs(result[beard] - picture.astype(int)[beard]).mean() < 3.0
    assert np.abs(result - picture.astype(int)).mean() > 1.0


def test_gallery_api_lists_and_renders():
    listing = client.get("/api/gallery").json()
    assert len(listing) == 7
    assert "points" not in listing[0]
    photo = cv2.imread(str(SAMPLE))
    response = client.post("/api/gallery", files=upload(photo))
    assert response.status_code == 200
    assert len(response.json()["results"]) == 7
    response = client.post("/api/gallery", files=upload(photo), data={"key": "nietzsche"})
    assert [item["key"] for item in response.json()["results"]] == ["nietzsche"]


def test_gallery_api_rejects_bad_input():
    photo = cv2.imread(str(SAMPLE))
    assert client.post("/api/gallery", files=upload(photo), data={"key": "nope"}).status_code == 400
    noise = np.random.randint(0, 255, (360, 640, 3), np.uint8)
    assert client.post("/api/gallery", files=upload(noise)).status_code == 422
