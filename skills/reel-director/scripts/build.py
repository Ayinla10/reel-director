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


def sfx_events(beats, end):
    ev, breaks = [], []
    add = lambda s, t, g: ev.append({"sfx": s, "t": round(max(0, t), 3), "gain": g}) if 0 <= t < end else None
    for b in beats:
        if b["type"] == "words":
            for i, L in enumerate(b["lines"]):
                t = L.get("at", b["at"] + i * 0.3)
                big = L.get("style", "big") in ("big", "box")
                add("impact" if big and b.get("anim") in ("slam", "drop") else "pop", t, -14 if big else -18)
                if L.get("strike_at") is not None:
                    add("click", L["strike_at"], -12)
            continue
        k, at = b.get("kind"), b["at"]
        if k == "title":
            add("impact", at, -12)
            if at > 3:
                add("riser", at - 3.0, -24)
            breaks.append((at, b["until"] + 0.3))
        else:
            add("whoosh", at - 0.05, -17)
        if k in ("list", "pick", "bars", "converge"):
            for j, it in enumerate(b.get("items", [])):
                t = it.get("at", at + 0.4 + j * 0.5)
                add("click" if k == "pick" else "pop", t, -15)
        if k in ("counter", "donut"):
            add("ding", b.get("count_at", at + 0.3) + 1.0, -19)
        if k == "compare":
            if b.get("strike_at"):
                add("impact", b["strike_at"], -13)
            add("pop", b.get("op_at", at + 0.8), -17)
        if k == "source":
            add("pop", at + 1.0, -15)
        if k == "apps":
            d = b.get("delete_at", b["until"] - 1.4)
            for j in range(len(b.get("items", []))):
                add("click", d + j * 0.16, -12)
        if k == "converge":
            add("ding", b.get("target_at", at + 1.3), -18)
        if k == "comment":
            for j, it in enumerate(b.get("items", [{}])):
                add("ding", it.get("at", at + 0.3 + j * 0.6), -18)
        if k == "prompt":
            n = min(18, len(b.get("text", "")) // 3)
            for j in range(n):
                add("click", at + 0.35 + j * 0.12, -22)
            if b.get("answer"):
                add("pop", b.get("answer_at", at + 1.5), -16)
    return sorted(ev, key=lambda e: e["t"]), breaks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True); ap.add_argument("--profile", required=True)
    ap.add_argument("--beats", required=True)
    a = ap.parse_args()
    prof = load_json(a.profile); plan = load_json(a.beats)
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
    faces = install_fonts_and_gsap(comp, [x for x in {display, serif, mono} if x])
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
    data_js = "window.REEL=" + json.dumps(data, ensure_ascii=False).replace("</", "<\/") + ";"
    runtime_js = open(os.path.join(RUNTIME, "reel.js"), encoding="utf-8").read()
    shutil.copy(os.path.join(RUNTIME, "reel.css"), os.path.join(comp, "reel.css"))
    shutil.copy(os.path.join(a.work, "cut.mp4"), os.path.join(comp, "base.mp4"))
    for b in plan["beats"]:  # copy b-roll media next to the composition
        if b.get("kind") == "image" and b.get("src") and os.path.exists(b["src"]):
            dst = os.path.basename(b["src"]); shutil.copy(b["src"], os.path.join(comp, dst)); b["src"] = dst

    clips = []
    for i, b in enumerate(plan["beats"]):
        until = min(b["until"], END)
        track = 3 if b["type"] == "page" else 2
        cls = "fx clip " + ("page" if b["type"] == "page" else "words")
        clips.append(f'<div id="b{i}" class="{cls}" data-start="{b["at"]:.4f}" data-duration="{until - b["at"]:.4f}" data-track-index="{track}"></div>')
    root = f""":root{{--W:{W}px;--H:{H}px;--u:{u}px;--primary:{primary};--on-primary:{on_primary};--page-bg:{page_bg};--ink:{ink};--wall-ink:{wall_ink};--hi:{hi};
--primary-90:{rgba(primary, .9)};--primary-35:{rgba(primary, .35)};--primary-20:{rgba(primary, .2)};
--ink-55:{rgba(ink, .55)};--ink-25:{rgba(ink, .25)};--ink-12:{rgba(ink, .12)};--ink-08:{rgba(ink, .08)};--ink-06:{rgba(ink, .06)};
--font-display:"{display}";--font-serif:"{serif}";--font-mono:"{mono}";--page-top:{(0.11 if portrait else 0.08) * H:.0f}px;--page-bottom:{(0.22 if portrait else 0.18) * H:.0f}px}}"""
    html = f"""<!doctype html>
<html lang="{prof.get('language', 'en')}"><head><meta charset="utf-8">
<style>{''.join(faces)}</style><style>{root}</style><link rel="stylesheet" href="reel.css">
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
