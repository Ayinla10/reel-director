"""Real sound effects: CC0 recordings fetched once from Openverse (mostly Freesound), cached in
~/.reel-director/sfx/, with synthesized fallbacks so a run never fails offline.

The keyboard set is sliced from a real typing recording into individual keystrokes, so every
character typed on screen gets its own key sound (space bar and Enter are heavier).
"""
import json
import os
import re
import urllib.parse
import urllib.request
import wave

import numpy as np

from rdlib import FFMPEG, log, run

SR = 48000
CACHE = os.path.join(os.path.expanduser("~"), ".reel-director", "sfx")
UA = {"User-Agent": "reel-director/1.0 (https://github.com/Ayinla10/reel-director)"}

# name -> (search query, min ms, max ms)
CATALOG = {
    "click":      ("mouse click", 30, 1500),
    "pop":        ("pop", 40, 700),
    "pop2":       ("bubble pop", 40, 700),
    "whoosh":     ("swipe whoosh", 150, 900),
    "whoosh2":    ("swoosh", 150, 1000),
    "whoosh_deep": ("deep whoosh", 600, 4000),
    "ding":       ("ding", 150, 1600),
    "notify":     ("notification sound", 150, 1500),
    "swoosh_up":  ("message sent", 150, 1800),
    "tick":       ("clock tick", 20, 500),
    "shutter":    ("camera shutter", 100, 900),
    "impact":     ("cinematic impact|boom hit|bass drop|thud", 300, 5000),
    "riser":      ("riser", 1500, 9000),
    "glitch":     ("glitch", 100, 1500),
    "cash":       ("cash register", 200, 2500),
    "success":    ("success chime|success|positive notification|achievement", 300, 3000),
    "typing_src": ("mechanical keyboard typing", 4000, 60000),
}


def _get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _load(path):
    w = wave.open(path)
    ch, n = w.getnchannels(), w.getnframes()
    x = np.frombuffer(w.readframes(n), np.int16).astype(np.float32) / 32768
    return x.reshape(-1, ch).mean(1) if ch > 1 else x


def _save(path, mono):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    m = mono / (np.abs(mono).max() + 1e-9) * 0.9
    w = wave.open(path, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((m * 32767).astype(np.int16).tobytes()); w.close()


def _fetch(name, queries, lo, hi, credits):
    for query in queries.split("|"):  # alternative wordings, first match wins
        got = _fetch_one(name, query, lo, hi, credits)
        if got:
            return got
    return None


def _fetch_one(name, query, lo, hi, credits):
    d = json.loads(_get("https://api.openverse.org/v1/audio/?" + urllib.parse.urlencode(
        {"q": query, "license": "cc0", "page_size": 20}), 30))
    for r in d.get("results", []):
        dur = r.get("duration") or 0
        if not (lo <= dur <= hi) or not r.get("url"):
            continue
        raw = os.path.join(CACHE, "_dl", re.sub(r"\W", "_", name) + "." + (r.get("filetype") or "mp3"))
        os.makedirs(os.path.dirname(raw), exist_ok=True)
        try:
            open(raw, "wb").write(_get(r["url"]))
            out = os.path.join(CACHE, name + ".wav")
            run([FFMPEG, "-v", "error", "-y", "-i", raw, "-ac", "1", "-ar", str(SR), "-af",
                 "silenceremove=start_periods=1:start_threshold=-50dB", out])
            credits.append(f"{name}: \"{r.get('title')}\" by {r.get('creator') or 'unknown'} (CC0) {r.get('foreign_landing_url') or r['url']}")
            return out
        except Exception:
            continue
    return None


def _slice_keys(src):
    """Cut a typing recording into single keystrokes (onset detection)."""
    x = _load(src)
    if len(x) < SR:
        return 0
    env = np.maximum.accumulate(np.abs(x).reshape(-1, 48)[:, ::-1], axis=1)[:, 0] if False else \
        np.array([np.abs(x[i:i + 240]).max() for i in range(0, len(x) - 240, 240)])  # 5 ms frames
    thr = np.percentile(env, 99) * 0.35
    onsets, last = [], -100
    for i, v in enumerate(env):
        if v > thr and env[max(0, i - 1)] <= thr and i - last > 14:  # >=70 ms apart
            onsets.append(i * 240); last = i
    keys = []
    for o in onsets:
        s = max(0, o - 120); e = s + int(0.13 * SR)
        if e > len(x):
            break
        k = x[s:e].copy()
        fade = int(0.04 * SR); k[-fade:] *= np.linspace(1, 0, fade)
        if np.abs(k).max() > thr:
            keys.append(k)
    if len(keys) < 6:
        return 0
    # rank by "weight" (low-frequency energy x length): heaviest become space/enter
    weight = [float(np.abs(np.convolve(k, np.ones(40) / 40, "same")).sum()) for k in keys]
    order = np.argsort(weight)
    _save(os.path.join(CACHE, "key_space.wav"), keys[order[-1]])
    _save(os.path.join(CACHE, "key_enter.wav"), keys[order[-2]])
    normal = [keys[i] for i in order[len(order) // 6: -2]][:24]
    for i, k in enumerate(normal):
        _save(os.path.join(CACHE, f"key_{i:02d}.wav"), k)
    return len(normal)


# ---------------------------------------------------------------- synthesized fallbacks
def _synth(name):
    rng = np.random.default_rng(abs(hash(name)) % 2**32)
    t = lambda s: np.arange(int(s * SR)) / SR
    if name.startswith("key"):
        tt = t(0.09); n = rng.standard_normal(len(tt))
        body = np.sin(2 * np.pi * (180 if "space" in name or "enter" in name else 320) * tt) * np.exp(-tt * 60)
        return (np.convolve(n, np.ones(3) / 3, "same") * np.exp(-tt * 140) * 0.7 + body * 0.6)
    if name in ("pop", "pop2"):
        tt = t(0.18); return np.sin(2 * np.pi * (900 * tt - 1500 * tt**2)) * np.exp(-tt * 30)
    if name in ("click", "tick", "shutter"):
        tt = t(0.05); return rng.standard_normal(len(tt)) * np.exp(-tt * 160) + np.sin(2 * np.pi * 2400 * tt) * np.exp(-tt * 120)
    if name.startswith("whoosh") or name == "swoosh_up":
        L = 1.2 if name == "whoosh_deep" else 0.55; tt = t(L)
        return np.convolve(rng.standard_normal(len(tt)), np.ones(6) / 6, "same") * np.sin(np.pi * tt / L) ** 2
    if name == "impact":
        tt = t(0.9); return np.sin(2 * np.pi * np.cumsum(38 + 80 * np.exp(-tt * 18)) / SR) * np.exp(-tt * 5)
    if name == "riser":
        tt = t(3.0); return np.sin(2 * np.pi * np.cumsum(200 + 900 * (tt / 3) ** 2) / SR) * (tt / 3) ** 2
    tt = t(0.8)  # ding / notify / success / cash / glitch
    return (np.sin(2 * np.pi * 1320 * tt) + 0.5 * np.sin(2 * np.pi * 1980 * tt)) * np.exp(-tt * 6)


def ensure_library(offline=False):
    """Download (once) and prepare the library. Returns the cache dir."""
    os.makedirs(CACHE, exist_ok=True)
    credits = []
    cfile = os.path.join(CACHE, "credits.txt")
    if os.path.exists(cfile):
        credits = open(cfile, encoding="utf-8").read().splitlines()
    for name, (q, lo, hi) in CATALOG.items():
        out = os.path.join(CACHE, name + ".wav")
        if os.path.exists(out) or offline:
            continue
        try:
            got = _fetch(name, q, lo, hi, credits)
            log(f"  sfx {name}: {'CC0 recording' if got else 'not found, will synthesize'}")
        except Exception as e:
            log(f"  sfx {name}: offline/failed ({type(e).__name__}), will synthesize")
    if not os.path.exists(os.path.join(CACHE, "key_00.wav")) and os.path.exists(os.path.join(CACHE, "typing_src.wav")):
        n = _slice_keys(os.path.join(CACHE, "typing_src.wav"))
        log(f"  keyboard: {n} real keystrokes sliced" if n else "  keyboard: slicing failed, will synthesize")
    open(cfile, "w", encoding="utf-8").write("\n".join(dict.fromkeys(credits)) + "\n")
    return CACHE


_bank = {}


def sound(name, var=0):
    """Mono float array for a named sound (real if cached, else synthesized). `var` picks a keystroke."""
    if name == "key":
        keys = sorted(f for f in os.listdir(CACHE) if re.match(r"key_\d\d\.wav$", f)) if os.path.isdir(CACHE) else []
        name = keys[var % len(keys)][:-4] if keys else "key"
    if name not in _bank:
        p = os.path.join(CACHE, name + ".wav")
        _bank[name] = _load(p) if os.path.exists(p) else _synth(name)
    return _bank[name]


def render_track(events, dur):
    """Place every event (name, time, gain dB, var) into one stereo track - unlimited events, fast."""
    out = np.zeros((int(dur * SR) + SR, 2), np.float32)
    for e in events:
        s = sound(e["sfx"], e.get("var", 0)) * (10 ** (e.get("gain", -14) / 20))
        i = int(max(0, e["t"]) * SR)
        if i >= len(out):
            continue
        s = s[: len(out) - i]
        pan = e.get("pan", 0.0)
        out[i:i + len(s), 0] += s * (1 - max(0, pan)); out[i:i + len(s), 1] += s * (1 + min(0, pan))
    return out[: int(dur * SR)]
