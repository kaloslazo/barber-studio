import cv2
import numpy as np

FACE_ANCHOR_MAX = 65.0
REVERSE_LIMIT = -1.0
REVOLUTION_MIN = 120.0
RESCALE_RANGE = (0.6, 2.0)
FACE_SIGMA = 4.0
STEP_SIGMA = 1.2
MIN_FEATURES = 12
BIN_DEGREES = 12


def head_extent(mask):
    ys, xs = np.nonzero(mask)
    if len(xs) < 200:
        return None
    left, right = np.percentile(xs, [1.5, 98.5])
    top = np.percentile(ys, 1.0)
    return float((left + right) / 2), float(max((right - left) / 2, 4.0)), float(top)


class HeadTracker:
    """Rotation of a head turning on a swivel chair, frame to frame.

    The head is a sphere turning about a vertical axis: a feature at the
    normalised column u = sin(phi) moves to sin(phi + dtheta), so every
    tracked feature votes for dtheta = asin(u1) - asin(u0) and the median of
    those votes is the turn between two frames. It works with no face in
    view (back of the head), where the face mesh gives no yaw."""

    def __init__(self):
        self.previous = None
        self.centers = []
        self.radii = []

    def reset(self):
        self.previous = None
        self.centers = []
        self.radii = []

    def axis(self, extent):
        self.centers.append(extent[0])
        self.radii.append(extent[1])
        recent_c = self.centers[-9:]
        recent_r = self.radii[-9:]
        return float(np.median(recent_c)), float(np.median(recent_r))

    def step(self, gray, head_mask):
        extent = head_extent(head_mask)
        if extent is None:
            self.previous = None
            return None
        axis_x, radius = self.axis(extent)
        current = {"gray": gray, "axis": axis_x, "radius": radius, "extent": extent}
        before, self.previous = self.previous, current
        if before is None:
            return {"delta": 0.0, "weight": 0.0, "features": 0, "extent": extent}
        inner = cv2.erode(head_mask.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(radius * 0.12) | 1,) * 2))
        points = cv2.goodFeaturesToTrack(before["gray"], 260, 0.005, max(3, int(radius * 0.05)), mask=inner if inner.any() else None)
        if points is None or len(points) < MIN_FEATURES:
            return {"delta": 0.0, "weight": 0.0, "features": 0, "extent": extent}
        lk = dict(winSize=(21, 21), maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 24, 0.01))
        moved, ok, _ = cv2.calcOpticalFlowPyrLK(before["gray"], gray, points, None, **lk)
        back, ok_back, _ = cv2.calcOpticalFlowPyrLK(gray, before["gray"], moved, None, **lk)
        error = np.linalg.norm((back - points).reshape(-1, 2), axis=1)
        good = ok.ravel().astype(bool) & ok_back.ravel().astype(bool) & (error < 0.8)
        p0, p1 = points.reshape(-1, 2)[good], moved.reshape(-1, 2)[good]
        u0 = (p0[:, 0] - before["axis"]) / before["radius"]
        u1 = (p1[:, 0] - axis_x) / radius
        keep = (np.abs(u0) < 0.82) & (np.abs(u1) < 0.9)
        if keep.sum() < MIN_FEATURES:
            return {"delta": 0.0, "weight": 0.0, "features": int(keep.sum()), "extent": extent}
        votes = np.degrees(np.arcsin(np.clip(u1[keep], -1, 1)) - np.arcsin(np.clip(u0[keep], -1, 1)))
        weights = np.cos(np.arcsin(np.clip(u0[keep], -1, 1))) ** 2
        order = np.argsort(votes)
        cumulative = np.cumsum(weights[order])
        median = float(votes[order][np.searchsorted(cumulative, cumulative[-1] / 2)])
        spread = float(np.median(np.abs(votes - median))) + 0.4
        confidence = float(np.clip(keep.sum() / 60.0, 0.1, 1.0) / spread)
        return {"delta": median, "weight": confidence, "features": int(keep.sum()), "extent": extent}


def unwrap_face_yaw(flow_yaw, face_yaw):
    """Face yaw is only known modulo a full turn once the head has gone round;
    pick the multiple of 360 that agrees with the integrated flow."""
    return face_yaw + 360.0 * np.round((flow_yaw - face_yaw) / 360.0)


def one_direction(deltas):
    """A person going round on a chair turns one way. When the net turn is
    most of a revolution, steps against it are tracking noise: they are
    limited to a small step back instead of undoing the turn."""
    total = float(np.sum(deltas[1:]))
    if abs(total) < REVOLUTION_MIN:
        return deltas
    sign = np.sign(total)
    out = deltas.copy()
    out[1:] = sign * np.maximum(sign * deltas[1:], REVERSE_LIMIT)
    return out


def rescale_between_anchors(deltas, anchors, targets):
    """Point tracking under-measures a turn by a roughly constant share. Between
    two face anchors the true turn is known, so the measured steps in that gap
    are scaled by the ratio (true / measured), within sane limits."""
    out = deltas.copy()
    for first, second in zip(anchors[:-1], anchors[1:]):
        if second - first < 3:
            continue
        measured = float(out[first + 1:second + 1].sum())
        needed = float(targets[second] - targets[first])
        if abs(measured) < 10.0:
            continue
        ratio = needed / measured
        if RESCALE_RANGE[0] < ratio < RESCALE_RANGE[1]:
            out[first + 1:second + 1] *= ratio
    return out


def solve_yaw(deltas, weights, face_yaw, face_ok):
    """Yaw of every frame from two kinds of evidence: the frame-to-frame turn
    (smooth, but it drifts) and the face mesh yaw (absolute, but only while
    the face is in view). A least squares problem on a chain: the face frames
    pin the drift, and in the gaps (the back of the head) the correction is
    spread over the turns, which closes the loop of a full revolution."""
    n = len(deltas)
    deltas = one_direction(np.asarray(deltas, np.float64))
    weights = np.asarray(weights, np.float64)
    integrated = np.concatenate([[0.0], np.cumsum(deltas[1:])])
    anchors = np.array([face_ok[i] and abs(face_yaw[i]) <= FACE_ANCHOR_MAX for i in range(n)])
    if not anchors.any():
        return integrated
    first = int(np.argmax(anchors))
    integrated = integrated - integrated[first] + face_yaw[first]
    targets = np.array([unwrap_face_yaw(integrated[i], face_yaw[i]) if anchors[i] else 0.0 for i in range(n)])
    deltas = rescale_between_anchors(deltas, np.flatnonzero(anchors), targets)
    rows, rhs = [], []
    for i in range(n):
        if anchors[i]:
            row = np.zeros(n)
            row[i] = 1.0 / FACE_SIGMA
            rows.append(row)
            rhs.append(targets[i] / FACE_SIGMA)
    for i in range(1, n):
        row = np.zeros(n)
        row[i], row[i - 1] = 1.0, -1.0
        w = np.sqrt(max(weights[i], 0.02)) / STEP_SIGMA
        rows.append(row * w)
        rhs.append(deltas[i] * w)
    solution, *_ = np.linalg.lstsq(np.array(rows), np.array(rhs), rcond=None)
    return solution


def wrap(yaw):
    return (np.asarray(yaw, np.float64) + 180.0) % 360.0 - 180.0


def pick_views(yaw, quality, per_bin=1, bin_degrees=BIN_DEGREES):
    """Indices of the best frame of every angular bin: the coverage of the
    360 turn, one sharp frame per slice."""
    yaw = wrap(yaw)
    bins = ((yaw + 180.0) // bin_degrees).astype(int)
    chosen = []
    for b in np.unique(bins):
        members = np.flatnonzero(bins == b)
        order = members[np.argsort(-np.asarray(quality)[members])]
        chosen.extend(order[:per_bin].tolist())
    return sorted(chosen, key=lambda i: yaw[i])


def coverage(yaw, bin_degrees=BIN_DEGREES):
    bins = np.unique(((wrap(yaw) + 180.0) // bin_degrees).astype(int))
    total = int(round(360 / bin_degrees))
    return len(bins) / total, sorted(int(b) for b in bins)


def sharpness(gray, mask=None):
    lap = cv2.Laplacian(gray, cv2.CV_32F)
    if mask is not None and mask.any():
        return float(lap[mask > 0].var())
    return float(lap.var())
