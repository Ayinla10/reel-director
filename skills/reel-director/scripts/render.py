"""Step 6 - preview frames, then the final render straight at social-media size.

  python render.py preview --work W                 # W/review/preview_sheet.jpg (one frame per effect + seam)
  python render.py final   --work W --out "D:/videos/my_reel.mp4"

The final pass renders ONCE at a platform-friendly bitrate (no giant intermediate files to re-encode),
muxes W/final_audio.wav, then writes W/review/final_sheet.jpg including the loop seam (last | first frame).
"""
import argparse
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rdlib import FFMPEG, FFPROBE, load_json, log, run

BITRATE = {"9:16": ("9M", "12M"), "16:9": ("9M", "12M"), "1:1": ("7M", "10M"), "4:5": ("7M", "10M")}


def npx():
    return shutil.which("npx") or shutil.which("npx.cmd") or "npx"


def sheet(video, times, out, width=270):
    """Grid of frames at the given times (8 per row) for a quick visual check."""
    import numpy as np
    from rdlib import grab_frames, save_image
    fr = grab_frames(video, times, width)
    if not fr:
        return None
    h = min(f.shape[0] for f in fr); cols = min(8, len(fr)); rows = (len(fr) + cols - 1) // cols
    grid = np.zeros((rows * h, cols * width, 3), np.float32)
    for i, f in enumerate(fr):
        r, c = divmod(i, cols); grid[r * h:(r + 1) * h, c * width:(c + 1) * width] = f[:h, :width]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    save_image(grid, out)
    return out


def key_times(work):
    plan = load_json(os.path.join(work, "beats.json"), {"beats": []})
    edl = load_json(os.path.join(work, "edl.json"))
    end = edl["duration"]
    ts = [0.4]
    for b in plan["beats"]:
        ts.append(min(b["until"] - 0.35, b["at"] + (b["until"] - b["at"]) * 0.7))
    return sorted(set(round(t, 2) for t in ts if 0 <= t < end))[:23], end


def preview(work):
    comp = os.path.join(work, "comp")
    ts, end = key_times(work)
    out = os.path.join(work, "review")
    os.makedirs(out, exist_ok=True)
    p = subprocess.run([npx(), "hyperframes", "snapshot", comp, "--at", ",".join(f"{t:g}" for t in ts),
                        "--no-end", "-o", os.path.join(out, "snaps")], capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit("snapshot failed:\n" + p.stderr[-1500:])
    log("preview frames ->", os.path.join(out, "snaps"), "(contact-sheet*.jpg inside)")


def final(work, out):
    edl = load_json(os.path.join(work, "edl.json"))
    comp = os.path.join(work, "comp")
    br, mx = BITRATE.get(edl["format"], ("9M", "12M"))
    tag = f"{os.getpid()}"  # unique temp names: a stray earlier run can never write into this one
    vid = os.path.join(work, f"_video_{tag}.mp4")
    log(f"rendering {edl['format']} at ~{br} (one pass, social-media size)...")
    cmd = [npx(), "hyperframes", "render", comp, "-o", vid, "--fps", str(edl["fps"]),
           "--video-bitrate", br, "--max-bitrate", mx]
    for attempt in (1, 2):
        # stream the renderer's own progress so a stall is visible immediately
        p = subprocess.run(cmd, stdout=sys.stderr, stderr=sys.stderr)
        if p.returncode == 0 and os.path.exists(vid):
            break
        if attempt == 1:  # headless Chrome sometimes stalls on a busy laptop - one clean retry
            log("render attempt 1 failed; retrying once (close other heavy apps if this repeats)...")
    else:
        raise SystemExit("render failed twice - see the renderer output above. Close browsers/editors, "
                         "run `npx hyperframes doctor`, and retry.")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    tmp_out = os.path.join(os.path.dirname(os.path.abspath(out)), f".{tag}_{os.path.basename(out)}")
    run([FFMPEG, "-v", "error", "-y", "-i", vid, "-i", os.path.join(work, "final_audio.wav"), "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", tmp_out])
    os.remove(vid)
    # integrity check: decode every frame/packet; a damaged file is never reported as done
    chk = subprocess.run([FFMPEG, "-v", "error", "-i", tmp_out, "-f", "null", "-"], capture_output=True, text=True)
    if chk.stderr.strip():
        raise SystemExit(f"the rendered file failed the decode check (kept for inspection: {tmp_out}):\n{chk.stderr[:800]}")
    os.replace(tmp_out, out)
    size = os.path.getsize(out) / 1e6
    ts, end = key_times(work)
    seam = [max(0, end - 0.08), 0.02] if edl.get("loop") else [max(0, end - 0.08)]
    sheet(out, ts + seam, os.path.join(work, "review", "final_sheet.jpg"))
    dur = float(run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out]).strip())
    log(f"DONE {out}  ({dur:.1f}s, {size:.0f} MB). Check sheet: {os.path.join(work, 'review', 'final_sheet.jpg')}"
        + ("  (last two tiles = loop seam: last frame | first frame)" if edl.get("loop") else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["preview", "final"])
    ap.add_argument("--work", required=True); ap.add_argument("--out")
    a = ap.parse_args()
    if a.cmd == "preview":
        preview(a.work)
    else:
        final(a.work, a.out or os.path.join(a.work, "reel.mp4"))


if __name__ == "__main__":
    main()
