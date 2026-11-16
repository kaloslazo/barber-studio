import json

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.api import routes
from app.main import app

client = TestClient(app)


def upload():
    success, encoded = cv2.imencode(".jpg", np.full((480, 640, 3), 128, np.uint8))
    assert success
    return {"image": ("frame.jpg", encoded.tobytes(), "image/jpeg")}


def test_debug_frames_are_kept_and_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "LIVE_DEBUG_DIR", tmp_path)
    routes.live_debug.clear()
    for _ in range(3):
        response = client.post("/api/live", files=upload(), data={"mode": "beard", "style": "full", "debug": "1"})
        assert response.status_code == 200
        assert response.headers["X-Face-Found"] == "0"
    saved = client.post("/api/live/debug/save")
    assert saved.status_code == 200 and saved.json()["frames"] == 3
    folder = next(tmp_path.iterdir())
    assert sorted(p.name for p in folder.glob("00*_in.jpg")) == ["000_in.jpg", "001_in.jpg", "002_in.jpg"]
    assert len(list(folder.glob("00*_clean.jpg"))) == 3
    meta = json.loads((folder / "meta.json").read_text())
    assert [m["source"] for m in meta] == ["sin cara"] * 3


def test_nothing_is_kept_without_debug(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "LIVE_DEBUG_DIR", tmp_path)
    routes.live_debug.clear()
    client.post("/api/live", files=upload(), data={"mode": "beard", "style": "full"})
    assert len(routes.live_debug) == 0
    assert client.post("/api/live/debug/save").status_code == 409
