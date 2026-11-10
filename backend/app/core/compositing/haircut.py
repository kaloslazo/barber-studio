import cv2
import numpy as np

from app.core.segmentation.mp_segmenter import BACKGROUND, BODY_SKIN, CLOTHES, FACE_SKIN, HAIR

STYLES = {
    "low-fade": (0.10, -0.12),
    "mid-fade": (-0.08, -0.30),
    "high-fade": (-0.24, -0.46),
    "buzz": None,
}
DISABLED_STYLES = ()

WORK_FACE_WIDTH = 420.0
SKULL_SIDE = 0.55
SHORT_DENSITY = 0.82


def _smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _kernel(size):
    size = max(3, int(size) | 1)
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))


def _blur(layer, sigma):
    return cv2.GaussianBlur(layer, (0, 0), max(0.5, float(sigma)))


def pull_push(image, known):
    """Fills every pixel from the known ones only, coarse to fine, so the
    hole gets a smooth continuation of what surrounds it instead of the
    streaks that drag hair color outward."""
    levels = []
    color = image * known[..., None]
    weight = known.astype(np.float32)
    while min(color.shape[:2]) > 8:
        levels.append((color, weight))
        color = cv2.pyrDown(color)
        weight = cv2.pyrDown(weight)
    fill = color / np.maximum(weight, 1e-6)[..., None]
    for color, weight in reversed(levels):
        up = cv2.pyrUp(fill, dstsize=(color.shape[1], color.shape[0]))
        alpha = np.clip(weight * 2.0, 0.0, 1.0)[..., None]
        fill = alpha * (color / np.maximum(weight, 1e-6)[..., None]) + (1.0 - alpha) * up
    return fill


def _frame(shape, geometry):
    """Head coordinates in face widths: x across, y down, origin between
    the ears at eye level, rotated with the head."""
    h, w = shape
    cx, cy = geometry["center"]
    fw = geometry["face_w"]
    cos, sin = np.cos(geometry["roll"]), np.sin(geometry["roll"])
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = xs - cx, ys - cy
    return (dx * cos + dy * sin) / fw, (-dx * sin + dy * cos) / fw


def _to_frame(point, geometry):
    cx, cy = geometry["center"]
    cos, sin = np.cos(geometry["roll"]), np.sin(geometry["roll"])
    dx, dy = point[0] - cx, point[1] - cy
    return (dx * cos + dy * sin) / geometry["face_w"], (-dx * sin + dy * cos) / geometry["face_w"]


def _skull(x, y, top):
    """Shaved head silhouette: a dome over the eyes up to `top` that keeps
    the width of the temples down to the ears."""
    dome = np.abs(x / SKULL_SIDE) ** 2.15 + np.abs(np.minimum(y, 0.0) / top) ** 2.15
    sides = np.abs(x) <= SKULL_SIDE - 0.25 * np.maximum(y, 0.0)
    return ((dome <= 1.0) & (y <= 0.22) & sides).astype(np.float32)


def _column_top(x, y, inside, start, limit=-1.1):
    """Highest row of the central column, walking up from `start`, that is
    still mostly `inside`."""
    band = (np.abs(x) < 0.1) & (y < start) & (y > limit)
    if not band.any():
        return start
    rows = np.round(y[band] * 100).astype(int)
    hits = inside[band]
    top = int(np.floor(start * 100))
    misses = 0
    for row in range(top, int(limit * 100), -1):
        sample = hits[rows == row]
        if len(sample) < 4:
            break
        if sample.mean() < 0.5:
            misses += 1
            if misses > 2:
                break
            continue
        misses = 0
        top = row
    return top / 100.0


def _front_hairline(x, y, geometry, face_skin):
    """Where the forehead ends. When enough forehead shows, the skin itself
    says it; when hair covers it (bangs), a forehead of usual height is
    assumed above the brows."""
    _, brow = _to_frame((geometry["center"][0], geometry["brow_y"]), geometry)
    usual = brow - 0.30
    if face_skin is None:
        return usual
    skin_top = _column_top(x, y, face_skin > 0.5, brow)
    if brow - skin_top >= 0.2:
        return skin_top - 0.005
    return usual


def _hairline(x, front):
    ax = np.abs(x)
    line = front + 0.04 * (ax / 0.3) ** 2 - 0.02 * _smoothstep((ax - 0.12) / 0.14)
    corner = np.clip((ax - 0.27) / 0.21, 0.0, 1.0)
    return line + (0.10 - line) * (1.0 - np.sqrt(1.0 - corner * corner))


def _light(image_bgr, face, x):
    lightness = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)[..., 0].astype(np.float32)
    left = face & (x < -0.05)
    right = face & (x > 0.05)
    if left.sum() < 50 or right.sum() < 50:
        lx = 0.0
    else:
        lx = float(np.clip((np.median(lightness[right]) - np.median(lightness[left])) / 60.0, -0.8, 0.8))
    light = np.array([lx, -0.65, 0.75], np.float32)
    return light / np.linalg.norm(light)


def _shade(x, y, light, top):
    nx = x / SKULL_SIDE
    ny = np.minimum(y, 0.0) / abs(top)
    nz = np.sqrt(np.clip(1.0 - nx * nx - ny * ny, 0.02, 1.0))
    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    lambert = (nx * light[0] + ny * light[1] + nz * light[2]) / norm
    return 0.62 + 0.38 * np.clip(lambert, 0.0, 1.0)


def _hair_color(image_bgr, hair):
    pixels = image_bgr[hair]
    if len(pixels) < 50:
        return np.array([45.0, 130.0, 132.0], np.float32)
    lab = cv2.cvtColor(pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    lightness = lab[:, 0]
    lower = lab[lightness <= np.percentile(lightness, 45)]
    return np.median(lower if len(lower) > 20 else lab, axis=0)


def _face(shape, geometry):
    """The face the cut never touches: the jaw and brows, pulled in a
    little so sideburn hair on its edge can fade with the sides."""
    polygon = geometry["polygon"].astype(np.float32)
    center = polygon.mean(axis=0)
    polygon = np.round(center + (polygon - center) * 0.95).astype(np.int32)
    face = np.zeros(shape, np.uint8)
    cv2.fillPoly(face, [polygon], 255)
    return face


def _parts(image_bgr, hair_mask, geometry, probabilities):
    shape = image_bgr.shape[:2]
    hair = hair_mask.astype(np.float32) / 255.0
    face = _face(shape, geometry)
    if probabilities is not None:
        hair = np.maximum(_blur(hair, 1.0), probabilities[HAIR])
        return {
            "hair": hair,
            "background": probabilities[BACKGROUND],
            "skin": np.maximum(probabilities[FACE_SKIN], probabilities[BODY_SKIN]),
            "face_skin": probabilities[FACE_SKIN],
            "rest": np.maximum(probabilities[CLOTHES], probabilities[BODY_SKIN]),
        }
    near = cv2.dilate(np.maximum(hair_mask, face), _kernel(geometry["face_w"] * 0.06)) > 0
    face_f = (face > 0).astype(np.float32)
    return {
        "hair": hair,
        "background": (~near).astype(np.float32),
        "skin": face_f,
        "face_skin": None,
        "rest": np.zeros(shape, np.float32),
    }


def _layout(x, y, style, short, wobble):
    """Where the cut keeps the original hair (`keep`) and how dense the
    short hair grows everywhere else (`density`)."""
    if STYLES[style] is None:
        return np.zeros_like(x), np.full_like(x, short)
    skin_line, top_line = STYLES[style]
    reach = 0.36 + 0.16 * _smoothstep((-0.40 - y) / 0.25)
    sides = _smoothstep((np.abs(x) - reach + 0.015 * wobble) / 0.07)
    keep = 1.0 - sides
    density = short * np.sqrt(_smoothstep((skin_line - y) / (skin_line - top_line)))
    return keep, density


def _render(image_bgr, hair_mask, geometry, style, probabilities, seed, shortness):
    shape = image_bgr.shape[:2]
    fw = geometry["face_w"]
    original = image_bgr.astype(np.float32)
    parts = _parts(image_bgr, hair_mask, geometry, probabilities)
    x, y = _frame(shape, geometry)
    rng = np.random.default_rng(seed)
    wobble = _blur(rng.normal(0.0, 1.0, shape).astype(np.float32), fw * 0.02)
    wobble /= wobble.std() + 1e-6
    keep, density = _layout(x, y, style, SHORT_DENSITY * (1.1 - 0.4 * shortness), wobble)
    front = _front_hairline(x, y, geometry, parts["face_skin"])
    crown = _column_top(x, y, parts["hair"] + parts["skin"] > 0.5, front)
    top = float(np.clip(max(front - 0.33, crown + 0.03), -0.9, -0.55))

    face = _face(shape, geometry)
    hair = (parts["hair"] > 0.25).astype(np.uint8)
    if not hair.any():
        return original, np.zeros(shape, np.float32)
    hair_wide = cv2.dilate(hair, _kernel(fw * 0.035)) > 0
    hair_wide &= face == 0

    person = (parts["background"] < 0.5).astype(np.float32)
    head = cv2.dilate(_skull(x, y, top), _kernel(fw * 0.05)) * cv2.dilate(person, _kernel(fw * 0.01))
    head = _blur(head, fw * 0.004)
    cut = keep < 0.5

    remove = (hair_wide & cut & (head < 0.5)).astype(np.uint8)
    known = ((parts["background"] > 0.6) | (parts["rest"] > 0.7)) & (remove == 0) & ~hair_wide
    plate = pull_push(original, known.astype(np.float32))
    band = cv2.dilate(remove, _kernel(fw * 0.2)) > 0
    difference = np.abs(original - plate).sum(axis=2)
    strands = band & (difference > 30) & (parts["skin"] < 0.4) & (parts["rest"] < 0.5) & cut & (head < 0.5)
    strands &= face == 0
    if strands.any():
        remove = np.maximum(remove, cv2.dilate(strands.astype(np.uint8), _kernel(3)))
        known &= remove == 0
        plate = pull_push(original, known.astype(np.float32))
    grain = _blur(rng.normal(0.0, 1.0, shape).astype(np.float32), 0.6)
    plate += grain[..., None] * 1.5
    removal = _blur(remove.astype(np.float32), max(0.8, fw * 0.003))

    light = _light(image_bgr, face > 0, x)
    shade = _shade(x, y, light, top)
    hairline_shadow = cv2.dilate(hair, _kernel(fw * 0.09)) > 0
    skin_known = (parts["skin"] > 0.6) & ~hairline_shadow & (y < 0.25)
    if skin_known.sum() < 50:
        skin_known = face > 0
    skin_weight = skin_known.astype(np.float32)
    skin = pull_push(original, skin_weight)
    scalp = skin + grain[..., None] * 2.0

    inner = cv2.erode(face, _kernel(fw * 0.03)) > 0
    reskin = cv2.dilate(hair, _kernel(fw * 0.11)) > 0
    reskin &= ~inner
    covered = np.maximum(_blur(hair_wide.astype(np.float32), fw * 0.004), _blur(reskin.astype(np.float32), fw * 0.016) * cut)
    covered = np.clip(covered, 0.0, 1.0) * head
    base = original * (1.0 - removal[..., None]) + plate * removal[..., None]
    base = base * (1.0 - covered[..., None]) + scalp * covered[..., None]

    drift = _blur(rng.normal(0.0, 1.0, shape).astype(np.float32), fw * 0.08)
    drift /= drift.std() + 1e-6
    zone = _smoothstep((_hairline(x, front) + 0.006 * drift - y) / 0.02)
    ears = _smoothstep((np.abs(x) - 0.36) / 0.06)
    paint = np.clip(1.0 - parts["skin"] * (1.0 - hair_wide) * ears, 0.0, 1.0)
    streak = cv2.GaussianBlur(rng.normal(0.0, 1.0, shape).astype(np.float32), (0, 0), sigmaX=0.7, sigmaY=max(1.0, fw / 180.0))
    streak /= streak.std() + 1e-6
    patches = _blur(rng.normal(0.0, 1.0, shape).astype(np.float32), fw * 0.03)
    patches /= patches.std() + 1e-6
    coverage = density * zone * head * paint * np.clip(1.0 + 0.08 * streak + 0.06 * patches, 0.0, 1.2)

    color = _hair_color(image_bgr, hair_wide & (parts["hair"] > 0.6))
    lab = np.empty(shape + (3,), np.float32)
    lab[..., 0] = np.clip(color[0] * (0.55 + 0.6 * shade) - 3.0 * streak, 0, 255)
    lab[..., 1] = color[1]
    lab[..., 2] = color[2]
    short = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR).astype(np.float32)
    coverage = np.clip(coverage, 0.0, 1.0)[..., None]
    result = base * (1.0 - coverage) + short * coverage

    kept = keep[..., None]
    result = np.where(kept > 0.999, original, original * kept + result * (1.0 - kept))
    changed = np.clip(np.maximum.reduce([removal, covered, coverage[..., 0]]) * (1.0 - keep), 0.0, 1.0)
    result = np.where(changed[..., None] > 0.0, result, original)
    inner = cv2.erode(face, _kernel(fw * 0.03)) > 0
    result[inner] = original[inner]
    changed[inner] = 0.0
    return result, changed


def _window(shape, geometry, hair_mask):
    h, w = shape
    cx, cy = geometry["center"]
    fw = geometry["face_w"]
    x0, y0 = int(cx - fw * 1.1), int(cy - fw * 1.25)
    x1, y1 = int(cx + fw * 1.1), int(cy + fw * 0.9)
    rows, cols = np.nonzero(hair_mask)
    if len(rows):
        pad = int(fw * 0.2)
        x0, y0 = min(x0, cols.min() - pad), min(y0, rows.min() - pad)
        x1, y1 = max(x1, cols.max() + pad), max(y1, rows.max() + pad)
    return max(0, x0), max(0, y0), min(w, x1), min(h, y1)


def apply_haircut(image_bgr, hair_mask, geometry, style, strength, probabilities=None, seed=7):
    """Short-hair styles on a photo.

    Hair that the cut takes away is replaced by what was behind it, rebuilt
    only from real background pixels; inside a skull fitted to the face the
    scalp is continued from the forehead skin and lit like the face. Short
    hair in the person's own color then grows back above a hairline taken
    from the face proportions. Fades keep the top and shorten the sides,
    from bare skin at the bottom to short hair at the fade line; the buzz
    shortens everything."""
    if style not in STYLES:
        raise ValueError(f"Unknown haircut style: {style}")
    amount = float(np.clip(strength, 0.0, 1.0))
    if amount <= 0.0 or not (hair_mask > 0).any():
        return image_bgr.copy()

    x0, y0, x1, y1 = _window(image_bgr.shape[:2], geometry, hair_mask)
    crop = image_bgr[y0:y1, x0:x1]
    scale = min(1.0, WORK_FACE_WIDTH / geometry["face_w"])
    local = dict(geometry)
    local["center"] = ((geometry["center"][0] - x0) * scale, (geometry["center"][1] - y0) * scale)
    local["brow_y"] = (geometry["brow_y"] - y0) * scale
    local["chin"] = ((geometry["chin"][0] - x0) * scale, (geometry["chin"][1] - y0) * scale)
    local["face_w"] = geometry["face_w"] * scale
    local["polygon"] = np.round((geometry["polygon"] - np.array([x0, y0])) * scale).astype(np.int32)
    size = (max(8, int(round((x1 - x0) * scale))), max(8, int(round((y1 - y0) * scale))))

    def shrink(layer, interpolation=cv2.INTER_AREA):
        return layer if scale == 1.0 else cv2.resize(layer, size, interpolation=interpolation)

    probs = None
    if probabilities is not None:
        probs = np.stack([shrink(np.ascontiguousarray(layer[y0:y1, x0:x1])) for layer in probabilities])
    small = shrink(crop)
    result, changed = _render(small, shrink(hair_mask[y0:y1, x0:x1], cv2.INTER_LINEAR), local, style, probs, seed, amount)
    if scale != 1.0:
        full = (x1 - x0, y1 - y0)
        result = cv2.resize(result, full, interpolation=cv2.INTER_CUBIC)
        changed = cv2.resize(changed, full, interpolation=cv2.INTER_LINEAR)
        detail = crop.astype(np.float32) - cv2.resize(small, full, interpolation=cv2.INTER_CUBIC).astype(np.float32)
        result = result + detail * (1.0 - changed[..., None])
    out = image_bgr.copy()
    out[y0:y1, x0:x1] = np.clip(np.rint(result), 0, 255).astype(np.uint8)
    return out
