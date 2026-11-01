"""Step 1 - analyse a raw talking-head video.

  python prepare.py <video> --work <workdir> [--model small] [--language auto]

Writes into <workdir>:
  meta.json        duration, size, fps, HDR, face box (normalised), audio levels
  words.json       word-level transcript [[text, start, end, prob], ...] (any language)
  segments.txt     readable transcript with timestamps
  silences.json    pauses [[start, end], ...]
  review.txt       hints for the edit: long pauses, filler words, likely retakes / false starts
"""
import argparse
import os
import re
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rdlib import FFMPEG, grab_frames, log, probe, run, save_json

FILLERS = {
    "en": ["um", "uh", "erm", "uhm", "hmm", "you know", "i mean", "like", "basically", "actually", "so yeah"],
    "fr": ["euh", "heu", "bah", "ben", "en fait", "tu vois", "du coup"],
    "es": ["eh", "este", "o sea", "pues", "bueno"],
    "pt": ["é", "tipo", "né", "então"],
}


def extract_audio(video, work):
    wav = os.path.join(work, "audio16.wav")
    run([FFMPEG, "-v", "error", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000", wav])
    return wav


def transcribe(wav, model_size, language):
    from faster_whisper import WhisperModel
    w = wave.open(wav)
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    model = WhisperModel(model_size, device="auto", compute_type="int8")
    segs, info = model.transcribe(audio, word_timestamps=True, beam_size=5, condition_on_previous_text=False,
                                  language=None if language in (None, "", "auto") else language)
    words, lines = [], []
    for s in segs:
        lines.append(f"[{s.start:7.2f}-{s.end:7.2f}] {s.text.strip()}")
        for wd in s.words or []:
            t = wd.word.strip()
            if t:
                words.append([t, round(wd.start, 3), round(wd.end, 3), round(wd.probability, 2)])
    return words, lines, info.language, info.language_probability


def silences(wav, db=-38, mind=0.22):
    import subprocess
    p = subprocess.run([FFMPEG, "-hide_banner", "-i", wav, "-af", f"highpass=f=80,silencedetect=n={db}dB:d={mind}",
                        "-f", "null", "-"], capture_output=True, text=True)
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", p.stderr)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    out = []
    for i, s in enumerate(st):
        e = en[i] if i < len(en) else None
        out.append([round(s, 3), round(e, 3) if e else None])
    return out


def _haar(frames):
    try:
        import cv2
        casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    except Exception:  # OpenCV missing, or OpenCV 5 (Haar moved to contrib)
        return None
    boxes = []
    for f in frames:
        g = cv2.cvtColor((f * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
        found = casc.detectMultiScale(g, 1.1, 6, minSize=(40, 40))
        if len(found):
            x, y, w, h = max(found, key=lambda b: b[2] * b[3])
            H, W = g.shape
            boxes.append([x / W, y / H, w / W, h / H])
    return boxes


def _skin_face(frames):
    """Dependency-free fallback: the face is the top-most dense skin region near the centre column."""
    from grade import skin_mask
    boxes = []
    for f in frames:
        m = skin_mask(f).astype(float)
        H, W = m.shape
        m[int(H * 0.75):] = 0  # hands / arms live lower in the frame
        rows = m.mean(1)
        dense = np.where(rows > 0.04)[0]
        if len(dense) < 5:
            continue
        top = dense[0]
        band = m[top:top + int(H * 0.16)]
        cols = band.mean(0)
        xs = np.where(cols > 0.25)[0]
        if len(xs) < 3:
            continue
        x0, x1 = xs[0], xs[-1]
        h = (x1 - x0) * 1.35
        boxes.append([x0 / W, top / H, (x1 - x0) / W, h / H])
    return boxes


def face_box(video, meta):
    """Median face box over a few frames, normalised 0-1 in the upright frame. None if no face."""
    frames = grab_frames(video, [meta["duration"] * f for f in (0.1, 0.25, 0.4, 0.55, 0.7, 0.85)], 480)
    boxes = _haar(frames) or _skin_face(frames)
    if not boxes:
        return None
    x, y, w, h = np.median(np.array(boxes), 0).tolist()
    # haar boxes cover brows->chin; extend up to include hair/forehead
    top = max(0.0, y - h * 0.35)
    return {"x": round(x, 4), "y": round(top, 4), "w": round(w, 4), "h": round(y + h - top, 4),
            "cx": round(x + w / 2, 4), "chin": round(y + h, 4), "detected_in": len(boxes)}


def review(words, sil, language):
    """Plain-text hints so the editor (Claude) can decide the cut quickly."""
    lang = (language or "en")[:2]
    fill = FILLERS.get(lang, []) + FILLERS["en"][:4]
    lines = []
    long_p = [s for s in sil if s[1] and s[1] - s[0] >= 0.8]
    lines.append(f"LONG PAUSES (>=0.8s): {len(long_p)}")
    for s in long_p:
        lines.append(f"  {s[0]:7.2f}-{s[1]:7.2f}  ({s[1] - s[0]:.1f}s)")
    toks = [re.sub(r"[^\w'%]", "", w[0].lower()) for w in words]
    lines.append("FILLER CANDIDATES (keep if meaningful):")
    for i, t in enumerate(toks):
        two = t + " " + (toks[i + 1] if i + 1 < len(toks) else "")
        if t in fill or two in fill:
            lines.append(f"  {words[i][1]:7.2f}  '{words[i][0]}{(' ' + words[i + 1][0]) if two in fill else ''}'")
    lines.append("POSSIBLE RETAKES / FALSE STARTS (repeated phrase within 12s - usually keep the LAST take):")
    for n in (4, 3):
        seen = {}
        for i in range(len(toks) - n):
            g = " ".join(toks[i:i + n])
            if g in seen and words[i][1] - words[seen[g]][1] < 12:
                j = seen[g]
                lines.append(f"  '{' '.join(w[0] for w in words[j:j + n])}' at {words[j][1]:.2f} repeats at {words[i][1]:.2f}"
                             f"  -> candidate remove {words[j][1]:.2f}-{words[i][1]:.2f}")
            seen[g] = i
    low = [w for w in words if w[3] < 0.4]
    if low:
        lines.append("LOW-CONFIDENCE WORDS (check spelling / names):")
        lines += [f"  {w[1]:7.2f}  '{w[0]}' ({w[3]})" for w in low]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--work", required=True)
    ap.add_argument("--model", default="small", help="whisper size: tiny/base/small/medium/large-v3 (multilingual)")
    ap.add_argument("--language", default="auto")
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    meta = probe(a.video)
    log(f"{meta['width']}x{meta['height']} {meta['fps']}fps {meta['duration']:.1f}s hdr={meta['hdr']}")
    meta["face"] = face_box(a.video, meta)
    log("face:", meta["face"])
    wav = extract_audio(a.video, a.work)
    log(f"transcribing with whisper '{a.model}' (first run downloads the model)...")
    words, lines, lang, lp = transcribe(wav, a.model, a.language)
    meta.update(language=lang, language_prob=round(lp, 2), words=len(words))
    sil = silences(wav)
    save_json(meta, os.path.join(a.work, "meta.json"))
    save_json(words, os.path.join(a.work, "words.json"))
    save_json(sil, os.path.join(a.work, "silences.json"))
    with open(os.path.join(a.work, "segments.txt"), "w", encoding="utf-8") as f:
        f.write(f"language={lang} ({lp:.2f})\n" + "\n".join(lines))
    with open(os.path.join(a.work, "review.txt"), "w", encoding="utf-8") as f:
        f.write(review(words, sil, lang))
    log(f"done: {len(words)} words, language {lang}, {len(sil)} pauses -> {a.work}")


if __name__ == "__main__":
    main()
