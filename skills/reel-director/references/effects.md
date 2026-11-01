# Effects catalogue (beats.json)

`beats.json` = `{"beats": [ ... ]}`, times in seconds on the **cut** timeline (words_cut.json).
Every beat has `type`, `at`, `until`. Optional on any beat: `hide_captions` (words default true,
pages default false; title pages always hide).

## words - kinetic text on the wall above the head
```json
{"type": "words", "at": 0.0, "until": 5.6, "role": "hook", "anim": "mask",
 "lines": [
   {"text": "Almost a", "style": "serif", "at": 0.0},
   {"text": "Billion", "style": "box", "at": 0.55},
   {"text": "Offline", "style": "big", "at": 1.8, "strike_at": 3.0, "out_at": 4.7},
   {"text": "an opportunity.", "style": "serif", "at": 4.95, "swap": true}
 ]}
```
- `style`: `big` (heavy uppercase), `box` (heavy uppercase in a primary box), `serif` (italic accent)
- `anim`: `mask` (rise from a mask - default), `slam` (scales down hard - punchlines), `drop` (letters
  fall and bounce - numbers/names)
- `strike_at`: draws a line through the word; `out_at`: line fades early; `swap`: occupies the
  previous line's slot (use after that line's `out_at`); `size`: font px at 1080 width (big 128, serif 72)
- `role`: `hook` (first beat) / `loop` (last beat, exits upward at the very end)

## page kinds (`"type": "page", "kind": ...`)
All pages accept `label` (small mono caption at the top, e.g. "AFRICA · MOBILE INTERNET").

| kind | fields |
|---|---|
| `title` | `kicker`, `title`, `serif` (italic second line). Full primary colour. 1.5-2.5 s |
| `counter` | `value`, `prefix`, `suffix`, `decimals`, `sub`, `count_at`, `count_dur`, `from` |
| `donut` | `value` (0-100), `suffix` ["%"], `sub`, `count_at`, `base` (faint earlier share, e.g. 63 when now showing 37) |
| `bars` | `items: [{label, value, at}]`, `unit` |
| `list` | `items: [{text, icon, at}]` (≤5 items) |
| `compare` | `left`, `op` ["="], `right`, `left_at`, `op_at`, `right_at`, `strike_at` (turns op into ≠), `verdict`, `verdict_at` |
| `source` | `name` (e.g. "GSMA"), `sub`, `zone` (drop-zone label) |
| `converge` | `items: [{text, icon, at}]` (3), `target`, `target_sub`, `target_at` |
| `apps` | `items: [{name, letter}]` (4), `delete_at`, `after` (serif word shown after deletion) |
| `pick` | `items: [{text, icon, at}]` (4) - eyedropper fills each tile on its word |
| `prompt` | `text` (typed), `answer_label`, `answer`, `answer_at` |
| `timeline` | `ticks: ["NOW", "", "2030"]`, `tracks: [[{text, from, to, at, alt}]]` (from/to in %) |
| `image` | `src` (path to the user's image/clip), `caption`, `full` (edge-to-edge) |
| `quote` | `text`, `by` |
| `comment` | `items: [{handle, text, at}]` |

Icons for `icon`: phone, wallet, chat, target, shield, chart, growth, trend_down, tower, globe,
people, user, tool, bank, money, check, cross, clock, bolt, heart, star, home, book, cart, car, lock,
wifi, signal, idea, rocket, calendar, mail, play, pin, language.

## Example (excerpt from a real 1:37 Reel)
```json
{"beats": [
 {"type":"words","at":0,"until":5.6,"role":"hook","lines":[
   {"text":"Almost a","style":"serif","at":0},{"text":"Billion","style":"box","at":0.55},
   {"text":"Offline","style":"big","at":1.8,"strike_at":3.0,"out_at":4.7},
   {"text":"an opportunity.","style":"serif","at":4.95,"swap":true}]},
 {"type":"page","kind":"source","at":6.25,"until":10.45,"label":"THE SOURCE","name":"GSMA","sub":"Tracks mobile connectivity globally","zone":"GLOBAL MOBILE CONNECTIVITY DATA"},
 {"type":"words","at":18.2,"until":22.9,"anim":"drop","lines":[{"text":"1 Billion","style":"big","at":18.35},{"text":"people, still not using it.","style":"serif","at":19.6}]},
 {"type":"page","kind":"donut","at":23.0,"until":25.9,"label":"AFRICA · MOBILE INTERNET","value":63,"sub":"of the population not using mobile internet","count_at":23.36},
 {"type":"page","kind":"title","at":42.8,"until":44.55,"kicker":"HERE'S THE THING","title":"But here's","serif":"the thing."},
 {"type":"page","kind":"list","at":54.3,"until":61.0,"label":"THE NEXT WAVE COMES WITH DIFFERENT","items":[
   {"text":"Devices","icon":"phone","at":54.9},{"text":"Budgets","icon":"wallet","at":56.14},{"text":"Languages","icon":"chat","at":57.24},
   {"text":"Needs","icon":"target","at":58.44},{"text":"Trust","icon":"shield","at":60.36}]},
 {"type":"page","kind":"compare","at":81.3,"until":85.95,"label":"THE MOST DANGEROUS ASSUMPTION","left":"Future users","right":"Current users","left_at":81.6,"op_at":83.2,"right_at":84.55,"strike_at":85.7,"verdict":"They won't."},
 {"type":"words","at":95.9,"until":97.2,"role":"loop","lines":[
   {"text":"still","style":"serif","at":96.0},{"text":"Not yet","style":"box","at":96.45},{"text":"Online","style":"big","at":96.82}]}
]}
```
