"""Step 3 - cut, frame, grade and clean the voice in ONE decode pass.

  python cut.py <video> --work <workdir> --edit <workdir>/edit.json --cube <workdir>/grade/grade.cube

edit.json (written by Claude after reading review.txt):
{
  "cut": "tight" | "light" | "none",        # pause removal strength
  "remove": [[12.4, 15.9], ...],            # retakes, false starts, fillers, asides (source seconds)
  "zoom": "alternate" | "none",             # punch-in on alternate cuts to hide jump cuts
  "loop": true,                             # last shot framed like the first (seamless replay)
  "format": "9:16" | "16:9" | "1:1" | "4:5",
  "fps": 30,                                # optional; default = source fps if 24/25/30 else 30
  "finish": {"smooth": 0.5, "sharpen": 0.5, "grain": 0, "vignette": 0},  # 0..1 each
  "fix": {"GSME": "GSMA"}                   # transcription corrections (word -> correct spelling)
}

Writes: cut.mp4 (graded video, no audio), voice.wav (cleaned, cut), edl.json, words_cut.json
"""
import argparse
import math
import os
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rdlib import FFMPEG, hdr_filter, load_json, log, probe, run, save_json

FORMATS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}
LEVELS = {"tight": (0.42, 0.12, 0.07), "light": (0.9, 0.22, 0.12), "none": (99, 0.3, 0.2)}  # min pause, pad out, pad in


def build_edl(words, sil, edit, fps, dur):
    min_p, pad_out, pad_in = LEVELS[edit.get("cut", "tight")]
    start = max(0.0, (words[0][1] if words else 0) - 0.15)
    end = min(dur, (words[-1][2] if words else dur) + 0.3)
    if edit.get("trim"):
        start, end = max(start, edit["trim"][0]), min(end, edit["trim"][1])
    cuts = []
    for s, e in sil:
        e = e if e is not None else dur
        if e - s >= min_p:
            cuts.append((s + pad_out, e - pad_in))
    cuts += [tuple(r) for r in edit.get("remove", [])]
    cuts = sorted((max(a, start), min(b, end)) for a, b in cuts if b > start and a < end and b > a)
    keep, t = [], start
    for a, b in cuts:
        if a > t:
            keep.append([t, a])
        t = max(t, b)
    if t < end:
        keep.append([t, end])
    edl, z, tl = [], 0, 0.0
    for i, (a, b) in enumerate(keep):
        fa, fb = round(a * fps), round(b * fps)
        if fb - fa < 3:
            continue
        if edl and edit.get("zoom", "alternate") == "alternate" and a - edl[-1]["src_out"] >= 0.6:
            z ^= 1
        edl.append({"src_in": fa / fps, "src_out": fb / fps, "fa": fa, "fb": fb, "zoom": z,
                    "t_in": round(tl, 4), "t_out": round(tl + (fb - fa) / fps, 4)})
        tl += (fb - fa) / fps
    if edit.get("loop") and len(edl) > 1:
        edl[-1]["zoom"] = edl[0]["zoom"]
    return edl


def map_words(words, edl, removed=(), fixes=None):
    """Move word timings onto the cut timeline. Whisper's timestamps drift from the real audio, so a
    word goes to the shot it overlaps most; words that only touch a trimmed pause are snapped to the
    nearest shot; only words inside an explicit removal are dropped."""
    fixes = fixes or {}
    out = []
    for w in words:
        a, b = w[1], max(w[2], w[1] + 0.01)
        mid = (a + b) / 2
        if any(r0 <= mid < r1 for r0, r1 in removed):
            continue
        best, ov = None, 0.0
        for s in edl:
            o = min(b, s["src_out"]) - max(a, s["src_in"])
            if o > ov:
                best, ov = s, o
        if best is None:
            best = min(edl, key=lambda s: min(abs(mid - s["src_in"]), abs(mid - s["src_out"])))
        f = lambda t: round(min(max(t, best["src_in"]), best["src_out"]) - best["src_in"] + best["t_in"], 3)
        t0, t1 = f(a), f(b)
        if t1 - t0 < 0.08:
            t1 = round(t0 + 0.08, 3)
        text = w[0]
        core = text.strip(".,!?;:")
        if core in fixes:
            text = text.replace(core, fixes[core])
        out.append([text, t0, t1])
    out.sort(key=lambda x: x[1])
    return out


def video_graph(meta, edl, fmt, fps, cube, finish, hdr_mode):
    W, H = FORMATS[fmt]
    sw, sh = meta["width"], meta["height"]
    face = meta.get("face") or {"cx": 0.5, "y": 0.2}
    cover = abs((sw / sh) / (W / H) - 1) < 0.2
    Z = 1.15
    sel = "+".join(f"between(n\\,{s['fa']}\\,{s['fb'] - 1})" for s in edl)
    zsel = "+".join(f"between(in\\,{s['fa']}\\,{s['fb'] - 1})" for s in edl if s["zoom"]) or "0"
    pre = hdr_filter(meta, hdr_mode)
    if cover:
        WZ, HZ = 2 * round(W * Z / 2), 2 * round(H * Z / 2)
        s = max(WZ / sw, HZ / sh)
        SW, SH = 2 * math.ceil(sw * s / 2), 2 * math.ceil(sh * s / 2)
        cx = face["cx"]
        # crop to the exact output aspect around the face, then zoompan:
        # z=1 shows that whole frame, z=Z is a 1:1-pixel punch-in centred on the face
        crop = f"crop={WZ}:{HZ}:x='min(max({cx}*iw-{WZ}/2\\,0)\\,iw-{WZ})':y='(ih-{HZ})*0.2'"
        x = f"min(max({cx}*iw-iw/zoom/2\\,0)\\,iw-iw/zoom)"
        y = "(ih-ih/zoom)*0.28"
        frame = (f"scale={SW}:{SH}:flags=lanczos,{crop},"
                 f"zoompan=z='if({zsel}\\,{Z}\\,1)':x='{x}':y='{y}':d=1:s={W}x{H}:fps={fps}")
        chain = f"[0:v]{pre}fps={fps},{frame},select='{sel}',setpts=N/{fps}/TB"
    else:
        # different orientation: subject fitted, soft blurred copy of the shot fills the frame
        chain = (f"[0:v]{pre}fps={fps},select='{sel}',setpts=N/{fps}/TB,split[a][b];"
                 f"[b]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma=40,eq=brightness=-0.03[bg];"
                 f"[a]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2")
    look = [f"lut3d=file={os.path.basename(cube)}:interp=tetrahedral"]
    sm = finish.get("smooth", 0.4)
    if sm > 0:
        look.append(f"bilateral=sigmaS={3 + 4 * sm:.1f}:sigmaR={0.03 + 0.05 * sm:.3f}")
    sh_ = finish.get("sharpen", 0.5)
    if sh_ > 0:
        look.append(f"unsharp=5:5:{0.3 + 0.7 * sh_:.2f}")
    if finish.get("vignette", 0) > 0:
        look.append(f"vignette=PI/{6 - 2.5 * finish['vignette']:.2f}")
    if finish.get("grain", 0) > 0:
        look.append(f"noise=alls={int(3 + 7 * finish['grain'])}:allf=t")
    return chain + "," + ",".join(look) + ",format=yuv420p[v]", (W, H)


def face_out(meta, fmt):
    """Where the face sits in the OUTPUT frame (normalised), for placing words above the head."""
    W, H = FORMATS[fmt]; sw, sh = meta["width"], meta["height"]
    f = meta.get("face") or {"cx": 0.5, "y": 0.22, "chin": 0.45}
    if abs((sw / sh) / (W / H) - 1) < 0.2:
        WZ, HZ = W * 1.15, H * 1.15
        s = max(WZ / sw, HZ / sh); SW, SH = sw * s, sh * s
        x0 = min(max(f["cx"] * SW - WZ / 2, 0), SW - WZ); y0 = (SH - HZ) * 0.2
        m = lambda yy: (yy * SH - y0) / HZ
        return {"cx": round((f["cx"] * SW - x0) / WZ, 4), "top": round(m(f["y"]), 4), "chin": round(m(f["chin"]), 4), "mode": "cover"}
    s = min(W / sw, H / sh); oy = (H - sh * s) / 2; ox = (W - sw * s) / 2
    return {"cx": round((f["cx"] * sw * s + ox) / W, 4), "top": round((f["y"] * sh * s + oy) / H, 4),
            "chin": round((f["chin"] * sh * s + oy) / H, 4), "mode": "fit"}


def cut_voice(video, edl, work):
    raw = os.path.join(work, "voice_src48.wav")
    run([FFMPEG, "-v", "error", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "48000", raw])
    w = wave.open(raw)
    a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32)
    sr, fade = 48000, int(0.008 * 48000)
    parts = []
    for s in edl:
        seg = a[int(round(s["src_in"] * sr)):int(round(s["src_out"] * sr))].copy()
        n = int(round((s["t_out"] - s["t_in"]) * sr))
        seg = np.pad(seg, (0, max(0, n - len(seg))))[:n]
        if len(seg) > 2 * fade:
            seg[:fade] *= np.linspace(0, 1, fade); seg[-fade:] *= np.linspace(1, 0, fade)
        parts.append(seg)
    out = np.concatenate(parts)
    cutwav = os.path.join(work, "voice_cut_raw.wav")
    wo = wave.open(cutwav, "wb"); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(sr)
    wo.writeframes(np.clip(out, -32768, 32767).astype(np.int16).tobytes()); wo.close()
    # voice polish: rumble cut, denoise, de-mud, presence, de-ess, gentle compression, loudness
    chain = ("highpass=f=75,afftdn=nf=-30:tn=1,equalizer=f=280:t=q:w=1.2:g=-2.5,equalizer=f=3800:t=q:w=1:g=2.5,"
             "equalizer=f=11000:t=h:w=0.7:g=1.5,deesser=i=0.35,acompressor=threshold=-21dB:ratio=3:attack=8:release=120:makeup=2,"
             "loudnorm=I=-16:TP=-1.5:LRA=9,aresample=48000")
    run([FFMPEG, "-v", "error", "-y", "-i", cutwav, "-af", chain, "-c:a", "pcm_s16le", os.path.join(work, "voice.wav")])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("--work", required=True)
    ap.add_argument("--edit", required=True); ap.add_argument("--cube", required=True)
    ap.add_argument("--hdr", default="compat")
    a = ap.parse_args()
    meta = load_json(os.path.join(a.work, "meta.json")) or probe(a.video)
    edit = load_json(a.edit, {})
    fmt = edit.get("format", "9:16")
    fps = edit.get("fps") or (round(meta["fps"]) if round(meta["fps"]) in (24, 25, 30) else 30)
    words = load_json(os.path.join(a.work, "words.json"), [])
    sil = load_json(os.path.join(a.work, "silences.json"), [])
    edl = build_edl(words, sil, edit, fps, meta["duration"])
    total = edl[-1]["t_out"]
    log(f"{len(edl)} shots, {meta['duration']:.1f}s -> {total:.1f}s, {fmt} @ {fps}fps")
    save_json({"fps": fps, "format": fmt, "duration": total, "face_out": face_out(meta, fmt), "loop": bool(edit.get("loop")),
               "shots": edl}, os.path.join(a.work, "edl.json"))
    save_json(map_words(words, edl, [tuple(r) for r in edit.get("remove", [])], edit.get("fix")),
              os.path.join(a.work, "words_cut.json"))

    cube = os.path.abspath(a.cube)
    if os.path.dirname(cube) != os.path.abspath(a.work):
        import shutil
        shutil.copy(cube, os.path.join(a.work, "grade.cube")); cube = os.path.join(a.work, "grade.cube")
    graph, (W, H) = video_graph(meta, edl, fmt, fps, cube, edit.get("finish", {}), a.hdr)
    gpath = os.path.join(a.work, "cut_graph.txt")
    open(gpath, "w").write(graph)
    log("grading + cutting in one pass (this is the slow step on 4K phone footage)...")
    # run inside the work dir so the LUT path has no drive letter for ffmpeg's filter parser
    run([FFMPEG, "-v", "error", "-y", "-i", os.path.abspath(a.video), "-/filter_complex", "cut_graph.txt",
         "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-g", str(fps),
         "-bsf:v", "h264_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1",
         "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
         "-movflags", "+faststart", "cut.mp4"], cwd=a.work)
    cut_voice(a.video, edl, a.work)
    log(f"done -> {os.path.join(a.work, 'cut.mp4')} ({W}x{H}, {total:.1f}s) + voice.wav")


if __name__ == "__main__":
    main()
