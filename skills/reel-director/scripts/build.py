"""Step 5 - turn the brand profile + this video's plan (beats.json) into a HyperFrames composition.

  python build.py --work W --profile ~/.reel-director/profiles/<name>.json --beats W/beats.json

Creates W/comp/ (index.html, data.js, reel.js, reel.css, gsap, fonts, base.mp4) and
W/sfx_events.json + W/music_breaks.txt derived from the effects.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rdlib import hex_to_rgb, load_json, log, save_json

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME = os.path.join(HERE, "..", "assets", "runtime")
FORMATS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}
GSAP_VERSION = "3.13.0"


def mix(c1, c2, t):
    a, b = hex_to_rgb(c1), hex_to_rgb(c2)
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def rgba(c, a):
    r, g, b = hex_to_rgb(c)
    return f"rgba({r},{g},{b},{a})"


def is_dark(c):
    r, g, b = hex_to_rgb(c)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) < 140


def slug(family):
    return family.strip().lower().replace(" ", "-")


def install_fonts_and_gsap(comp, families):
    """npm-install GSAP and open-licensed (OFL) fontsource packages next to the composition
    (not inside it, so the renderer never scans node_modules) and copy just the files needed."""
    pkgs = [f"gsap@{GSAP_VERSION}"] + [f"@fontsource/{slug(f)}" for f in families]
    npm = shutil.which("npm") or shutil.which("npm.cmd") or "npm"
    nm_root = os.path.join(os.path.dirname(comp), "_npm")
    p = subprocess.run([npm, "install", "--prefix", nm_root, "--no-audit", "--no-fund", "--loglevel=error", *pkgs],
                       capture_output=True, text=True)
    if p.returncode != 0:
        log("npm install had problems (fonts may fall back to system fonts):", p.stderr[-400:])
    g = os.path.join(nm_root, "node_modules", "gsap", "dist", "gsap.min.js")
    if not os.path.exists(g):
        raise SystemExit("GSAP couldn't be installed - check your internet connection / npm and retry.")
    shutil.copy(g, os.path.join(comp, "gsap.min.js"))
    faces = []
    os.makedirs(os.path.join(comp, "fonts"), exist_ok=True)
    for fam in families:
        d = os.path.join(nm_root, "node_modules", "@fontsource", slug(fam), "files")
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith(".woff2") and "-latin-" in f and "-ext-" not in f:
                parts = f[:-6].split("-")
                w, style = parts[-2], parts[-1]
                if not w.isdigit():
                    continue
                shutil.copy(os.path.join(d, f), os.path.join(comp, "fonts", f))
                faces.append(f'@font-face{{font-family:"{fam}";src:url("fonts/{f}") format("woff2");font-weight:{w};font-style:{style};font-display:block}}')
    return faces


def custom_fonts(comp, files):
    faces = []
    for role, path in (files or {}).items():
        if path and os.path.exists(path):
            name = f"Brand{role.capitalize()}"
            dst = os.path.join(comp, "fonts", os.path.basename(path))
            shutil.copy(path, dst)
            ext = os.path.splitext(path)[1].lower().lstrip(".")
            fmt = {"ttf": "truetype", "otf": "opentype", "woff": "woff", "woff2": "woff2"}.get(ext, ext)
            faces.append(f'@font-face{{font-family:"{name}";src:url("fonts/{os.path.basename(path)}") format("{fmt}");font-display:block}}')
    return faces


def _jit(i, seed):
    """Deterministic 0..1 jitter (renders must be reproducible)."""
    return ((i * 9301 + seed * 49297 + 233280) % 233280) / 233280.0


def key_schedule(text, start, latest_end, seed=7):
    """Human-like typing: ~13 chars/s, quicker inside words, small pauses after spaces/punctuation,
    sped up if it would not finish by latest_end. Returns one time per character."""
    gaps = []
    for i, ch in enumerate(text):
        g = 0.055 + 0.05 * _jit(i, seed)
        if ch == " ":
            g += 0.035
        if i and text[i - 1] in ",.?!:;":
            g += 0.16
        gaps.append(g)
    total = sum(gaps)
    k = min(1.0, max(0.25, (latest_end - start) / total)) if total else 1.0
    t, out = start, []
    for g in gaps:
        out.append(round(t, 3)); t += g * k
    return out


def prepare_typing(b):
    """Fill b['_keys'] (+ derived times) for kinds that type text, so visuals and sounds share timing."""
    k = b.get("kind")
    if k == "search":
        txt = b.get("text", "")
        t0 = b.get("type_at", b["at"] + 0.75)
        b["_keys"] = key_schedule(txt, t0, min(t0 + 2.8, b["until"] - 2.6))
        b["_enter"] = round(b.get("enter_at", (b["_keys"][-1] if b["_keys"] else t0) + 0.35), 3)
        b["_results"] = round(b["_enter"] + 0.4, 3)
    elif k == "chat":
        txt = b.get("user", "")
        t0 = b.get("type_at", b["at"] + 0.5)
        limit = (b["reply_at"] - 1.0) if b.get("reply_at") else min(t0 + 2.6, b["until"] - 2.2)
        b["_keys"] = key_schedule(txt, t0, limit, seed=11)
        b["_send"] = round((b["_keys"][-1] if b["_keys"] else t0) + 0.3, 3)
        b["_reply"] = round(b.get("reply_at", b["_send"] + 0.9), 3)
    elif k == "prompt":
        txt = b.get("text", "")
        t0 = b["at"] + 0.35
        limit = (b["answer_at"] - 0.5) if b.get("answer_at") else b["until"] - 1.5
        b["_keys"] = key_schedule(txt, t0, limit, seed=3)


def sfx_events(beats, end):
    ev, breaks = [], []

    def add(s, t, g, var=0, pan=0.0):
        if 0 <= t < end:
            ev.append({"sfx": s, "t": round(max(0, t), 3), "gain": g, "var": var, "pan": pan})
    wipe = 0
    for bi, b in enumerate(beats):
        if b["type"] == "words":
            for i, L in enumerate(b["lines"]):
                t = L.get("at", b["at"] + i * 0.3)
                big = L.get("style", "big") in ("big", "box")
                if big and b.get("anim") in ("slam", "drop"):
                    add("impact", t, -15)
                else:
                    add("whoosh2" if big else "pop2", t - 0.03, -17 if big else -22)
                if L.get("strike_at") is not None:
                    add("glitch", L["strike_at"], -16)
            continue
        k, at = b.get("kind"), b["at"]
        if k == "title":
            add("whoosh_deep", at - 0.15, -14); add("impact", at + 0.1, -13)
            if at > 3:
                add("riser", at - 3.0, -24)
            breaks.append((at, b["until"] + 0.3))
        else:
            add("whoosh" if wipe % 2 == 0 else "whoosh2", at - 0.06, -16); wipe += 1
        for j, t in enumerate(b.get("_keys", [])):  # one real keystroke per character
            ch = (b.get("text") or b.get("user") or "")[j:j + 1]
            add("key_space" if ch == " " else "key", t, -12 - 4 * _jit(j, bi), var=j * 7 + bi, pan=0.25 * (_jit(j, bi + 3) - 0.5))
        if k == "search":
            add("click", at + 0.55, -14)                       # cursor clicks into the box
            add("key_enter", b["_enter"], -10); add("whoosh2", b["_results"] - 0.05, -18)
            if b.get("highlight"):
                add("ding", b["highlight"].get("at", b["_results"] + 1.0), -17)
        if k == "chat":
            add("click", b["_send"] - 0.02, -13); add("swoosh_up", b["_send"], -15)
            add("notify", b["_reply"], -16)
            for st in b.get("steps", []):
                add("tick", st["at"], -14)
            if b.get("steps"):
                add("success", b["steps"][-1]["at"] + 0.4, -17)
        if k in ("list", "bars", "converge"):
            for j, it in enumerate(b.get("items", [])):
                add("pop" if j % 2 == 0 else "pop2", it.get("at", at + 0.4 + j * 0.5), -15)
        if k == "pick":
            for j, it in enumerate(b.get("items", [])):
                add("click", it.get("at", at + 0.5 + j * 0.6), -13); add("pop2", it.get("at", at + 0.5 + j * 0.6) + 0.05, -20)
        if k in ("counter", "donut"):
            c0, cd = b.get("count_at", at + 0.3), b.get("count_dur", 1.1)
            for j in range(int(cd / 0.07)):  # ticks while the number counts up
                add("tick", c0 + j * 0.07, -24 + 6 * j / max(1, cd / 0.07))
            add("ding", c0 + cd, -16)
        if k == "compare":
            add("pop", b.get("op_at", at + 0.8), -17)
            if b.get("strike_at"):
                add("glitch", b["strike_at"], -15); add("impact", b["strike_at"] + 0.03, -16)
            if b.get("verdict"):
                add("pop2", b.get("verdict_at", b.get("strike_at") or b["until"] - 0.8), -16)
        if k == "source":
            add("pop", at + 1.0, -14); add("success", at + 1.15, -19)
        if k == "apps":
            d = b.get("delete_at", b["until"] - 1.4)
            for j in range(len(b.get("items", []))):
                add("pop2", d + j * 0.16, -13)
        if k == "converge":
            add("success", b.get("target_at", at + 1.3), -17)
        if k == "comment":
            for j, it in enumerate(b.get("items", [{}])):
                add("notify", it.get("at", at + 0.3 + j * 0.6), -16)
        if k == "prompt" and b.get("answer"):
            add("key_enter", b["_keys"][-1] + 0.2 if b.get("_keys") else at + 1.2, -11)
            add("notify", b.get("answer_at", at + 1.5), -16)
        if k == "broll":
            add("whoosh2", at - 0.06, -18)
    return sorted(ev, key=lambda e: e["t"]), breaks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True); ap.add_argument("--profile", required=True)
    ap.add_argument("--beats", required=True)
    a = ap.parse_args()
    prof = load_json(a.profile); plan = load_json(a.beats)
    # the owner's yes/no answers: whole families can be off, single moments can be skipped
    on = {"broll": True, "animations": True, "graphics": True}
    on.update({k: bool(v) for k, v in (prof.get("edit", {}).get("include") or {}).items()})
    on.update({k: bool(v) for k, v in (plan.get("include") or {}).items()})
    fam = lambda b: "animations" if b["type"] == "words" else ("broll" if b.get("kind") == "broll" else "graphics")
    plan["beats"] = [b for b in plan["beats"] if not b.get("skip") and on[fam(b)]
                     and not (b.get("kind") == "broll" and not b.get("src"))]
    for b in plan["beats"]:
        prepare_typing(b)
    edl = load_json(os.path.join(a.work, "edl.json")); words = load_json(os.path.join(a.work, "words_cut.json"), [])
    W, H = FORMATS[edl["format"]]; u = min(W, H) / 1080; END = edl["duration"]; portrait = H > W
    comp = os.path.join(a.work, "comp"); os.makedirs(comp, exist_ok=True)

    c = prof.get("colors", {})
    primary = c.get("primary", "#111111")
    on_primary = c.get("on_primary") or ("#ffffff" if is_dark(primary) else "#111111")
    page_bg = c.get("page_bg") or mix(primary, "#ffffff", 0.955)
    ink = c.get("ink") or (primary if is_dark(primary) else "#111111")
    wall_ink = c.get("wall_ink") or ink
    hi = c.get("highlight") or c.get("accent") or mix(primary, "#ffffff", 0.55)
    shades = [primary, mix(primary, "#ffffff", 0.15), mix(primary, "#ffffff", 0.3), mix(primary, "#ffffff", 0.45)]
    f = prof.get("fonts", {})
    display, serif, mono = f.get("display", "Inter"), f.get("serif", "Cormorant Garamond"), f.get("mono", "JetBrains Mono")
    # Roboto + Poppins power the realistic search / chat mockups (they imitate real apps, not the brand)
    faces = install_fonts_and_gsap(comp, [x for x in {display, serif, mono, "Roboto", "Poppins"} if x])
    faces += custom_fonts(comp, f.get("files"))
    if (f.get("files") or {}).get("display"): display = "BrandDisplay"
    if (f.get("files") or {}).get("serif"): serif = "BrandSerif"

    # layout from where the face actually is in the output frame
    fo = edl.get("face_out") or {"top": 0.25, "chin": 0.45, "cx": 0.5}
    wall_top, wall_bottom = (0.06 if portrait else 0.07) * H, (fo["top"] - 0.03) * H
    if wall_bottom - wall_top < 0.12 * H:  # head near the top: words go below the chin instead
        wall_top, wall_bottom = (fo["chin"] + 0.05) * H, 0.66 * H
    caps_y = min(max((fo["chin"] + 0.12) * H, 0.55 * H), 0.74 * H) if portrait else 0.8 * H
    caps_page_y = 0.8 * H if portrait else 0.86 * H
    if wall_top > 0.4 * H:
        caps_y = 0.76 * H

    cap = prof.get("captions", {})
    data = {"id": "reel", "W": W, "H": H, "u": u, "fps": edl["fps"], "duration": END,
            "wall": {"top": wall_top, "bottom": wall_bottom}, "capsY": caps_y, "capsPageY": caps_page_y,
            "captions": {"style": cap.get("style", "bold-box"), "case": cap.get("case", "upper"),
                         "max_words": cap.get("max_words", 3), "max_chars": cap.get("max_chars", 17 if portrait else 28)},
            "shades": shades, "beats": plan["beats"], "words": words}
    data_js = "window.REEL=" + json.dumps(data, ensure_ascii=False).replace("</", r"<\/") + ";"
    runtime_js = open(os.path.join(RUNTIME, "reel.js"), encoding="utf-8").read()
    for css in ("reel.css", "reel-ui.css"):
        shutil.copy(os.path.join(RUNTIME, css), os.path.join(comp, css))
    shutil.copy(os.path.join(a.work, "cut.mp4"), os.path.join(comp, "base.mp4"))
    for b in plan["beats"]:  # copy b-roll / image media next to the composition
        if b.get("kind") in ("image", "broll") and b.get("src"):
            srcp = b["src"] if os.path.isabs(b["src"]) else os.path.join(a.work, b["src"])
            if os.path.exists(srcp):
                os.makedirs(os.path.join(comp, "media"), exist_ok=True)
                dst = "media/" + os.path.basename(srcp); shutil.copy(srcp, os.path.join(comp, dst)); b["src"] = dst

    clips = []
    for i, b in enumerate(plan["beats"]):
        until = min(b["until"], END)
        track = 3 if b["type"] == "page" else 2
        cls = "fx clip " + ("page" if b["type"] == "page" else "words")
        if b.get("kind") == "broll":
            # real video layer the renderer decodes: its own id, inside an UNTIMED wrapper (a timed parent
            # would offset its frames); the wrapper carries the wipe + push-in, the beat div the label
            clips.append(f'<div id="bw{i}" class="bwrap"><video id="bv{i}" class="bv" src="{b["src"]}" muted playsinline '
                         f'data-has-audio="false" data-start="{b["at"]:.4f}" data-duration="{until - b["at"]:.4f}" '
                         f'data-track-index="{10 + i}"></video></div>')
        clips.append(f'<div id="b{i}" class="{cls}" data-start="{b["at"]:.4f}" data-duration="{until - b["at"]:.4f}" data-track-index="{track}"></div>')
    root = f""":root{{--W:{W}px;--H:{H}px;--u:{u}px;--primary:{primary};--on-primary:{on_primary};--page-bg:{page_bg};--ink:{ink};--wall-ink:{wall_ink};--hi:{hi};
--primary-90:{rgba(primary, .9)};--primary-35:{rgba(primary, .35)};--primary-20:{rgba(primary, .2)};
--ink-55:{rgba(ink, .55)};--ink-25:{rgba(ink, .25)};--ink-12:{rgba(ink, .12)};--ink-08:{rgba(ink, .08)};--ink-06:{rgba(ink, .06)};
--font-display:"{display}";--font-serif:"{serif}";--font-mono:"{mono}";--page-top:{(0.11 if portrait else 0.08) * H:.0f}px;--page-bottom:{(0.22 if portrait else 0.18) * H:.0f}px}}"""
    html = f"""<!doctype html>
<html lang="{prof.get('language', 'en')}"><head><meta charset="utf-8">
<style>{''.join(faces)}</style><style>{root}</style><link rel="stylesheet" href="reel.css"><link rel="stylesheet" href="reel-ui.css">
<style>html,body{{font-family:"{display}","Inter",sans-serif}}</style></head>
<body><div id="stage" data-composition-id="reel" data-start="0" data-duration="{END:.4f}" data-fps="{edl['fps']}" data-width="{W}" data-height="{H}">
<div id="vwrap"><video id="base" src="base.mp4" playsinline muted data-has-audio="false" data-start="0" data-duration="{END:.4f}" data-track-index="0"></video></div>
{chr(10).join(clips)}
<div id="caps" class="clip" data-start="0" data-duration="{END:.4f}" data-track-index="5"></div>
<script>{data_js}</script><script src="gsap.min.js"></script><script>{runtime_js}</script>
</div></body></html>"""
    open(os.path.join(comp, "index.html"), "w", encoding="utf-8").write(html)
    ev, breaks = sfx_events(plan["beats"], END)
    save_json(ev, os.path.join(a.work, "sfx_events.json"))
    open(os.path.join(a.work, "music_breaks.txt"), "w").write(",".join(f"{x:.2f}-{y:.2f}" for x, y in breaks))
    log(f"composition -> {comp}  ({len(plan['beats'])} effects, {len(ev)} sound events, {W}x{H})")


if __name__ == "__main__":
    main()
