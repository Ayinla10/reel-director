# Directing the graphics

You are designing for a phone screen watched with the sound on and off. The speaker is the star;
graphics make a point land harder, clearer or more memorable. These rules come from real creator
feedback - follow the reasoning, not just the letter.

## Hard rules (why)
- **Never cover the face.** People trust faces; a card over the face reads as cheap and hides the
  emotion. Anything bigger than a word goes on a **full-screen page** (cutaway) while the voice
  continues, then cut back to the speaker.
- **Brand colours only.** Primary + white/neutral, plus tints of the primary. No rainbow accents;
  consistency is what makes a channel recognisable.
- **Sync to the word.** An element appears on the exact word that introduces it (word start time from
  words_cut.json, minus ~0.05 s). Early or late graphics feel amateur.
- **Speaker on screen ≥ ~60%** (moderate density). Pages are punctuation, not wallpaper.
- **Captions stay readable**: they're placed below the chin automatically; on pages they switch to
  page colours. Hide them only where giant on-screen words already say the same thing.

## What deserves what
| Moment in the script | Treatment |
|---|---|
| Opening claim / hook (first 3 s) | `words` beat, `role: "hook"`, mask reveal, 2-3 lines, one boxed word |
| A single striking number | `counter` page, or `donut` for a percentage of a whole |
| Several numbers / ranking | `bars` page |
| "X, Y and Z" lists | `list` page, each item on its spoken word |
| Two things contrasted / a wrong assumption | `compare` page with `strike_at` on the turning word |
| Citing a source / report / study | `source` page (file-drop) - only names the speaker actually said |
| Several groups chasing one thing | `converge` page |
| Things becoming obsolete / deleted | `apps` page (jiggle + delete) |
| "Build for / focus on / pick" choices | `pick` page (eyedropper samples each) |
| Looking something up, citing a stat/source ("Databricks found...") | `search` page: real-looking Google search, highlight the number |
| Asking an AI / chatbot behaviour / an agent doing tasks | `chat` page (typed question, streamed reply, `steps` for agents) |
| A question the audience would ask | `prompt` page (typed bar + answer) |
| Before/after, now vs future, roadmap | `timeline` page |
| A pivot ("But here's the thing") | `title` page, 1.5-2 s, full primary colour |
| Punchline / one-word verdict | `words` beat with `anim: "slam"` and a boxed word |
| Quote from someone | `quote` page |
| Call to action | `comment` page (bubbles with the keyword) or `words` beat |
| A concrete, visual noun or scene ("customer service", "a market in Lagos", "data centre") | `broll` beat, 2.5-4.5 s, `query` = plain description of the shot |
| A still image the user supplied | `image` page (`full: true` for edge-to-edge) |

Don't invent facts, sources or numbers the speaker didn't say. Short labels (2-5 words) beat
sentences; the voice carries the detail.

## Realistic UI moments
`search` and `chat` imitate real apps on purpose - viewers recognise them instantly, so they keep the
real apps' look instead of the brand colours. Write `text`/`user` the way a person would actually
type it (lowercase search queries, natural questions). Never put words in a real company's mouth:
result titles/snippets restate what the speaker said, with neutral site names for anything else.

## B-roll: when it helps
B-roll earns its place when the words name something people can *see* and the speaker's face adds
nothing for those seconds: examples, places, products, "imagine..." scenes, lists of concrete things.
Avoid it for opinions, emotions, punchlines and calls to action - that's when the face matters most.
B-roll is always **video** (photos look like a slideshow). Write `query` like a stock-footage search ("woman typing on laptop at night", "phone notifications",
"robot arm assembly line"): 3-6 plain words, no brand names. Keep 1 cutaway per ~15-25 s; never two
cutaways back-to-back without the speaker in between. Captions stay on during B-roll.

## Pacing
- Moderate: one page or title every ~8-12 s, words beats in between; nothing for the first 0.5 s of
  speech after a page (let the face breathe).
- A page lasts 2.5-7 s: long enough to read, short enough to return to the speaker.
- Never stack two pages back-to-back without at least ~1.5 s of speaker between (except a title card
  leading into a page).
- Words beats: 1.2-5 s; hook up to ~5.5 s.

## Loops (ending: "loop")
The video should replay without a visible end. Set `"loop": true` in edit.json (last shot framed
like the first). The first beat is a `words` beat with `"role": "hook"`; the last beat is a `words`
beat with `"role": "loop"` that **mirrors the hook's layout** (same number of lines, same styles)
using the final words, from ~1.3 s before the end until the end. The loop lines exit upward on the
last frames exactly as the hook lines enter from below at 0 s. Script-wise, the strongest loops end
on a line that leads naturally into the opening line - point that out to the user if their script
almost does it.

## Other endings
- follow: `title` page (last 2.5 s) with handle as title and a serif line ("Follow for more").
- comment: `comment` page with 2 bubbles: the creator asking, a viewer replying with the keyword.
- link: `title` page with the URL.

## Before showing the preview
Look at the snapshot sheet and fix: words touching the head, text cut off at the edges, a page
appearing late/early, captions overlapping page content, two effects fighting for attention.
