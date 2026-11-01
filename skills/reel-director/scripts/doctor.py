"""Check everything reel-director needs and say exactly how to fix what's missing.

  python doctor.py
"""
import importlib
import shutil
import subprocess
import sys

OK, BAD = "  [ok] ", "  [!!] "
problems = 0


def check(name, ok, fix, detail=""):
    global problems
    print((OK if ok else BAD) + name + (f"  {detail}" if detail else ""))
    if not ok:
        problems += 1
        print("        fix: " + fix)


def ver(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120).stdout.strip().splitlines()[0]
    except Exception:
        return ""


print("reel-director doctor\n")
check("Python >= 3.9", sys.version_info >= (3, 9), "install Python 3.10+ from python.org", sys.version.split()[0])
for mod, pip in (("numpy", "numpy"), ("PIL", "pillow"), ("faster_whisper", "faster-whisper")):
    try:
        importlib.import_module(mod); found = True
    except Exception:
        found = False
    check(f"python package {pip}", found, f"pip install {pip}")
ff = shutil.which("ffmpeg")
check("ffmpeg", bool(ff), "Windows: winget install Gyan.FFmpeg | macOS: brew install ffmpeg | Linux: apt install ffmpeg",
      ver(["ffmpeg", "-version"])[:40] if ff else "")
if ff:
    filters = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    for f in ("lut3d", "zoompan", "bilateral", "loudnorm", "afftdn", "sidechaincompress"):
        check(f"ffmpeg filter {f}", f" {f} " in filters, "install a full ffmpeg build (e.g. gyan.dev 'full' on Windows)")
node = shutil.which("node")
check("Node.js >= 18", bool(node), "install Node.js LTS from nodejs.org", ver(["node", "--version"]) if node else "")
npx = shutil.which("npx") or shutil.which("npx.cmd")
if npx:
    hv = ver([npx, "hyperframes", "--version"])
    check("HyperFrames CLI (npx hyperframes)", bool(hv), "npx hyperframes doctor   (first run downloads it)", hv)
    if hv:
        print("        tip: run `npx hyperframes doctor` once to fetch the headless browser used for rendering")
try:
    import cv2  # noqa
    print("  [--] OpenCV found (optional; face finding works without it)")
except Exception:
    print("  [--] OpenCV not installed (optional)")
print("\nAll good - you're ready to /reel-director." if not problems else f"\n{problems} thing(s) to fix above.")
sys.exit(1 if problems else 0)
