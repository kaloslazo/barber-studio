import threading
import time
from collections import OrderedDict

import numpy as np

from app.core.splatting import turntable

MAX_SESSIONS = 6
FAST_STEP = 14.0


class TurnSession:
    """What the server remembers of one scan while the person turns on the
    chair: one measurement per received frame, the head tracker and a running
    yaw that gives the live feedback (the final angles are solved at the end,
    over the whole chain)."""

    def __init__(self):
        self.tracker = turntable.HeadTracker()
        self.deltas = []
        self.weights = []
        self.face_yaw = []
        self.face_ok = []
        self.quality = []
        self.online = []
        self.created = time.monotonic()

    def add(self, step, face_yaw, quality):
        delta = float(step["delta"]) if step else 0.0
        weight = float(step["weight"]) if step else 0.0
        self.deltas.append(delta)
        self.weights.append(weight)
        self.face_yaw.append(float(face_yaw) if face_yaw is not None else 0.0)
        self.face_ok.append(face_yaw is not None and abs(face_yaw) <= turntable.FACE_ANCHOR_MAX)
        self.quality.append(float(quality))
        previous = self.online[-1] if self.online else 0.0
        if self.face_ok[-1]:
            current = float(turntable.unwrap_face_yaw(previous, self.face_yaw[-1]))
        else:
            current = previous + delta
        self.online.append(current)
        return current, delta

    def covered(self):
        if not self.online:
            return 0.0, []
        return turntable.coverage(np.asarray(self.online))

    def solve(self, bin_degrees=turntable.BIN_DEGREES):
        if len(self.deltas) < 4 or not any(self.face_ok):
            raise ValueError("The scan needs the face in view at least once and a few frames")
        yaw = turntable.solve_yaw(self.deltas, self.weights, self.face_yaw, self.face_ok)
        picks = turntable.pick_views(yaw, self.quality, bin_degrees=bin_degrees)
        fraction, bins = turntable.coverage(yaw, bin_degrees)
        return yaw, picks, fraction, bins


class TurnSessions:
    def __init__(self):
        self.items = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key, create=True):
        with self.lock:
            if key in self.items:
                self.items.move_to_end(key)
                return self.items[key]
            if not create:
                return None
            self.items[key] = TurnSession()
            while len(self.items) > MAX_SESSIONS:
                self.items.popitem(last=False)
            return self.items[key]

    def drop(self, key):
        with self.lock:
            self.items.pop(key, None)
