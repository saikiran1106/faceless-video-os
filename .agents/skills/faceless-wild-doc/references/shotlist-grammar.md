# Shot list grammar (`02-direction/shotlist.txt`)

One row per narration line. Line ids `L<i>` come from `01-audio/lines.txt`. Every cut lands on the first sound of a word.

```
## the-challenge                         (comment-style section marker, optional)
L1: S:savanna_sunset_aerial@2 ; alone=P:P01:dolly +t=whip +fx=dust
L5: S:moon_clouds@6 ; lions,=P:P10:crash +t=punch ; hyenas,=P:P18:crash +t=glitch
L6: S:grass_night_wind@1 +t=whip ; none=R:lion_skull +t=glitch +nolabel
L7: S:sunrise_savanna@8 +t=leak ; morning?=M:title +t=glitch
O L4 phone, kw 1.0 {"text":"NO PHONE","tone":"red","pos":"l"}
O L5 lions, threat 1.1 {"n":1,"name":"LIONS","sci":"Panthera leo"}
X L5 lions, lion_roar -8
```

## Row: `L<i>: <spec> ; <anchor>=<spec> ; ...`
- The first spec starts at the line (the very first row starts at frame 0).
- `anchor` = a word of that line in the **script's spelling**; punctuation and case are ignored. `^` = line start.
  Repeated words resolve left to right after the previous anchor in the same row.
- A shot lasts until the next shot starts. Shots > `style.cut.max_shot_s` (3.3 s) are split into jump cuts
  (`zoom`, `cut`, `glitch` cycle; stock keeps playing across the cut).

## Specs
| Spec | Picture | Source |
|---|---|---|
| `S:<name>[@sec]` | real footage from second `sec`, graded by the chapter look | `stock_picks.txt` (`<pixabay id> <name>`) or `06-assets/clips/<name>.mp4` |
| `P:<id>[:move]` | AI still in 2.5D depth parallax | `06-assets/plates/<id>.png` (prompt in `plates.json`) |
| `R:<id>` | evidence card: photo + blurred bg + label/sub/badge | `refs.txt` |
| `M:<graphic>[#key]` | full-screen graphic | props in `graphics.json["<graphic>#key"]` or `["<graphic>"]` |

Moves: `push pull panl panr rise drop dolly orbit hold crash` (`crash` = fast punch-in, for threats).

## Flags
`+t=` transition into the shot: `whip zoom glitch flash punch dip leak ice slide cut` (each has its own SFX) ·
`+fx=snow|embers|dust` particles · `+blur` · `+gray` · `+nolabel` (R) · `+look=<look>` overrides the chapter grade.

Good habits from the client film: `dip` into a new chapter, `punch`/`crash` on threats, `flash` on fire and reveals,
`glitch` on evidence and "but...", `leak` before the title, `whip` between footage.

## Overlay: `O L<i> <anchor> <kind> <seconds> {json}`
Sits on top of the picture; ends on a nearby cut automatically. Kinds and props: `graphics.md`.

## Story sound: `X L<i> <anchor> <sfx name> <gain dB>`
`sfx name` = a `style.json` `story_sfx` entry (generated with ElevenLabs) or a file `06-assets/sfx/<name>.mp3|wav`.
Typical gains: -8 (roar, charge) to -16 (breath, footsteps). The mix adds `mix.story_boost_db` (+3).

## Beds and music (style.json)
```json
"chapters": {
  "*":      {"look": "dusk"},
  "the-challenge": {"look": "dusk",  "title": "The challenge", "bed": ["savanna_night_bed", -24], "music": "Mysterious and urgent: ticking pulse, low strings, 110 BPM."},
  "the-hunt":      {"look": "night", "title": "The hunt", "bed": ["savanna_night_bed", -24], "music_file": "~/music/chase.mp3"}
},
"story_sfx": {"savanna_night_bed": ["Savanna at dusk: crickets, distant birds, warm wind through tall dry grass", 22],
              "lion_roar": ["A huge lion roar, powerful, echoing across an open plain at night", 6]}
```
