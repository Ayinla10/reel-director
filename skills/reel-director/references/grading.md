# Grading guide

All methods produce a 33-point 3D LUT (`grade.cube`) applied in the single cut pass, followed by the
profile's finish (skin smoothing, sharpening, optional grain/vignette).

## What the engine does (preset + reference)
1. **Phone HDR** (iPhone HLG / Dolby Vision, Android HDR10): read in "compat" mode by default -
   no purple/grey tone-mapping casts. `--hdr tonemap` is available for very bright highlights.
2. **Auto exposure** - black/white points from the footage's own percentiles, mid-tones lifted only as
   far as the look allows (bright looks never darken a face; moody looks never brighten).
3. **Auto white balance** - neutralises the camera's cast measured on the background.
4. **Brand tint** - per-channel curves pass the measured background exactly onto the target colour.
5. **Skin protection** - every LUT node is weighted by how close it is to *this person's* measured skin
   cluster (works for every skin tone). Skin gets its own exposure/hue target instead of the tint.
6. **Closed loop** - the graded frames are re-measured and targets corrected until background (and
   skin, for references) land on target. grade.json reports source / graded / target colours.

## Choosing a method
| Situation | Method |
|---|---|
| They have a reference video/link they love | `reference` with 3-4 clean stills of the person on screen |
| CapCut / VN / InShot / Lightroom mobile / VSCO preset | `pair` (same frame, before + after export) |
| Premiere / Resolve / Final Cut / Photoshop LUT | `cube` |
| No reference | `preset` - pick by brand mood |

## Reference stills - how to capture well
- Frames where the person fills a normal amount of the frame, facing camera, no full-screen graphics.
- Crop away platform UI (TikTok/IG buttons, black bars). Captions in the frame are tolerated (the
  background measurement ignores saturated graphics) but cleaner is better.
- 3-4 stills from different moments beat one.

## Pair method - instructions to give the user
"Open any of your videos in your app. Export one still frame with **no** filter/preset (before) and
the **same frame** with your usual preset (after). Send me both images." The engine fits the preset
(local colour mapping + smooth global model), so it reproduces it on all their footage; tested error
≈2/255 on unseen frames. Pair and cube looks are applied exactly as the creator made them; add
`--normalize` only if their footage varies a lot in exposure.

## When the result isn't right
- Face too dark/bright → it's exposure: for presets adjust `min_mid`/`max_mid` via a custom look, or
  for references use cleaner reference stills.
- Skin shifts colour → raise `--skin-protect` (0.85 → 0.95) or lower `--intensity`.
- Tint too strong → `--intensity 0.7`.
- Custom brand look: copy an entry in `assets/looks.json` into the profile folder as
  `looks.json`-style dict and change `bg_rgb` (wall colour), `contrast`, `saturation`, `shadow_tint`.
