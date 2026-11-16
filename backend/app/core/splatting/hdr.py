import shutil
import subprocess

import numpy as np

HLG_A, HLG_B, HLG_C = 0.17883277, 0.28466892, 0.55991073
BT2020_TO_BT709 = np.array([[1.6605, -0.5876, -0.0728], [-0.1246, 1.1329, -0.0083], [-0.0182, -0.1006, 1.1187]], np.float32)
DIFFUSE_WHITE = 0.265
SHOULDER = 4.0


def video_is_hdr(path):
    """True when the video is HLG or PQ (an iPhone's default), which OpenCV
    decodes as if it were ordinary video: washed-out skin and flat colour."""
    tool = shutil.which("ffprobe")
    if tool is None:
        return False
    try:
        out = subprocess.run(
            [tool, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_transfer", "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return False
    return out in ("arib-std-b67", "smpte2084")


def hlg_to_sdr(bgr):
    """HLG (BT.2020) frame as decoded by OpenCV to an ordinary sRGB-like
    frame: inverse HLG curve to scene light, BT.2020 -> BT.709 primaries,
    diffuse white to 1, a soft shoulder for the highlights, sRGB encoding."""
    v = bgr[..., ::-1].astype(np.float32) / 255.0
    linear = np.where(v <= 0.5, v * v / 3.0, (np.exp((v - HLG_C) / HLG_A) + HLG_B) / 12.0)
    rgb = np.clip(linear @ BT2020_TO_BT709.T, 0.0, None) / DIFFUSE_WHITE
    rgb = rgb * (1.0 + rgb / (SHOULDER * SHOULDER)) / (1.0 + rgb)
    srgb = np.where(rgb <= 0.0031308, 12.92 * rgb, 1.055 * np.power(np.maximum(rgb, 1e-8), 1 / 2.4) - 0.055)
    return np.clip(srgb[..., ::-1] * 255.0 + 0.5, 0, 255).astype(np.uint8)
