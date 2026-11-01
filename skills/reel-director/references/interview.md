# The brand interview

Goal: learn enough about this creator to make their video look like *their* brand, then save it as a
profile so next time is one command. Ask with AskUserQuestion, up to 4 questions per round,
recommended option first. Always allow "Other" (free text) - many answers are file paths or links.
Keep the tone light: they're a creator, not filling a form.

## Round 1 - Brand kit
1. **Name & handle** - how they appear on screen (e.g. "Prof Tidjani", "@proftidjani"). Free text.
2. **Brand colours** - primary (main colour, used for boxes, pages, highlights) and secondary
   (usually white or a light tone). Options: "I'll type hex codes", "Pick from my logo" (ask for the
   logo file and sample its dominant colours with PIL), "Suggest a palette" (offer 3 palettes as
   options with hex codes in the descriptions). Advise using **one** strong colour + white/neutral;
   a second accent only if they insist.
3. **Fonts** - options: "Inter + elegant serif (default)", "Bold condensed (Anton/Oswald)",
   "Rounded friendly (Poppins/Nunito)", "Use my font files" (ask for .ttf/.otf/.woff2 paths).
   Any Google Font name works (installed from fontsource).
4. **Logo** (optional) - path to a PNG/SVG, used on title pages/end cards.

## Round 2 - Look (colour grade)
Explain briefly that the skill can copy a look exactly. Options:
1. **"Match my reference video/link"** - their own best-looking video or a creator they admire.
   - A link (TikTok/IG/YouTube): open it with the browser tools, let it play, screenshot 3-4
     moments where the person is on screen (crop to the video area, no UI), save as
     `~/.reel-director/profiles/<name>/refs/ref1.png...`. Ask them to confirm the frames look right.
   - A file: use it directly (`--ref video.mp4` samples it).
2. **"My editing-app preset"**:
   - Premiere Pro / DaVinci Resolve / Final Cut / Photoshop / Lightroom desktop → export a **.cube
     LUT** (Premiere: Lumetri panel ⋯ → Export .cube; Resolve: right-click the node → Generate LUT →
     33 point cube; Lightroom/Photoshop: Export → Color Lookup Tables). Store the path.
   - CapCut, VN, InShot, Lightroom mobile, Snapseed, VSCO (no LUT export) → the **before/after
     pair**: pick any frame from one of their videos, export it once with no filter (before) and
     once with their preset (after), same size. The skill learns the preset from those two images.
3. **"Pick a look"** - show the presets from `assets/looks.json` with their `about` lines
   (bright-clean, bright-blue, natural, warm-film, golden-hour, soft-pastel, moody, mono).
4. **Skin & finish** - skin smoothing (none / subtle (default) / soft), grain (none default),
   vignette (none default). Remind: skin protection keeps every skin tone natural under any look.

## Round 3 - Edit style
1. **Captions** - "Bold boxed (word lights up in your colour)", "Coloured word (clean white,
   spoken word in colour)", "Simple subtitles", "No captions". Also case: UPPERCASE or Sentence.
2. **Graphics density** - moderate (default: a page/title every ~10 s), minimal (only the key
   numbers), rich (every point gets a visual, but face still on screen ≥50%).
3. **Effect families** they like (multi-select): stat pages, kinetic words, UI mockups (prompt bar,
   apps, file drop, timeline, eyedropper), b-roll/images, comment bubbles.
4. **Punch-in zooms** on cuts (yes default / no) and **pacing** of cuts (tight default).

## Round 4 - Goal & platform defaults
1. **Main platforms** (multi-select): TikTok, Instagram Reels, YouTube Shorts, YouTube long-form,
   LinkedIn, WhatsApp Status. (Formats are still confirmed per video.)
2. **Default ending** - "Seamless loop (the end flows into the start)", "Follow/subscribe card",
   "Comment-keyword CTA (e.g. 'Comment AI')", "Website/link card".
3. **Music** - "I'll give my own tracks" (ask for a folder or file) / "Compose royalty-free
   music for me" + mood (hopeful, upbeat, calm, energetic, serious, luxury). Sound effects on/off.
4. **Approval** - one check before the long render (default) or fully automatic.

Save the profile (`references/profile.md`), then show a one-paragraph summary of it.

## Every video (profile already exists)
Ask in ONE round:
1. **Format(s)** - 9:16 / 16:9 / 1:1 / 4:5 / several (multi-select; recommend 9:16 for phones).
2. **Cut** - tight (pauses, retakes, fillers out) / light (only obvious mistakes) / none.
3. **Ending** - profile default pre-selected; offer the others.
4. **Anything special?** - free text: topic/goal, numbers or sources to visualise, b-roll images
   or clips to include, a music track for this one, a CTA keyword.
If the user says "just do it" / "same as last time", skip the round and use profile defaults.
