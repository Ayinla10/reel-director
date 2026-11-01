"""Music, sound effects and the final mix - all royalty-free (composed / synthesised here).

  python audio.py music --work W --duration 97.2 [--mood hopeful] [--loop] [--breaks 42.8-47.7,77.1-86.3]
  python audio.py music --work W --duration 97.2 --track mysong.mp3 [--loop]      # user's own track, fitted
  python audio.py sfx   --work W                                                    # writes W/sfx/*.wav
  python audio.py mix   --work W [--events W/comp/sfx_events.json] [--music-db -12] [--lufs -14] [--loop]

Outputs W/music.wav, W/sfx/{pop,click,whoosh,impact,riser,ding}.wav, W/final_audio.wav
"""
import argparse
import json
import os
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rdlib import FFMPEG, log, run

SR = 44100
MOODS = {
    #            bpm  chords (midi roots of triads)           minor flags          drums hats arp
    "hopeful":   (96, [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]], 1.0, 0.6, 0.7),
    "upbeat":    (108, [[48, 52, 55], [55, 59, 62], [57, 60, 64], [53, 57, 60]], 1.0, 1.0, 0.8),
    "calm":      (80, [[48, 52, 55], [57, 60, 64], [53, 57, 60], [55, 59, 62]], 0.4, 0.0, 0.5),
    "energetic": (118, [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]], 1.2, 1.2, 1.0),
    "serious":   (88, [[50, 53, 57], [46, 50, 53], [53, 57, 60], [48, 52, 55]], 0.8, 0.4, 0.5),
    "luxury":    (84, [[50, 53, 57, 60], [55, 58, 62, 65], [48, 52, 55, 59], [53, 57, 60, 64]], 0.5, 0.3, 0.4),
}


def write_wav(path, stereo, sr=SR):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    x = np.clip(stereo, -1, 1)
    w = wave.open(path, "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes((x * 32767).astype(np.int16).tobytes()); w.close()


def midi(m):
    return 440 * 2 ** ((m - 69) / 12)


def compose(dur, mood, loop, breaks):
    bpm0, prog, drums, hats, arp_amt = MOODS.get(mood, MOODS["hopeful"])
    bar0 = 4 * 60 / bpm0
    bars = max(4, round(dur / bar0 / 4) * 4) if loop else int(np.ceil(dur / bar0))
    bpm = bars * 4 * 60 / dur if loop else bpm0      # loop: exact whole bars so the seam is invisible
    B = 60 / bpm; bar = 4 * B
    total = dur + 2.0
    N = int(SR * total)
    rng = np.random.default_rng(7)
    level = lambda t: 0.0 if any(a <= t < b for a, b in breaks) else 1.0
    pad = np.zeros(N); bass = np.zeros(N); kick = np.zeros(N); hat = np.zeros(N); arp = np.zeros(N)
    for i in range(int(total / bar) + 1):
        s = int(i * bar * SR); e = min(N, int((i + 1) * bar * SR) + int(0.4 * SR))
        if s >= N:
            break
        tt = np.arange(e - s) / SR; seg = np.zeros(e - s)
        for m in prog[i % 4]:
            for dt in (-0.1, 0.0, 0.09):
                seg += 2 * ((tt * midi(m) * 2 ** (dt / 12) + rng.random()) % 1) - 1
        env = np.minimum(1, tt / 0.6) * np.minimum(1, np.maximum(0, (len(tt) / SR - tt) / 0.5))
        pad[s:e] += seg * env * 0.85 / (3 * len(prog[i % 4]))
    for _ in range(3):
        pad = np.convolve(pad, np.ones(28) / 28, mode="same")
    for j in range(int(total / (B / 2))):
        t0 = j * B / 2; s = int(t0 * SR); n = int(B / 2 * 0.9 * SR)
        if s + n >= N or level(t0) == 0:
            continue
        tt = np.arange(n) / SR; f = midi(prog[int(t0 // bar) % 4][0] - 12)
        bass[s:s + n] += (np.sin(2 * np.pi * f * tt) + 0.25 * np.tanh(3 * np.sin(2 * np.pi * f * tt))) * np.exp(-tt * 5) * 0.5
    for j in range(int(total / B)):
        t0 = j * B; s = int(t0 * SR)
        if level(t0) == 0:
            continue
        if drums and j % 2 == 0 and s + int(0.35 * SR) < N:
            tt = np.arange(int(0.35 * SR)) / SR
            kick[s:s + len(tt)] += drums * np.sin(2 * np.pi * np.cumsum(50 + 90 * np.exp(-tt * 30)) / SR) * np.exp(-tt * 9) * 0.7
        s2 = int((t0 + B / 2) * SR); n = int(0.06 * SR)
        if hats and s2 + n < N:
            nz = np.diff(np.concatenate([[0], rng.standard_normal(n)]))
            hat[s2:s2 + n] += hats * nz * np.exp(-np.arange(n) / SR * 70) * 0.1
    pat = [0, 2, 1, 2, 0, 2, 1, 2]
    for j in range(int(total / (B / 4))):
        t0 = j * B / 4
        if not arp_amt or level(t0) == 0:
            continue
        ch = prog[int(t0 // bar) % 4]; m = ch[pat[j % 8] % len(ch)] + 12
        s = int(t0 * SR); n = int(0.3 * SR)
        if s + n >= N:
            break
        tt = np.arange(n) / SR; f = midi(m)
        arp[s:s + n] += arp_amt * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)) * np.exp(-tt * 14) * 0.12
    pump = np.ones(N)
    for j in range(int(total / B)):
        s = int(j * B * SR); n = int(0.25 * SR)
        if drums and s + n < N and level(j * B):
            pump[s:s + n] = np.minimum(pump[s:s + n], 0.55 + 0.45 * np.linspace(0, 1, n) ** 0.7)
    d = int(0.375 * SR); h = int(0.012 * SR)
    padL = pad * pump; padR = np.zeros(N); padR[h:] = padL[:-h]
    arpR = np.zeros(N); arpR[d:] = arp[:-d] * 0.6
    L = padL + bass + kick + hat + arp; R = padR + bass + kick + hat * 0.8 + arpR
    M = int(dur * SR)
    if loop:  # wrap the tail onto the head: the end flows into the start
        L[:N - M] += L[M:]; R[:N - M] += R[M:]
    L, R = L[:M], R[:M]
    if not loop:
        f = int(2.5 * SR); L[-f:] *= np.linspace(1, 0, f); R[-f:] *= np.linspace(1, 0, f)
    peak = max(np.abs(L).max(), np.abs(R).max()) * 1.12
    return np.stack([L / peak, R / peak], 1)


def fit_track(path, dur, loop, work):
    tmp = os.path.join(work, "_track.wav")
    run([FFMPEG, "-v", "error", "-y", "-i", path, "-ac", "2", "-ar", str(SR), tmp])
    w = wave.open(tmp); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, 2).astype(np.float32) / 32768
    M = int(dur * SR); xf = int(2.0 * SR)
    while len(x) < M + xf:  # repeat with a crossfade
        ramp = np.linspace(0, 1, xf)[:, None]
        x = np.concatenate([x[:-xf], x[-xf:] * (1 - ramp) + x[:xf] * ramp, x[xf:]])
    if loop:
        tail = x[M:M + xf]; ramp = np.linspace(1, 0, len(tail))[:, None]
        x = x[:M].copy(); x[:len(tail)] = x[:len(tail)] * (1 - ramp) + tail * ramp
    else:
        x = x[:M].copy(); f = int(2.5 * SR); x[-f:] *= np.linspace(1, 0, f)[:, None]
    return x


def synth_sfx(work):
    d = os.path.join(work, "sfx"); os.makedirs(d, exist_ok=True)
    rng = np.random.default_rng(3)
    t = lambda s: np.arange(int(s * SR)) / SR

    def save(name, mono):
        mono = mono / (np.abs(mono).max() + 1e-9) * 0.9
        write_wav(os.path.join(d, name + ".wav"), np.stack([mono, mono], 1))
    tt = t(0.18); save("pop", np.sin(2 * np.pi * (900 * tt - 1500 * tt**2)) * np.exp(-tt * 30))
    tt = t(0.05); save("click", rng.standard_normal(len(tt)) * np.exp(-tt * 160) + np.sin(2 * np.pi * 2400 * tt) * np.exp(-tt * 120))
    tt = t(0.55); nz = rng.standard_normal(len(tt))
    sweep = np.convolve(nz, np.ones(6) / 6, "same") * np.sin(np.pi * tt / 0.55) ** 2
    save("whoosh", sweep * (0.4 + 0.6 * tt / 0.55))
    tt = t(0.9); save("impact", np.sin(2 * np.pi * np.cumsum(38 + 80 * np.exp(-tt * 18)) / SR) * np.exp(-tt * 5)
                     + rng.standard_normal(len(tt)) * np.exp(-tt * 40) * 0.5)
    tt = t(3.0); save("riser", (np.convolve(rng.standard_normal(len(tt)), np.ones(4) / 4, "same") * 0.5
                               + np.sin(2 * np.pi * np.cumsum(200 + 900 * (tt / 3) ** 2) / SR) * 0.5) * (tt / 3) ** 2)
    tt = t(0.8); save("ding", (np.sin(2 * np.pi * 1320 * tt) + 0.5 * np.sin(2 * np.pi * 1980 * tt)) * np.exp(-tt * 6))
    log("sfx ->", d)


def mix(work, events, music_db, lufs, loop):
    voice = os.path.join(work, "voice.wav"); music = os.path.join(work, "music.wav")
    dur = float(json.load(open(os.path.join(work, "edl.json")))["duration"])
    ins = ["-i", voice, "-i", music]
    fc = [f"[0:a]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{dur},asplit=2[v][key]",
          f"[1:a]aresample=48000,volume={music_db}dB[mus]",
          "[mus][key]sidechaincompress=threshold=0.03:ratio=5:attack=25:release=400:makeup=1[duck]"]
    lab = ["[v]", "[duck]"]
    for i, e in enumerate(events):
        ms = max(0, int(e["t"] * 1000))
        ins += ["-i", os.path.join(work, "sfx", e["sfx"] + ".wav")]
        fc.append(f"[{i + 2}:a]aresample=48000,volume={e.get('gain', -14)}dB,adelay={ms}|{ms}[s{i}]")
        lab.append(f"[s{i}]")
    fc.append("".join(lab) + f"amix=inputs={len(lab)}:normalize=0:duration=longest,atrim=0:{dur},"
              f"loudnorm=I={lufs}:TP=-1.0:LRA=10[a]")
    script = os.path.join(work, "mix_graph.txt"); open(script, "w").write(";".join(fc))
    run([FFMPEG, "-v", "error", "-y", *ins, "-/filter_complex", script, "-map", "[a]", "-c:a", "pcm_s16le",
         os.path.join(work, "final_audio.wav")])
    log("mix ->", os.path.join(work, "final_audio.wav"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["music", "sfx", "mix"])
    ap.add_argument("--work", required=True)
    ap.add_argument("--duration", type=float)
    ap.add_argument("--mood", default="hopeful"); ap.add_argument("--track")
    ap.add_argument("--loop", action="store_true"); ap.add_argument("--breaks", default="")
    ap.add_argument("--events"); ap.add_argument("--music-db", type=float, default=-12)
    ap.add_argument("--lufs", type=float, default=-14)
    a = ap.parse_args()
    if a.cmd == "sfx":
        return synth_sfx(a.work)
    if a.cmd == "mix":
        ev = json.load(open(a.events)) if a.events and os.path.exists(a.events) else []
        return mix(a.work, ev, a.music_db, a.lufs, a.loop)
    dur = a.duration or float(json.load(open(os.path.join(a.work, "edl.json")))["duration"])
    breaks = [tuple(map(float, b.split("-"))) for b in a.breaks.split(",") if b]
    x = fit_track(a.track, dur, a.loop, a.work) if a.track else compose(dur, a.mood, a.loop, breaks)
    write_wav(os.path.join(a.work, "music.wav"), x)
    log(f"music ({'track' if a.track else a.mood}{', loop' if a.loop else ''}) -> {os.path.join(a.work, 'music.wav')}")


if __name__ == "__main__":
    main()
