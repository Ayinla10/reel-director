# Profile schema

`~/.reel-director/profiles/<name>.json` (assets used by the profile - references, LUTs, pairs, fonts,
logo, music - go in `~/.reel-director/profiles/<name>/`). Every field is optional; defaults in brackets.

```json
{
  "name": "Prof Tidjani",
  "handle": "@proftidjani",
  "language": "auto",
  "colors": {
    "primary": "#061C5F",          // boxes, pages, highlights, active caption word
    "on_primary": "#FFFFFF",       // text on primary [auto: white on dark, near-black on light]
    "page_bg": null,               // full-screen page background [very light tint of primary]
    "ink": null,                   // text on pages [primary if dark, else #111]
    "wall_ink": null,              // kinetic words over the footage [ink]; use #FFFFFF on dark looks
    "highlight": null              // caption highlight for the "color" style [light tint of primary]
  },
  "fonts": {
    "display": "Inter",            // any Google Font family name
    "serif": "Cormorant Garamond", // italic accents
    "mono": "JetBrains Mono",      // small labels
    "files": {"display": null, "serif": null}   // or the creator's own .ttf/.otf/.woff2
  },
  "logo": null,
  "look": {
    "method": "preset",            // preset | reference | pair | cube
    "preset": "bright-clean",      // name from assets/looks.json
    "refs": [],                    // reference stills/videos (method=reference)
    "before": null, "after": null, // still pair (method=pair)
    "cube": null,                  // .cube path (method=cube)
    "intensity": 1.0,
    "skin_protect": 0.85,
    "finish": {"smooth": 0.45, "sharpen": 0.5, "grain": 0, "vignette": 0}
  },
  "captions": {"style": "bold-box", "case": "upper", "max_words": 3},   // bold-box | color | clean | none
  "edit": {"density": "moderate", "effects": ["pages", "words", "ui"], "zoom": "alternate", "cut": "tight",
           "include": {"broll": true, "animations": true, "graphics": true}},   // the owner's yes/no extras
  "broll": {"folder": null,          // creator's own clips (matched by file name to the moment)
            "pexels_key": null,      // free key from pexels.com/api   (or env PEXELS_API_KEY)
            "pixabay_key": null,     // free key from pixabay.com/api/docs (or env PIXABAY_API_KEY)
            "sources": "folder,pexels,pixabay,commons,openverse"},
  "sound": {"music": "generate", "mood": "hopeful", "tracks": [], "sfx": true, "lufs": -14},
  "ending": "loop",                // loop | follow | comment | link
  "cta": {"keyword": null, "link": null},
  "platforms": ["tiktok", "reels", "shorts"],
  "approval": "once"               // once | never
}
```

Notes
- Write real JSON (no comments) when saving.
- `wall_ink`: kinetic words sit on the background above the head. On bright looks the primary
  colour reads well; on moody/dark looks set it to white.
- Keep the profile in sync with what the user tells you later ("always use a loop", "less zoom").
