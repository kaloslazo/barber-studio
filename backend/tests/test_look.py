from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.core.compositing.look import apply_look
from app.main import app

client = TestClient(app)
SAMPLE = Path(__file__).resolve().parents[2] / "frontend" / "assets" / "samples" / "ejemplo.jpg"


def upload(image):
    success, encoded = cv2.imencode(".jpg", image)
    assert success
    return {"image": ("photo.jpg", encoded.tobytes(), "image/jpeg")}


class Recorder:
    """Stands in for the pipeline and writes down the order of the steps."""

    def __init__(self, dye_fails=False):
        self.steps = []
        self.dye_fails = dye_fails

    def apply_beard(self, image, style, strength):
        self.steps.append(("beard", style))
        return image + 1

    def apply_hair_dye(self, image, color, strength, beard=False, beard_style=None):
        self.steps.append(("dye", color, beard, beard_style))
        if self.dye_fails:
            raise ValueError("No hair detected in the image")
        return image + 1

    def apply_haircut(self, image, style, strength):
        self.steps.append(("cut", style))
        return image + 1


def test_look_goes_beard_then_dye_then_cut():
    recorder = Recorder()
    result, skipped = apply_look(recorder, np.zeros((4, 4, 3), np.uint8), "goatee", "#3d8b3d", "buzz")
    assert [step[0] for step in recorder.steps] == ["beard", "dye", "cut"]
    assert recorder.steps[1] == ("dye", "#3d8b3d", True, "goatee")
    assert skipped == [] and result.max() == 3


def test_look_skips_what_it_cannot_do():
    recorder = Recorder(dye_fails=True)
    result, skipped = apply_look(recorder, np.zeros((4, 4, 3), np.uint8), None, "#1f1f1f", "crew")
    assert skipped == ["dye"]
    assert [step[0] for step in recorder.steps] == ["dye", "cut"]


def test_look_api_applies_the_whole_order():
    photo = cv2.imread(str(SAMPLE))
    response = client.post("/api/look", files=upload(photo), data={"beard": "goatee", "color": "#3d8b3d", "cut": "mid-fade"})
    assert response.status_code == 200
    assert response.headers["X-Skipped"] == ""
    result = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR)
    assert result.shape == photo.shape
    assert np.abs(result.astype(int) - photo.astype(int)).mean() > 2.0


def test_look_api_rejects_bad_input():
    photo = cv2.imread(str(SAMPLE))
    assert client.post("/api/look", files=upload(photo), data={"beard": "nope"}).status_code == 400
    assert client.post("/api/look", files=upload(photo), data={"cut": "nope"}).status_code == 400
    assert client.post("/api/look", files=upload(photo), data={"color": "zzz"}).status_code == 400
    noise = np.random.randint(0, 255, (360, 640, 3), np.uint8)
    assert client.post("/api/look", files=upload(noise), data={"beard": "full"}).status_code == 422
