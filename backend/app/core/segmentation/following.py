from concurrent.futures import ThreadPoolExecutor

import numpy as np

from app.core.segmentation.transfer_mask import follow_head


class FollowingSegmenter:
    """Live segmentation for slow CPUs: the model runs on a worker thread and
    every frame reuses its latest result carried along with the head motion
    (shift, scale, roll), so the video never waits for the model."""

    def __init__(self, segment, on_key=None, max_age=3):
        self._segment = segment
        self._on_key = on_key
        self._max_age = max_age
        self._worker = ThreadPoolExecutor(max_workers=1)
        self._key = None
        self._job = None
        self._generation = 0

    def reset(self):
        self._key = None
        self._job = None
        self._generation += 1

    def _run(self, image_bgr, geometry, yaw, generation):
        probabilities = self._segment(image_bgr, geometry)
        if probabilities is None:
            return None
        return {
            "frame": image_bgr, "geometry": geometry, "yaw": yaw, "probabilities": probabilities,
            "age": 0, "generation": generation,
        }

    def _adopt(self, key, shape):
        if key is None or key["generation"] != self._generation or key["frame"].shape[:2] != shape:
            return
        self._key = key
        if self._on_key is not None:
            self._on_key(key["frame"], key["probabilities"])

    def __call__(self, image_bgr, geometry, yaw):
        job = self._job
        if job is not None and job.done():
            self._job = None
            try:
                self._adopt(job.result(), image_bgr.shape[:2])
            except Exception:
                pass
        key = self._key
        if key is not None and key["frame"].shape[:2] != image_bgr.shape[:2]:
            key = self._key = None
        stale = key is None or key["age"] >= self._max_age
        if key is not None and not stale:
            moved = np.hypot(*np.subtract(geometry["center"], key["geometry"]["center"])) / geometry["face_w"]
            stale = moved > 0.1 or abs(yaw - key["yaw"]) > 8
        if stale and self._job is None:
            self._job = self._worker.submit(self._run, image_bgr.copy(), geometry, yaw, self._generation)
        if key is None:
            job, self._job = self._job, None
            self._adopt(job.result(), image_bgr.shape[:2])
            key = self._key
            if key is None:
                return None
        key["age"] += 1
        return follow_head(key["probabilities"], key["geometry"], geometry)
