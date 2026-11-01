"""Build a per-video colour grade as a 3D LUT (.cube) and preview it.

Methods (pick with --method):
  preset     a named look from assets/looks.json (bright-blue, bright-clean, warm-film, moody, mono ...)
  reference  match a reference: screenshots/stills or a video file (measures wall, skin, shadows)
  pair       learn the user's own preset from a BEFORE/AFTER still pair exported from any app
             (CapCut, VN, Lightroom, Snapseed, InShot ...) - reproduces that preset exactly
  cube       use the user's .cube LUT (Premiere/Lumetri, Resolve, Final Cut, Photoshop exports)

Every method starts from auto exposure + white balance so any phone's footage begins from the same
place, and (except pair/cube, which are the user's own look) protects skin: the background/highlights
take the brand tint while skin tones keep their natural, warm hue.

  python grade.py --video in.mov --method preset --look bright-blue --out work/grade
  python grade.py --video in.mov --method reference --ref ref1.png ref2.png --out work/grade
  python grade.py --video in.mov --method pair --before b.png --after a.png --out work/grade
  python grade.py --video in.mov --method cube --cube mylook.cube --intensity 0.8 --out work/grade

Writes <out>/grade.cube, <out>/preview.jpg (original | graded, 3 moments), <out>/grade.json (measurements).
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rdlib import grab_frames, hdr_filter, load_image, log, luma, probe, save_image, save_json, ycbcr

HERE = os.path.dirname(os.path.abspath(__file__))
N = 33  # LUT size


# ---------------------------------------------------------------- analysis
def skin_mask(img):
    """Skin likelihood for all skin tones (YCbCr cluster, works dark to light)."""
    y, cb, cr = ycbcr(img)
    m = (cr > 0.53) & (cr < 0.70) & (cb > 0.33) & (cb < 0.53) & (y > 0.08) & (y < 0.92)
    return m


def from_ycbcr(y, cb, cr):
    r = y + (cr - 0.5) / 0.713
    b = y + (cb - 0.5) / 0.564
    g = (y - 0.299 * r - 0.114 * b) / 0.587
    return np.stack([r, g, b], -1)


def analyze(frames):
    px = np.concatenate([f.reshape(-1, 3) for f in frames])
    sk = np.concatenate([skin_mask(f).reshape(-1) for f in frames])
    L = luma(px)
    _, cbp, crp = ycbcr(px)
    chroma = np.hypot(cbp - 0.5, crp - 0.5)
    # background = bright, low-chroma, non-skin pixels (ignores caption boxes, logos, UI)
    cand = (~sk) & (chroma <= np.percentile(chroma, 80))
    nonskin = px[cand] if cand.sum() > 100 else px
    Lns = luma(nonskin)
    hi = nonskin[(Lns >= np.percentile(Lns, 60)) & (Lns <= np.percentile(Lns, 97))]
    lo = px[L <= np.percentile(L, 8)]
    skin = px[sk] if sk.sum() > 200 else None
    _, cb, cr = ycbcr(px)
    stats = {
        "bg_rgb": np.median(hi, 0).tolist(),
        "shadow_rgb": lo.mean(0).tolist(),
        "black": float(np.percentile(L, 0.7)),
        "white": float(np.percentile(L, 99.6)),
        "mid": float(np.median(L)),
        "chroma": float(np.mean(np.hypot(cb - 0.5, cr - 0.5))),
        "skin_frac": float(sk.mean()),
    }
    if skin is not None:
        sy, scb, scr = ycbcr(skin)
        stats.update(skin_rgb=np.median(skin, 0).tolist(), skin_y=float(np.median(sy)),
                     skin_cb=float(np.median(scb)), skin_cr=float(np.median(scr)),
                     skin_sd=[float(np.std(scb)), float(np.std(scr))])
    return stats


# ---------------------------------------------------------------- curve helpers
def pchip(xs, ys, x):
    """Monotone cubic interpolation (no overshoot) - smooth tone curves without numpy extras."""
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    h = np.diff(xs); d = np.diff(ys) / h
    m = np.zeros_like(ys)
    for k in range(1, len(xs) - 1):
        if d[k - 1] * d[k] > 0:
            w1, w2 = 2 * h[k] + h[k - 1], h[k] + 2 * h[k - 1]
            m[k] = (w1 + w2) / (w1 / d[k - 1] + w2 / d[k])
    m[0], m[-1] = d[0], d[-1]
    x = np.clip(x, xs[0], xs[-1])
    k = np.clip(np.searchsorted(xs, x) - 1, 0, len(h) - 1)
    t = (x - xs[k]) / h[k]
    h00, h10, h01, h11 = 2 * t**3 - 3 * t**2 + 1, t**3 - 2 * t**2 + t, -2 * t**3 + 3 * t**2, t**3 - t**2
    return h00 * ys[k] + h10 * h[k] * m[k] + h01 * ys[k + 1] + h11 * h[k] * m[k + 1]


def identity_grid(n=N):
    r = np.linspace(0, 1, n)
    b, g, rr = np.meshgrid(r, r, r, indexing="ij")
    return np.stack([rr, g, b], -1)  # [b][g][r] -> rgb, matches .cube ordering (r fastest)


def apply_lut(lut, img):
    """Trilinear lookup of an (n,n,n,3) [b][g][r] LUT."""
    n = lut.shape[0]
    p = np.clip(img, 0, 1) * (n - 1)
    i0 = np.floor(p).astype(int); i1 = np.minimum(i0 + 1, n - 1); f = p - i0
    r0, g0, b0 = i0[..., 0], i0[..., 1], i0[..., 2]
    r1, g1, b1 = i1[..., 0], i1[..., 1], i1[..., 2]
    fr, fg, fb = f[..., 0:1], f[..., 1:2], f[..., 2:3]
    c = lambda b, g, r: lut[b, g, r]
    c00 = c(b0, g0, r0) * (1 - fr) + c(b0, g0, r1) * fr
    c01 = c(b0, g1, r0) * (1 - fr) + c(b0, g1, r1) * fr
    c10 = c(b1, g0, r0) * (1 - fr) + c(b1, g0, r1) * fr
    c11 = c(b1, g1, r0) * (1 - fr) + c(b1, g1, r1) * fr
    return (c00 * (1 - fg) + c01 * fg) * (1 - fb) + (c10 * (1 - fg) + c11 * fg) * fb


def write_cube(lut, path, title="reel-director"):
    n = lut.shape[0]
    with open(path, "w") as f:
        f.write(f'TITLE "{title}"\nLUT_3D_SIZE {n}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n')
        for row in np.clip(lut, 0, 1).reshape(-1, 3):
            f.write(f"{row[0]:.6f} {row[1]:.6f} {row[2]:.6f}\n")


def read_cube(path):
    size, rows, dmin, dmax = None, [], np.zeros(3), np.ones(3)
    for line in open(path, encoding="utf-8", errors="ignore"):
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("TITLE"):
            continue
        if s.startswith("LUT_3D_SIZE"):
            size = int(s.split()[1]); continue
        if s.startswith("DOMAIN_MIN"):
            dmin = np.array(list(map(float, s.split()[1:4]))); continue
        if s.startswith("DOMAIN_MAX"):
            dmax = np.array(list(map(float, s.split()[1:4]))); continue
        if s.startswith("LUT_1D_SIZE"):
            raise SystemExit("1D LUTs aren't supported - export a 3D .cube (LUT_3D_SIZE) from your editor.")
        parts = s.split()
        if len(parts) == 3:
            try:
                rows.append([float(v) for v in parts])
            except ValueError:
                pass
    if not size or len(rows) != size**3:
        raise SystemExit(f"Couldn't read {path} as a 3D .cube LUT.")
    lut = np.array(rows).reshape(size, size, size, 3)
    return (lut - dmin) / (dmax - dmin)


def resample(lut, n=N):
    return apply_lut(lut, identity_grid(n))


# ---------------------------------------------------------------- the grade model
def build_grade(src, tgt, opts):
    """src/tgt: analysis dicts (tgt may be a look preset). Returns an (N,N,N,3) LUT."""
    g = identity_grid()
    x = g.reshape(-1, 3)
    sb, sw = src["black"], max(src["white"], src["black"] + 0.2)
    tb, tw = tgt.get("black", 0.02), tgt.get("white", 0.97)
    smid = np.clip((src["mid"] - sb) / (sw - sb), 0.05, 0.95) * (tw - tb) + tb
    tmid = tgt["mid"] if "mid" in tgt else float(np.clip(smid, tgt.get("min_mid", 0), tgt.get("max_mid", 1)))
    gamma = np.log(np.clip((tmid - tb) / (tw - tb), 0.05, 0.95)) / np.log(np.clip((smid - tb) / (tw - tb), 0.05, 0.95))
    gamma = float(np.clip(gamma, 0.6, 1.6))
    s_bg = np.clip(np.array(src["bg_rgb"]), 1e-3, 1)
    wb = 1 + (s_bg.mean() / s_bg - 1) * tgt.get("wb_strength", 1.0)

    def stage1(c):
        """Auto exposure (levels + mid gamma on luma, hue kept) then auto white balance."""
        L = luma(c)
        Ln = np.clip((L - sb) / (sw - sb), 0, 1.2) * (tw - tb) + tb
        Ln = tb + (tw - tb) * np.clip((Ln - tb) / (tw - tb), 0, 1.5) ** gamma
        ratio = np.where(L > 1e-4, Ln / np.maximum(L, 1e-4), 1.0)
        return np.clip(c * ratio[..., None] * wb, 0, 1)

    # 1) exposure + white balance
    base = stage1(x)

    # 2) brand tint: per-channel curves that pass the measured background exactly onto the target
    bg1 = stage1(np.array([src["bg_rgb"]]))[0]
    t_bg = np.array(tgt.get("bg_rgb", bg1))
    t_sh = np.array(tgt.get("shadow_tint", [0, 0, 0]))  # small offsets added to shadows (e.g. navy/teal)
    out = np.empty_like(base)
    for c in range(3):
        bx = float(np.clip(bg1[c], 0.3, 0.97))
        xs = [0.0, 0.2, bx, 1.0]
        ys = [tb, 0.2 + t_sh[c], float(t_bg[c]), float(np.clip(t_bg[c] + (1 - bx) * 0.9, t_bg[c], 1.0))]
        ys = np.maximum.accumulate(np.array(ys))
        out[:, c] = pchip(xs, ys, base[:, c])

    # 3) contrast (S-curve on luma) and saturation
    k = tgt.get("contrast", 0.0)
    Lo = luma(out)
    Ls = Lo + k * (Lo - 0.5) * (1 - np.abs(2 * Lo - 1))
    out = out * (np.where(Lo > 1e-4, Ls / np.maximum(Lo, 1e-4), 1))[:, None]
    sat = tgt.get("saturation", 1.0)
    Lo = luma(out)[:, None]
    glob = np.clip(Lo + (out - Lo) * sat, 0, 1)

    # 4) skin path: same exposure + white balance, then skin's own brightness and hue targets
    if src.get("skin_cr") is not None and tgt.get("skin_protect", 0.85) > 0:
        sk = base.copy()
        s1 = stage1(np.array([src["skin_rgb"]]))[0]
        s1y, s1cb, s1cr = [float(v) for v in ycbcr(s1)]
        gain = tgt.get("skin_gain", 1.0)
        if "skin_y" in tgt:  # absolute target from a reference, relative to its background
            gain = tgt["skin_y"] / max(s1y, 1e-3)
        gain = float(np.clip(gain, 0.8, 1.45))
        y, cb, cr = ycbcr(sk)
        y = np.clip(y * gain, 0, 1)
        tcb = tgt.get("skin_cb", s1cb + tgt.get("skin_warmth", [0, 0])[1])
        tcr = tgt.get("skin_cr", s1cr + tgt.get("skin_warmth", [0, 0])[0])
        k = tgt.get("skin_match", 0.6)
        cb = cb + (tcb - s1cb) * k
        cr = cr + (tcr - s1cr) * k
        ss = tgt.get("skin_saturation", 1.05)
        cb = 0.5 + (cb - 0.5) * ss; cr = 0.5 + (cr - 0.5) * ss
        sk = np.clip(from_ycbcr(y, cb, cr), 0, 1)
        # skin likelihood of every LUT node, measured around THIS person's skin cluster
        _, xcb, xcr = ycbcr(x)
        sdb, sdr = src.get("skin_sd", [0.02, 0.025])
        dcb = (xcb - src["skin_cb"]) / max(3.0 * sdb, 0.035)
        dcr = (xcr - src["skin_cr"]) / max(3.0 * sdr, 0.04)
        w = np.exp(-0.5 * (dcb**2 + dcr**2))
        Ly = luma(x)
        w *= np.clip((Ly - 0.02) / 0.06, 0, 1) * np.clip((0.95 - Ly) / 0.12, 0, 1)
        w = (w * tgt.get("skin_protect", 0.85))[:, None]
        glob = glob * (1 - w) + sk * w

    lut = glob.reshape(g.shape)
    inten = opts.get("intensity", 1.0)
    return np.clip(g + (lut - g) * inten, 0, 1)


def calibrated(src, tgt, frames, opts, iters=4):
    """Closed loop: build, measure the graded frames, nudge targets by the error, repeat.
    Guarantees the background (and, when the target has one, the skin) lands on the target colour."""
    want_bg = np.array(tgt["bg_rgb"]) if "bg_rgb" in tgt else None
    want_skin = None
    if "skin_y" in tgt:
        want_skin = np.array([tgt["skin_y"], tgt["skin_cb"], tgt["skin_cr"]])
    t = dict(tgt)
    lut = build_grade(src, t, opts)
    for _ in range(iters):
        m = analyze([apply_lut(lut, f) for f in frames])
        moved = False
        if want_bg is not None:
            err = want_bg - np.array(m["bg_rgb"])
            if np.abs(err).max() > 0.006:
                t["bg_rgb"] = np.clip(np.array(t["bg_rgb"]) + err * 0.9, 0.05, 1.0).tolist(); moved = True
        if want_skin is not None and m.get("skin_y") is not None:
            err = want_skin - np.array([m["skin_y"], m["skin_cb"], m["skin_cr"]])
            if np.abs(err).max() > 0.004:
                t["skin_y"] += err[0] * 0.9; t["skin_cb"] += err[1] * 0.9; t["skin_cr"] += err[2] * 0.9; moved = True
        if not moved:
            break
        lut = build_grade(src, t, opts)
    return lut


# ---------------------------------------------------------------- learning a preset from a still pair
def fit_pair(before, after, n=17):
    """Learn any app's preset from the same frame exported without and with it."""
    if before.shape != after.shape:
        from PIL import Image
        ah, aw = before.shape[:2]
        after = np.asarray(Image.fromarray((after * 255).astype(np.uint8)).resize((aw, ah)), np.float32) / 255
    b = before.reshape(-1, 3); a = after.reshape(-1, 3)
    # global smooth model (2nd-order polynomial) for colours the still doesn't contain
    def feats(c):
        r, g_, bb = c[:, 0], c[:, 1], c[:, 2]
        return np.stack([np.ones_like(r), r, g_, bb, r * r, g_ * g_, bb * bb, r * g_, g_ * bb, r * bb], 1)
    coef, *_ = np.linalg.lstsq(feats(b), a, rcond=None)
    grid = identity_grid(n).reshape(-1, 3)
    poly = feats(grid) @ coef
    # local averages where the still has data, blended by confidence
    idx = np.clip(np.round(b * (n - 1)).astype(int), 0, n - 1)
    flat = idx[:, 2] * n * n + idx[:, 1] * n + idx[:, 0]
    cnt = np.bincount(flat, minlength=n**3).astype(float)
    acc = np.stack([np.bincount(flat, weights=a[:, c], minlength=n**3) for c in range(3)], 1)
    local = np.where(cnt[:, None] > 0, acc / np.maximum(cnt[:, None], 1), poly)
    conf = (cnt / (cnt + 8.0))[:, None]
    lut = (local * conf + poly * (1 - conf)).reshape(n, n, n, 3)
    # light 3x3x3 smoothing to remove JPEG noise
    pad = np.pad(lut, ((1, 1), (1, 1), (1, 1), (0, 0)), mode="edge")
    sm = sum(pad[i:i + n, j:j + n, k:k + n] for i in range(3) for j in range(3) for k in range(3)) / 27
    lut = lut * 0.5 + sm * 0.5
    return resample(np.clip(lut, 0, 1))


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--method", choices=["preset", "reference", "pair", "cube"], default="preset")
    ap.add_argument("--look", default="bright-clean")
    ap.add_argument("--ref", nargs="*", default=[], help="reference stills and/or a reference video")
    ap.add_argument("--before"); ap.add_argument("--after"); ap.add_argument("--cube")
    ap.add_argument("--intensity", type=float, default=1.0)
    ap.add_argument("--skin-protect", type=float, default=None)
    ap.add_argument("--hdr", choices=["compat", "tonemap"], default="compat")
    ap.add_argument("--normalize", action="store_true",
                    help="pair/cube: auto exposure + white balance before the user's look (off = apply it exactly)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    meta = probe(a.video)
    pre = hdr_filter(meta, a.hdr)
    times = [meta["duration"] * f for f in (0.12, 0.3, 0.45, 0.6, 0.75, 0.9)]
    frames = grab_frames(a.video, times, 320, pre)
    src = analyze(frames)
    looks = json.load(open(os.path.join(HERE, "..", "assets", "looks.json"), encoding="utf-8"))

    if a.method == "preset":
        if os.path.exists(a.look):  # a creator's own look file (same fields as assets/looks.json entries)
            tgt = json.load(open(a.look, encoding="utf-8"))
        elif a.look in looks:
            tgt = dict(looks[a.look])
        else:
            raise SystemExit(f"unknown look '{a.look}'. Available: {', '.join(looks)} (or a path to a look .json)")
        tgt["bg_rgb"] = [c / 255 for c in tgt["bg_rgb"]]
        if a.skin_protect is not None:
            tgt["skin_protect"] = a.skin_protect
        lut = calibrated(src, tgt, frames, {"intensity": a.intensity})
    elif a.method == "reference":
        rf = []
        for r in a.ref:
            if r.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
                rf.append(load_image(r, 320))
            else:
                m = probe(r)
                rf += grab_frames(r, [m["duration"] * f for f in (0.2, 0.4, 0.6, 0.8)], 320, hdr_filter(m, a.hdr))
        if not rf:
            raise SystemExit("reference method needs --ref images or a video")
        ref = analyze(rf)
        tgt = {"black": ref["black"], "white": ref["white"], "mid": ref["mid"], "bg_rgb": ref["bg_rgb"],
               "shadow_tint": (np.array(ref["shadow_rgb"]) - np.mean(ref["shadow_rgb"])).tolist(),
               "saturation": float(np.clip(ref["chroma"] / max(src["chroma"], 1e-3), 0.8, 1.25)),
               "contrast": 0.08, "skin_protect": 0.85}
        if ref.get("skin_y") is not None and src.get("skin_y") is not None:
            # keep the reference's skin-to-wall brightness relationship and its skin hue
            tgt["skin_y"] = ref["skin_y"]
            tgt["skin_cb"], tgt["skin_cr"] = ref["skin_cb"], ref["skin_cr"]
        if a.skin_protect is not None:
            tgt["skin_protect"] = a.skin_protect
        tgt["ref_stats"] = ref
        lut = calibrated(src, tgt, frames, {"intensity": a.intensity})
    elif a.method == "pair":
        if not (a.before and a.after):
            raise SystemExit("pair method needs --before and --after stills of the same frame")
        b = load_image(a.before, 640); af = load_image(a.after, 640)
        user = fit_pair(b, af)
        if a.normalize:
            neutral = build_grade(src, {"black": 0.02, "white": 0.96, "skin_protect": 0,
                                        "bg_rgb": [float(np.mean(src["bg_rgb"]))] * 3, "wb_strength": 0.6}, {})
            lut = apply_lut(user, neutral)
        else:
            lut = user
        lut = identity_grid() + (lut - identity_grid()) * a.intensity
        tgt = {"method": "pair"}
    else:
        if not a.cube:
            raise SystemExit("cube method needs --cube path")
        user = resample(read_cube(a.cube))
        if a.normalize:
            neutral = build_grade(src, {"black": 0.02, "white": 0.96, "skin_protect": 0,
                                        "bg_rgb": [float(np.mean(src["bg_rgb"]))] * 3, "wb_strength": 0.6}, {})
            lut = apply_lut(user, neutral)
        else:
            lut = user
        lut = identity_grid() + (lut - identity_grid()) * a.intensity
        tgt = {"method": "cube"}

    cube = os.path.join(a.out, "grade.cube")
    write_cube(lut, cube)
    graded = [apply_lut(lut, f) for f in frames]
    after = analyze(graded)
    # preview: original | graded for 3 moments, side by side
    pick = [frames[1], frames[3], frames[5]] if len(frames) >= 6 else frames[:3]
    gp = [apply_lut(lut, f) for f in pick]
    h = min(f.shape[0] for f in pick)
    cols = [np.concatenate([o[:h], gr[:h]], 1) for o, gr in zip(pick, gp)]
    save_image(np.concatenate(cols, 1), os.path.join(a.out, "preview.jpg"))
    fmt = lambda v: [round(c * 255) for c in v] if isinstance(v, list) else v
    report = {"method": a.method, "look": a.look if a.method == "preset" else None, "hdr": meta["hdr"],
              "source": {k: fmt(v) for k, v in src.items() if k in ("bg_rgb", "skin_rgb", "shadow_rgb")},
              "graded": {k: fmt(v) for k, v in after.items() if k in ("bg_rgb", "skin_rgb", "shadow_rgb")},
              "target_bg": fmt(list(tgt.get("bg_rgb", []))) if isinstance(tgt.get("bg_rgb"), list) else None,
              "cube": os.path.abspath(cube)}
    save_json(report, os.path.join(a.out, "grade.json"))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
