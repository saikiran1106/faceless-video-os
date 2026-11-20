# Wild-doc graphics catalogue

All on-screen text is **English, upper case** (client v4 note), Anton headlines / Bebas labels / Inter small text,
with a decaying RGB-split "glitch-in". Colours come from `style.json` `theme` (`red ice gold cream hot`).

## Overlays (`O` rows) - on top of the picture
| kind | props | use for |
|---|---|---|
| `kw` | `text`, `sub?`, `tone` red/ice/gold/white, `pos` l/c/r, `x?` (red ✕) | key words, rules, "NO PHONE" triples (l, c, r) |
| `bigword` | `text`, `size?` | one huge glowing word |
| `word3` | `text`, `i` 0/1/2 | three words in a row (one row each) |
| `threat` | `n`, `name`, `sci`, `label?`="THREAT" | lower-third tag per animal in a list |
| `danger` | `n`, `name`, `sci`, `label?` | big chapter-opening threat card |
| `time` | `t` "8:00 PM", `sub` | clock time of the story |
| `year` / `counter` | `to`, `from?`, `label?`, `suffix?` | counting number (10,000 YEARS AGO) |
| `clock` | `n` "12", `label` | ring timer (HOURS UNTIL DAWN) |
| `thermo` | `from`, `to`, `unit?`, `label?` | temperature falling/rising |
| `bodyheat` | `from`, `to`, `unit?`, `label?` | body silhouette draining |
| `fact` | `kicker`, `title`, `body` | side card with a fact and a payoff |
| `stamp` | `text` | rubber stamp top right (REAL FOSSIL EVIDENCE) |
| `namecard` | `title`, `sub` | species / person name |
| `yeartag` | `text` | small tag top centre |
| `question` | `text` | question across the top |
| `measure` | `text` | ruler that draws then a size ("1 METRE+") |
| `poll` | `q`, `a`, `b`, `cta?`, `commentWord?` (anchor word for the CTA pop) | engagement poll mid-film |
| `videocard` | `text`, `sub`, `img` (public path) | "watch next" card |

## Full-screen graphics (`M:<name>[#key]`, props in `02-direction/graphics.json`)
Any of these accepts `bg: "<stock name>@<sec>"` (blurred footage background), `hue`, `dim`, `blur`, or `bgImg`.
| name | props |
|---|---|
| `title` | `kicker`, `lines` [..] (last line is the big one) |
| `card` | `kicker`, `title`, `sub` |
| `compare` | `a` {label, value}, `b` {label, value}, `verdict` |
| `scale` | `big`, `left` {img, label, h}, `right` {img, label, h} (PNG cut-outs with alpha in `08-compose/public/cut/`) |
| `timeline` | `title`, `from`, `to`, `ticks` [..], `bars` [{label, from, to, color, row}], `highlight` {from, to, label} |
| `map` | `img` (any map image in public/), `points` [{x, y, label}] as 0-1 fractions, `note` |
| `percent` | `value`, `label`, `punch`, `punchWord` (anchor in the same line) |
| `endcard` | `name`, `tagline`, `cta`, `next` |
| `black` | - (cut to black; pairs with an impact boom) |

Example `graphics.json`:
```json
{
  "title": {"kicker": "MY CHANNEL", "lines": ["COULD YOU SURVIVE", "ONE NIGHT ON THE", "SAVANNA?"], "bg": "tall_grass_wind@3", "hue": "rgba(200,120,40,.5)"},
  "compare": {"a": {"label": "YOUR TOP SPEED", "value": 24}, "b": {"label": "A HUNTING CHEETAH", "value": 110}, "verdict": "4X FASTER THAN YOU", "bg": "cheetah_run@2"},
  "timeline#1": {"title": "MILLION YEARS AGO", "from": 70, "to": 0, "ticks": [70, 50, 30, 10, 0],
                 "bars": [{"label": "BIG CATS", "from": 11, "to": 0, "color": "rgba(255,170,80,.9)"}]},
  "endcard": {"name": "MY CHANNEL", "tagline": "LOST STORIES OF THE WILD", "cta": "SUBSCRIBE"}
}
```

## Evidence cards (`R:`)
`refs.txt`: `<id> <tag>#<n> | LABEL | sub line | BADGE` (Commons pick) or `<id> local:<file> | ...` (your file in
`06-assets/ref/`). Badges must be true: REAL FOSSIL, REAL CAVE ART, REAL ARTIFACT, REAL PHOTO, RECONSTRUCTION.
