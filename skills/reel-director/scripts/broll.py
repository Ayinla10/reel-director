"""Find, download and conform B-roll for every `broll` beat in beats.json.

  python broll.py --work W --beats W/beats.json --profile P.json [--folder D:/my_clips]

Each broll beat names what it should show:  {"type":"page","kind":"broll","at":12.0,"until":15.2,
  "query":"people using phones at a market", "caption":"optional small label"}
Sources, in order (first match wins, no clip is used twice):
  1. the creator's own folder (profile broll.folder or --folder): files whose names match the query
  2. Pexels video   (free key: profile broll.pexels_key or env PEXELS_API_KEY)
  3. Pixabay video  (free key: profile broll.pixabay_key or env PIXABAY_API_KEY)
  4. Wikimedia Commons public-domain/CC0 video (no key)
  5. (only with --allow-photos / profile broll.allow_photos) Openverse CC0 photos with a Ken Burns move
B-roll is VIDEO by default - photos look like slideshows. Footage made elsewhere (e.g. AI clips from
Google Flow) is attached to a moment with  --assign 9=D:/clips/agent.mp4,15=...
Clips are cut to the beat length, framed to the video's format, and blended 50% with the creator's
grade so they sit in the same look. Writes W/broll/b<N>.mp4, credits.txt, and fills each beat's
`src` + `credit`. Also writes W/review/broll_sheet.jpg (numbered thumbnails for the approval check).
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rdlib import FFMPEG, grab_frames, load_json, log, run, save_image, save_json

FORMATS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}
# archive footage of identifiable officials/events implies endorsement - never use it as generic b-roll
PUBLIC_FIGURES = re.compile(r"potus|president|minister|senator|governor|congress|parliament|prime|king|queen|pope|"
                            r"press conference|speech|summit|forum|campaign|election|ceremony|inaugurat|white house|obama|"
                            r"trump|biden|putin|official visit|leaders|apec|g20|g7|delegation|diplomat|ambassador|embassy|nato|united nations", re.I)
UA = {"User-Agent": "reel-director/1.0 (https://github.com/Ayinla10/reel-director)"}
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".webm", ".mkv")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp")


def get_json(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def download(url, dst):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r, open(dst, "wb") as f:
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
    return dst


def tokens(s):
    return {t for t in re.findall(r"[a-z0-9]+", s.lower()) if len(t) > 2}


# ---------------------------------------------------------------- sources
STOP = {"the", "and", "with", "for", "from", "into", "onto", "of", "on", "in", "at", "a", "an", "to", "using", "people",
        "person", "man", "woman", "someone", "their", "his", "her"}


def relaxed(query):
    """Exact phrase first, then simpler versions: free libraries rarely match long, specific phrases."""
    words = [w for w in re.findall(r"[A-Za-z0-9']+", query.lower())]
    core = [w for w in words if w not in STOP and len(w) > 2]
    out = [query]
    if len(core) >= 2:
        out += [" ".join(core), " ".join(core[:2]), " ".join(core[-2:])]
    out += core[::-1] if len(core) > 1 else core  # last nouns are usually the subject ("...on laptop")
    seen, res = set(), []
    for q in out:
        if q and q not in seen:
            seen.add(q); res.append(q)
    return res


def from_folder(folder, query, used, photos=False):
    if not folder or not os.path.isdir(folder):
        return None
    q = tokens(query); best, score = None, 0
    exts = VIDEO_EXT + (IMAGE_EXT if photos else ())
    for root, _, files in os.walk(folder):
        for fn in files:
            p = os.path.join(root, fn)
            if not fn.lower().endswith(exts) or p in used:
                continue
            s = len(q & tokens(os.path.splitext(fn)[0]))
            if s > score:
                best, score = p, s
    if best:
        return {"path": best, "kind": "video" if best.lower().endswith(VIDEO_EXT) else "image",
                "id": best, "credit": "creator's own footage"}
    return None


def from_pexels(key, query, portrait, used, tmp, dur=4):
    if not key:
        return None
    d = get_json("https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
        {"query": query, "per_page": 15, "orientation": "portrait" if portrait else "landscape", "size": "medium"}),
        {"Authorization": key})
    vids = d.get("videos", [])
    vids.sort(key=lambda v: 0 if (v.get("duration") or 0) >= dur else 1)  # keep relevance order, but long-enough first
    for v in vids:
        if f"pexels:{v['id']}" in used:
            continue
        files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("height")]
        files.sort(key=lambda f: abs(min(f["width"], f["height"]) - 1080))
        if files:
            dst = download(files[0]["link"], os.path.join(tmp, f"pexels_{v['id']}.mp4"))
            return {"path": dst, "kind": "video", "id": f"pexels:{v['id']}",
                    "credit": f"Video by {v.get('user', {}).get('name', 'Pexels creator')} on Pexels ({v.get('url', '')})"}
    return None


def from_pixabay(key, query, portrait, used, tmp):
    if not key:
        return None
    d = get_json("https://pixabay.com/api/videos/?" + urllib.parse.urlencode({"key": key, "q": query, "per_page": 10}))
    for v in d.get("hits", []):
        if f"pixabay:{v['id']}" in used:
            continue
        vids = v.get("videos", {})
        f = vids.get("large") or vids.get("medium")
        if f and f.get("url"):
            dst = download(f["url"], os.path.join(tmp, f"pixabay_{v['id']}.mp4"))
            return {"path": dst, "kind": "video", "id": f"pixabay:{v['id']}",
                    "credit": f"Video by {v.get('user', 'Pixabay creator')} on Pixabay ({v.get('pageURL', '')})"}
    return None


def from_commons(query, used, tmp):
    """Public-domain/CC0 video from Wikimedia Commons. Downloads Wikimedia's own ~720p transcode
    (a few MB) instead of the full archive master."""
    d = get_json("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 15,
        "gsrsearch": f"filetype:video {query}", "prop": "videoinfo",
        "viprop": "url|size|extmetadata|derivatives"}))
    for p in (d.get("query", {}).get("pages", {}) or {}).values():
        vi = (p.get("videoinfo") or [{}])[0]
        lic = (vi.get("extmetadata", {}).get("LicenseShortName", {}) or {}).get("value", "")
        if f"commons:{p['title']}" in used or not re.search(r"public domain|cc0|pd", lic, re.I) or PUBLIC_FIGURES.search(p["title"]):
            continue
        if (vi.get("duration") or 99) < 3:
            continue
        ders = [x for x in vi.get("derivatives", []) if x.get("height") and "video" in (x.get("type") or "")]
        ders.sort(key=lambda x: abs(x["height"] - 720))
        url = ders[0]["src"] if ders else (vi.get("url") if (vi.get("size") or 1e9) < 60e6 else None)
        if not url:
            continue
        ext = ".webm" if "webm" in url else os.path.splitext(urllib.parse.urlparse(url).path)[1] or ".webm"
        dst = download(url, os.path.join(tmp, f"commons_{abs(hash(p['title']))}{ext}"))
        return {"path": dst, "kind": "video", "id": f"commons:{p['title']}",
                "credit": f"{p['title'].replace('File:', '')} - Wikimedia Commons ({lic})"}
    return None


def from_openverse(query, portrait, used, tmp):
    res = []
    for aspect in (["tall", None] if portrait else [None]):  # prefer tall, accept any (we crop)
        params = {"q": query, "license": "cc0,pdm", "page_size": 20}
        if aspect:
            params["aspect_ratio"] = aspect
        d = get_json("https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(params))
        res = [r for r in d.get("results", []) if f"openverse:{r['id']}" not in used
               and min(r.get("width") or 0, r.get("height") or 0) >= 700 and not PUBLIC_FIGURES.search(r.get("title") or "")]
        if res:
            break
    for r in res[:5]:  # keep Openverse's relevance order - the best match comes first
        try:
            ext = os.path.splitext(urllib.parse.urlparse(r["url"]).path)[1] or ".jpg"
            dst = download(r["url"], os.path.join(tmp, f"openverse_{r['id']}{ext}"))
            return {"path": dst, "kind": "image", "id": f"openverse:{r['id']}",
                    "credit": f"\"{r.get('title') or 'Photo'}\" by {r.get('creator') or 'unknown'} ({r['license'].upper()}) via Openverse"}
        except Exception:
            continue
    return None


# ---------------------------------------------------------------- conform
def conform(src, dst, dur, W, H, fps, cube, work):
    """Cut to length, cover-crop to the format, blend 50% with the creator's grade."""
    grade = (f",split[a][b];[b]lut3d=file=grade.cube:interp=tetrahedral[g];[a][g]blend=all_mode=normal:all_opacity=0.5"
             if cube else "")
    if src["kind"] == "video":
        chain = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps},"
                 f"setsar=1,format=yuv420p{grade},format=yuv420p[v]")
        args = [FFMPEG, "-v", "error", "-y", "-stream_loop", "-1", "-i", src["path"], "-t", f"{dur:.3f}"]
    else:  # still photo: slow Ken Burns push-in
        n = int(dur * fps) + 1
        chain = (f"[0:v]scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
                 f"zoompan=z='1+0.08*on/{n}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={n}:s={W}x{H}:fps={fps},"
                 f"setsar=1,format=yuv420p{grade},format=yuv420p[v]")
        args = [FFMPEG, "-v", "error", "-y", "-loop", "1", "-i", src["path"], "-t", f"{dur:.3f}"]
    graph = os.path.join(work, "broll_graph.txt")
    open(graph, "w").write(chain)
    run(args + ["-/filter_complex", "broll_graph.txt", "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "18",
                "-preset", "medium", "-pix_fmt", "yuv420p", os.path.abspath(dst)], cwd=work)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True); ap.add_argument("--beats", required=True)
    ap.add_argument("--profile"); ap.add_argument("--folder")
    ap.add_argument("--sources", default="folder,pexels,pixabay,commons")
    ap.add_argument("--allow-photos", action="store_true", help="also use still photos (Ken Burns) as a last resort")
    ap.add_argument("--assign", default="", help="attach your own/AI clips: 9=D:/x.mp4,15=D:/y.mp4")
    ap.add_argument("--refetch", action="store_true", help="replace clips already chosen")
    ap.add_argument("--redo", default="", help="moment numbers to re-fetch, e.g. 9,16 (edit their query first); "
                                               "the rejected clip is never picked again")
    a = ap.parse_args()
    prof = load_json(a.profile, {}) if a.profile else {}
    bc = prof.get("broll", {})
    folder = a.folder or bc.get("folder")
    pexels = bc.get("pexels_key") or os.environ.get("PEXELS_API_KEY")
    pixabay = bc.get("pixabay_key") or os.environ.get("PIXABAY_API_KEY")
    plan = load_json(a.beats); edl = load_json(os.path.join(a.work, "edl.json"))
    W, H = FORMATS[edl["format"]]; fps = edl["fps"]; portrait = H > W
    cube = os.path.exists(os.path.join(a.work, "grade.cube"))
    out = os.path.join(a.work, "broll"); tmp = os.path.join(out, "_src")
    os.makedirs(tmp, exist_ok=True)
    sources = a.sources.split(",")
    photos = a.allow_photos or bool(bc.get("allow_photos"))
    if photos and "openverse" not in sources:
        sources.append("openverse")
    assigned = {int(k): v for k, v in (x.split("=", 1) for x in a.assign.split(",") if "=" in x)}
    redo = {int(x) for x in a.redo.split(",") if x.strip()}
    for i, b in enumerate(plan["beats"]):
        if i + 1 in redo and b.get("source_id"):
            b.setdefault("rejected", []).append(b.pop("source_id")); b.pop("src", None); b.pop("credit", None)
    used = {b.get("source_id") for b in plan["beats"] if b.get("source_id")}
    used |= {r for b in plan["beats"] for r in b.get("rejected", [])}
    credits, thumbs = [], []
    for i, b in enumerate(plan["beats"]):
        if b.get("skip_reason") == "no b-roll found":  # give earlier misses another chance
            b.pop("skip", None); b.pop("skip_reason", None)
        if b.get("kind") != "broll" or b.get("skip"):
            continue
        n = i + 1
        dst = os.path.join(out, f"b{n:02d}.mp4")
        if b.get("src") and os.path.exists(os.path.join(a.work, b["src"])) and not a.refetch:
            thumbs.append((n, os.path.join(a.work, b["src"]))); credits.append(f"#{n}: {b.get('credit', '')}")
            continue
        q = b.get("query") or b.get("caption") or ""
        found = None
        if n in assigned and os.path.exists(assigned[n]):
            f = assigned[n]
            found = {"path": f, "kind": "video" if f.lower().endswith(VIDEO_EXT) else "image", "id": f"assigned:{f}",
                     "credit": b.get("credit_note") or "supplied clip"}
        dur0 = max(0.5, b["until"] - b["at"])
        for s, qq in [(s, qq) for qq in relaxed(q) for s in sources]:
            if found:
                break
            try:
                found = {"folder": lambda: from_folder(folder, q, used, photos),
                         "pexels": lambda: from_pexels(pexels, qq, portrait, used, tmp, dur0),
                         "pixabay": lambda: from_pixabay(pixabay, qq, portrait, used, tmp),
                         "commons": lambda: from_commons(qq, used, tmp),
                         "openverse": lambda: from_openverse(qq, portrait, used, tmp)}[s]()
            except Exception as e:  # one flaky source never stops the run
                log(f"  #{n} {s} '{qq}': {type(e).__name__}: {str(e)[:120]}")
        if not found:
            log(f"  #{n} no B-roll found for '{q}' - beat will be skipped (try a simpler query)")
            b["skip"] = True; b["skip_reason"] = "no b-roll found"
            continue
        dur = max(0.5, b["until"] - b["at"]) + 0.3
        conform(found, dst, dur, W, H, fps, cube, a.work)
        used.add(found["id"])
        b.update(src=os.path.relpath(dst, a.work).replace("\\", "/"), credit=found["credit"], source_id=found["id"],
                 media=found["kind"])
        credits.append(f"#{n}: {found['credit']}")
        thumbs.append((n, dst))
        log(f"  #{n} {b['at']:.1f}s '{q}' <- {found['id']}")
    save_json(plan, a.beats)
    open(os.path.join(out, "credits.txt"), "w", encoding="utf-8").write("\n".join(credits) + "\n")
    if thumbs:  # numbered contact sheet for the approval check
        from PIL import Image, ImageDraw, ImageFont
        tiles = [(n, fr[0]) for n, p in thumbs for fr in [grab_frames(p, [0.6], 240)] if fr]
        if tiles:
            h = min(t.shape[0] for _, t in tiles); cols = min(6, len(tiles)); rows = (len(tiles) + cols - 1) // cols
            grid = np.ones((rows * h, cols * 240, 3), np.float32)
            for k, (n, t) in enumerate(tiles):
                r, c = divmod(k, cols); grid[r * h:(r + 1) * h, c * 240:(c + 1) * 240] = t[:h]
            img = Image.fromarray((grid * 255).astype(np.uint8)); d = ImageDraw.Draw(img)
            try:
                font = ImageFont.load_default(size=30)
            except TypeError:
                font = ImageFont.load_default()
            for k, (n, _) in enumerate(tiles):
                r, c = divmod(k, cols)
                d.rectangle([c * 240, r * h, c * 240 + 70, r * h + 44], fill=(6, 28, 95))
                d.text((c * 240 + 10, r * h + 6), f"#{n}", fill=(255, 255, 255), font=font)
            os.makedirs(os.path.join(a.work, "review"), exist_ok=True)
            img.save(os.path.join(a.work, "review", "broll_sheet.jpg"), quality=90)
    log(f"B-roll ready for {len(thumbs)} moment(s). Credits: {os.path.join(out, 'credits.txt')}")


if __name__ == "__main__":
    main()
