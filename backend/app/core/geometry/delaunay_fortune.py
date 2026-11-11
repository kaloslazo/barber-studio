"""Delaunay triangulation via Fortune's sweep-line algorithm (from scratch).

Every mesh in the app comes from here: the beard warp, the mesh overlay, the
3D mirror and the lab. The Bowyer-Watson version in ``delaunay.py`` stays as
an independent check.

Idea: Fortune sweeps a horizontal line downward, maintaining the "beach line"
(the lower envelope of the parabolas of the sites already passed). Two kinds of
events drive it:
  * site events  -> a new parabola arc appears on the beach line,
  * circle events -> an arc is squeezed to zero width and disappears.
Every circle event is a Voronoi vertex, and the three sites whose arcs meet
there are cocircular with an empty circumcircle: that triple IS a Delaunay
triangle. So we simply collect the triples at valid circle events.

Degenerate input (several sites on the same sweep line, four or more
cocircular sites, as in a grid) breaks the event order, so the sites are
moved by a fixed, tiny random offset (1e-6 of the point cloud's span) before
the sweep, and triangles with no area in the original points (collinear or
repeated sites) are dropped. Face points never notice it.

``delaunay_triangles(points, rect=None)`` matches the signature of the
Bowyer-Watson version and returns a list of index triplets into ``points``.
"""

import heapq
import math

import numpy as np

JITTER = 1e-6


class _Arc:
    __slots__ = ("site", "prev", "next", "event")

    def __init__(self, site):
        self.site = site
        self.prev = None
        self.next = None
        self.event = None


class _CircleEvent:
    __slots__ = ("arc", "cx", "cy", "y", "valid")

    def __init__(self, arc, cx, cy, y):
        self.arc = arc
        self.cx = cx
        self.cy = cy
        self.y = y
        self.valid = True


def _cross(ax, ay, bx, by, cx, cy):
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _circumcenter(ax, ay, bx, by, cx, cy):
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    a2 = ax * ax + ay * ay
    b2 = bx * bx + by * by
    c2 = cx * cx + cy * cy
    ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d
    uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d
    return ux, uy


def _breakpoint(px, py, rx, ry, ly):
    """x of the beach-line breakpoint between the left arc (focus p) and the
    right arc (focus r), with the sweep line (directrix) at y = ly."""
    if abs(py - ly) < 1e-9:
        return px
    if abs(ry - ly) < 1e-9:
        return rx
    dp = 2.0 * (py - ly)
    dq = 2.0 * (ry - ly)
    a = 1.0 / dp - 1.0 / dq
    b = -2.0 * (px / dp - rx / dq)
    c = (px * px + py * py - ly * ly) / dp - (rx * rx + ry * ry - ly * ly) / dq
    if abs(a) < 1e-12:
        if abs(b) < 1e-12:
            return (px + rx) / 2.0
        return -c / b
    disc = max(0.0, b * b - 4.0 * a * c)
    sq = math.sqrt(disc)
    x1 = (-b + sq) / (2.0 * a)
    x2 = (-b - sq) / (2.0 * a)
    return max(x1, x2) if py < ry else min(x1, x2)


def delaunay_triangles(points, rect=None):
    P = np.asarray(points, dtype=np.float64)
    n = len(P)
    if n < 3:
        return []
    original = P
    span = max(float(np.ptp(P, axis=0).max()), 1.0)
    P = P + np.random.default_rng(12345).uniform(-1.0, 1.0, P.shape) * span * JITTER

    triangles = []
    pq = []
    counter = 0

    # Site events: process the highest y first (sweep top -> bottom).
    for i in range(n):
        heapq.heappush(pq, (-P[i, 1], P[i, 0], counter, 0, i))
        counter += 1

    head = [None]  # beach line, doubly linked list of _Arc (head[0] = leftmost)

    def add_circle_event(arc):
        if arc is None or arc.prev is None or arc.next is None:
            return
        ax, ay = P[arc.prev.site]
        bx, by = P[arc.site]
        cx, cy = P[arc.next.site]
        # The middle arc collapses only if prev->mid->next turns clockwise.
        if _cross(ax, ay, bx, by, cx, cy) >= 0:
            return
        center = _circumcenter(ax, ay, bx, by, cx, cy)
        if center is None:
            return
        ox, oy = center
        r = math.hypot(ox - bx, oy - by)
        y_bottom = oy - r
        ev = _CircleEvent(arc, ox, oy, y_bottom)
        arc.event = ev
        nonlocal counter
        heapq.heappush(pq, (-y_bottom, ox, counter, 1, ev))
        counter += 1

    def find_arc_above(x, ly):
        arc = head[0]
        while arc is not None:
            left = -math.inf
            right = math.inf
            if arc.prev is not None:
                left = _breakpoint(*P[arc.prev.site], *P[arc.site], ly)
            if arc.next is not None:
                right = _breakpoint(*P[arc.site], *P[arc.next.site], ly)
            if left <= x <= right:
                return arc
            arc = arc.next
        return None

    def handle_site(i):
        site_x, site_y = P[i]
        if head[0] is None:
            head[0] = _Arc(i)
            return
        arc = find_arc_above(site_x, site_y)
        if arc is None:
            # numerical fallback: append at the rightmost end
            arc = head[0]
            while arc.next is not None:
                arc = arc.next
        if arc.event is not None:
            arc.event.valid = False
            arc.event = None

        left = _Arc(arc.site)
        mid = _Arc(i)
        right = _Arc(arc.site)

        left.prev = arc.prev
        left.next = mid
        mid.prev = left
        mid.next = right
        right.prev = mid
        right.next = arc.next
        if arc.prev is not None:
            arc.prev.next = left
        else:
            head[0] = left
        if arc.next is not None:
            arc.next.prev = right

        add_circle_event(left)
        add_circle_event(right)

    def handle_circle(ev):
        if not ev.valid:
            return
        arc = ev.arc
        prev = arc.prev
        nxt = arc.next
        if prev is None or nxt is None:
            return

        triangles.append((prev.site, arc.site, nxt.site))

        if prev.event is not None:
            prev.event.valid = False
            prev.event = None
        if nxt.event is not None:
            nxt.event.valid = False
            nxt.event = None

        prev.next = nxt
        nxt.prev = prev

        add_circle_event(prev)
        add_circle_event(nxt)

    while pq:
        _, _, _, kind, payload = heapq.heappop(pq)
        if kind == 0:
            handle_site(payload)
        else:
            handle_circle(payload)

    def has_area(tri):
        (ax, ay), (bx, by), (cx, cy) = original[list(tri)]
        return abs(_cross(ax, ay, bx, by, cx, cy)) > 1e-12 * span * span

    return [tri for tri in triangles if has_area(tri)]
