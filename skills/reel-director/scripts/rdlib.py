"""Shared helpers for reel-director scripts: ffmpeg/ffprobe calls, frame I/O, colour math."""
import json
import os
import shutil
import subprocess
import sys

import numpy as np

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


def run(args, **kw):
    """Run a command, raise with stderr on failure."""
    p = subprocess.run(args, capture_output=True, text=True, **kw)
    if p.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(map(str, args))[:300]}\n{p.stderr[-2000:]}")
    return p.stdout


def probe(path):
    """Duration, size (rotation applied), fps, HDR transfer and audio presence."""
    d = json.loads(run([FFPROBE, "-v", "error", "-show_streams", "-show_format", "-of", "json", path]))
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    if abs(rot) in (90, 270):
        w, h = h, w
    num, den = (v.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den or 1)
    trc = v.get("color_transfer", "") or ""
    return {
        "path": os.path.abspath(path),
        "duration": float(d["format"]["duration"]),
        "width": w, "height": h, "fps": round(fps, 3),
        "transfer": trc,
        "hdr": "hlg" if trc == "arib-std-b67" else "pq" if trc == "smpte2084" else None,
        "has_audio": any(s["codec_type"] == "audio" for s in d["streams"]),
    }


def hdr_filter(meta, mode="compat"):
    """Filter prefix that brings phone HDR to SDR.

    compat  - read the HLG signal as SDR (HLG is designed to be backward compatible) and let the
              grade's auto exposure / white balance normalise it. Safe, fast, no purple casts.
    tonemap - full linearise + hable tone map. More highlight detail, can shift colour on some phones.
    """
    if not meta.get("hdr") or mode == "compat":
        return ""
    tin = "arib-std-b67" if meta["hdr"] == "hlg" else "smpte2084"
    return (f"zscale=tin={tin}:t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
            "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,")


def grab_frames(path, times, width=320, prefix_filter=""):
    """Return list of float32 RGB arrays in [0,1] at the given times."""
    out = []
    for t in times:
        raw = subprocess.run(
            [FFMPEG, "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1",
             "-vf", f"{prefix_filter}scale={width}:-2:flags=area,format=rgb24", "-f", "rawvideo", "-"],
            capture_output=True).stdout
        if not raw:
            continue
        h = len(raw) // (width * 3)
        out.append(np.frombuffer(raw[: width * 3 * h], np.uint8).reshape(h, width, 3).astype(np.float32) / 255.0)
    return out


def load_image(path, width=480):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)))
    return np.asarray(im, np.float32) / 255.0


def save_image(arr, path):
    from PIL import Image
    Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8)).save(path, quality=92)


def luma(rgb):
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def ycbcr(rgb):
    y = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    cb = 0.5 + (rgb[..., 2] - y) * 0.564
    cr = 0.5 + (rgb[..., 0] - y) * 0.713
    return y, cb, cr


def hex_to_rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def log(*a):
    print("[reel-director]", *a, file=sys.stderr, flush=True)
