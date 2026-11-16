import json
import os
import tempfile
import time
from pathlib import Path

TURN_DIR = Path(__file__).resolve().parents[4] / "data" / "peluca_turns"
KEEP = 12


def save(frames, angles, root=None):
    """Keeps the frames of a 360 scan and their solved yaws on disk (data/ is
    not versioned), so a scan can be inspected or rebuilt later."""
    root = Path(root) if root else TURN_DIR
    folder = root / time.strftime("%Y%m%d-%H%M%S")
    folder.mkdir(parents=True, exist_ok=True)
    for index, (data, angle) in enumerate(zip(frames, angles)):
        (folder / f"{index:02d}_{angle:+07.1f}.jpg").write_bytes(data)
    (folder / "angles.json").write_text(json.dumps([float(angle) for angle in angles]))
    old = sorted(path for path in root.iterdir() if path.is_dir())
    for path in old[:-KEEP]:
        for item in path.iterdir():
            item.unlink()
        path.rmdir()
    return folder


async def spool(upload):
    """Writes an uploaded video to a temporary file (OpenCV reads from disk)."""
    suffix = os.path.splitext(upload.filename or "")[1] or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        while True:
            chunk = await upload.read(1 << 20)
            if not chunk:
                break
            handle.write(chunk)
        return handle.name


def discard(path):
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
