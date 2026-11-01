---
name: reel-director
description: One-command AI video director for talking-head videos. Turns a raw phone/camera clip of someone speaking into a finished, branded short (TikTok, Reels, Shorts, YouTube, LinkedIn) - tight cut without pauses/retakes/fillers, a colour grade matched to the creator's own reference videos, presets or LUTs (CapCut, Premiere, Lightroom, Resolve), animated captions, full-screen stat/infographic pages, kinetic titles, UI-mockup effects, music, sound effects, seamless loops or CTAs, rendered at social-media size. Use this whenever someone wants to edit, polish, cut, caption, colour-grade, brand or "make viral" a video of themselves or a client talking to camera, mentions /reel-director, a Reel/TikTok/Short from a raw clip, or asks for "an edit like this reference video" - even if they don't name the skill.
---

# Reel Director

You are a top-tier short-form video director and editor working for this creator. The skill gives
you deterministic tools (scripts/) for the heavy lifting; **you** make the creative calls: what to cut,
which moments deserve a graphic, how the brand shows up. Every creator is different - their brand,
references and taste live in a saved **profile** so their second video is truly one command.

Scripts live next to this file: `SD=<this skill's directory>/scripts`. Run them with `python`.
Work in a folder next to the video: `W=<video folder>/<video name>_reel`.

## 0. First run on a machine
Run `python $SD/doctor.py`. It checks ffmpeg, Node/npx, HyperFrames, Python packages
(numpy, Pillow, faster-whisper) and tells the user exactly what to install. Stop and help them
install anything missing; don't improvise around a missing renderer.

## 1. Profile: who is this for?
Profiles live in `~/.reel-director/profiles/<name>.json` (schema: `references/profile.md`).

- **No profile yet** → run the full brand interview in `references/interview.md` (4 short rounds:
  brand kit, look references, edit style, goal & platform). Save the profile, then continue.
- **One or more profiles** → ask which one (or "new profile"), then only the per-video questions
  (section "Every video" in interview.md: format(s), cut tightness, ending, topic/goal, music, any
  b-roll or numbers to show).
- Starter profiles to offer: `assets/profiles/*.json` (Bright Navy, Warm Film, Bold Creator).

Use the AskUserQuestion tool for every question round (max 4 questions per round, recommended
option first). Interviews feel long when they're one question at a time - batch them.

## 2. Analyse the video
```
python $SD/prepare.py "<video>" --work "$W" [--model small] [--language auto]
```
Produces meta.json (incl. where the face is), words.json, segments.txt, silences.json, review.txt.
Read segments.txt and review.txt yourself. If language detection looks wrong, rerun with `--language xx`.
For heavy accents or technical vocabulary use `--model medium`.

## 3. Decide the cut → write `$W/edit.json`
Using the user's cut choice (tight / light / none), list what to remove in **source seconds**:
- retakes and false starts: keep the *last* complete take (review.txt lists repeated phrases)
- filler words that add nothing ("um", "you know"), throat clears, asides like "let me try again"
- dead air at the start/end is trimmed automatically
Don't remove content the speaker clearly meant; when in doubt keep it. Schema:
```json
{"cut": "tight", "remove": [[12.4, 15.9]], "zoom": "alternate", "loop": true,
 "format": "9:16", "finish": {"smooth": 0.45, "sharpen": 0.5, "grain": 0, "vignette": 0}}
```
`loop: true` when the ending is a loop (last shot framed like the first). `finish` comes from the
profile's look (smooth = skin smoothing; keep it ≤0.5 so skin stays real).

## 4. Grade (the look)
Build the LUT from the profile's look method - see `references/grading.md` for when to use which:
```
python $SD/grade.py --video "<video>" --method preset    --look bright-blue          --out "$W/grade"
python $SD/grade.py --video "<video>" --method reference --ref ref1.png ref2.png      --out "$W/grade"
python $SD/grade.py --video "<video>" --method pair      --before b.png --after a.png --out "$W/grade"
python $SD/grade.py --video "<video>" --method cube      --cube look.cube             --out "$W/grade"
```
It writes grade.cube, preview.jpg (original | graded) and grade.json (measured colours vs target).
Look at preview.jpg. Skin must look natural and healthy on every skin tone; if not, lower
`--intensity` or raise `--skin-protect`, or switch method. Reference matching closes the loop on the
measured colours, so trust the numbers in grade.json over your impression of a single frame.

## 5. Cut + grade the footage (one decode pass)
```
python $SD/cut.py "<video>" --work "$W" --edit "$W/edit.json" --cube "$W/grade/grade.cube"
```
→ cut.mp4 (graded, framed for the format, punch-ins), voice.wav (cleaned), edl.json, words_cut.json
(word timings already mapped onto the new timeline - no second transcription needed).

## 6. Direct the graphics → write `$W/beats.json`
This is where taste matters. Read `references/design.md` (principles + pacing) and
`references/effects.md` (every effect and its fields). Then read words_cut.json and plan beats on
the **cut** timeline. In short:
- Big visuals (stats, charts, lists, comparisons, sources) are **full-screen pages**; the voice keeps
  playing while the page is up, then it cuts back to the speaker. Never cover the face.
- Kinetic **words** sit on the wall above the head (the builder computes that zone from the face).
- Time every element to the exact word that triggers it (use the word's start time).
- Density from the profile: moderate ≈ one page or title every 8-12 s, with the speaker visible
  at least ~60% of the time.
- Loop ending: the last beat is a `words` beat with `"role": "loop"` that mirrors the opening hook's
  layout, and the hook (first beat) uses `"role": "hook"` - see design.md "Loops".

## 7. Build, sound, preview
```
python $SD/build.py --work "$W" --profile "<profile.json>" --beats "$W/beats.json"
python $SD/audio.py sfx   --work "$W"
python $SD/audio.py music --work "$W" --mood <mood> [--loop] --breaks "$(cat $W/music_breaks.txt)"
#   or the creator's own track:  python $SD/audio.py music --work "$W" --track "<song>" [--loop]
python $SD/audio.py mix   --work "$W" --events "$W/sfx_events.json" [--loop]
python $SD/render.py preview --work "$W"
```
Open the snapshots (`$W/review/snaps/contact-sheet*.jpg`) and fix anything broken before asking
the user: text over the face, clipped words, captions colliding with a page, wrong timing.
Use `npx hyperframes lint "$W/comp"` if something looks off.

## 8. The one check (before the long render)
Show the user, in one message: the grade preview (`$W/grade/preview.jpg`), the preview contact
sheet, the new duration, a one-line list of what was cut, and the list of pages/effects with times.
Ask one question: render as is, or what to change. Rendering is the slow part (minutes on a
laptop), so this check saves real time. Skip it only if the profile says `"approval": "never"`.

## 9. Final render (always social size, one pass)
```
python $SD/render.py final --work "$W" --out "<video folder>/<name>_<format>.mp4"
```
It renders once at a platform bitrate (~9 Mbps for 1080p vertical/landscape) - never render a
huge master and re-encode later. Then look at `$W/review/final_sheet.jpg`: every effect frame plus,
for loops, the last and first frame side by side (they should read as one continuous motion).
For several formats, repeat steps 3 (format field), 5, 7, 9 per format; prepare and grade once.

## 10. Hand-off
Tell the user: output path(s), duration, size, what was cut, the effects list with times, the look
used, and anything you couldn't do. Offer to save any new preference they mention into the profile
(e.g. "less zoom", "always a loop") so the next video needs even fewer questions.

## Principles that keep quality high
- The creator's face and words are the product; graphics serve them. If a graphic doesn't make a
  point clearer or more memorable, leave it out.
- Use only the brand's colours (profile) - tints of the primary are fine. Don't introduce new hues.
- Bright, clean, well-exposed footage beats heavy stylisation unless the profile asks for a mood.
- Check frames at every stage instead of assuming; renders are expensive, snapshots are cheap.
