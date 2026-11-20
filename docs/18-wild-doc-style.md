# 18. Wild-doc style: script + audio → finished documentary

**Wild-doc** turns a finished script and its narration audio (any language) into a complete 16:9 natural-history /
wildlife / prehistoric documentary in one fixed, proven look. It was built over **seven client iterations** of one
long-form film (a prehistoric-wildlife survival story), and every default is a client note that stuck
([the lessons](../skills/faceless-wild-doc/references/iteration-lessons.md)).

**The look:** real stock footage graded per chapter (dusk, ice, night, fire, dawn, jungle, desert, ocean) · AI stills
brought to life as 2.5D depth parallax · real-photo "evidence" cards (fossils, cave art, artifacts) · English motion
graphics with a glitch-in (threat tags, key words, counters, timers, thermometers, polls, title and end cards) · a new
picture every 1-3 s with punch-in jump cuts · camera kicks on stressed words · a sound on every cut and text pop ·
story sounds on the words (howls, roars, fire) · chapter score ~11.5 dB under the voice · −14 LUFS master.

## Quick start

```bash
faceless login images                          # once: ChatGPT in the browser, or the Codex CLI (see doc 19)
faceless wild-doc setup --depth --kit procedural   # once: Remotion packages, depth model, free SFX kit

faceless wild-doc new wolves --script ~/client/script.txt --audio ~/client/voice.wav --lang en --channel "WILD PLANET"
faceless wild-doc run wolves                   # voice → transcript → timeline → draft shot list, then stops
#   … direct the film (or ask your agent: "direct the wolves wild-doc") …
faceless wild-doc run wolves --yes             # images, sounds, plan, grade, render, mix, master, QA, package
```

No time to direct? `faceless wild-doc run wolves --auto` renders the drafted cut (an AI plate per line, auto jump cuts,
full sound design) with no human step after `new`.

In Claude Code or Codex, just say:

> Here is the client's script `~/client/script.txt` and voice `~/client/voice.wav` (Hindi). Make the full wild-doc
> video, channel name "THE WILD ERA". Use my Codex for images and local transcription.

The agent follows [`skills/faceless-wild-doc`](../skills/faceless-wild-doc/SKILL.md).

## Inputs

**Script** (`.txt`, UTF-8): one narration sentence per line (longer lines are split at sentence ends); `## Title`
starts a chapter (it becomes a YouTube chapter and a grade/music/ambience zone); `#` lines are comments.
```text
## The challenge
Imagine you are dropped alone on the African savanna at sunset.
No phone, no torch, no weapon, and eleven hours until sunrise.
## The heat
At six in the evening the ground still holds the heat of the day.
```
**Audio**: the narration exactly as the client wants it heard. It is **never** trimmed, levelled, stretched or
pitch-shifted. A re-edited voice later? `faceless wild-doc voice <project> new.wav` re-times the whole film.

## Project layout

```
projects/<slug>/
  project.json  style.json              per-project overrides of styles/wild-doc/style.json
  00-source/    script.txt, voice.*      the client's files
  01-audio/     voice_master.wav, transcript.json, timeline.json, lines.txt (L<i> ids to direct against)
  02-direction/ shotlist.txt, plates.json, stock_picks.txt, refs.txt, graphics.json
  06-assets/    stock/ (candidates, sheets, raw), ref/, plates/ (AI images), clips/ (own/Flow footage), sfx/, music/
  08-compose/   public/ (render inputs), plan.json, chunks/, segments/, mix.wav
  09-package/   <slug>.mp4, thumbnail.jpg, youtube.md, qa.json, master.json
```

## The steps (each is also its own command)

| Step | Command | Notes |
|---|---|---|
| voice | (in `new`) | 48 kHz mono master, as delivered |
| transcribe | `transcribe P [--provider local\|elevenlabs\|openai]` | paid providers show the estimate and need `--yes` |
| align | `align P` | script words get audio times (difflib); prints match ratio and `lines.txt` |
| draft | `draft P` | plates-only `shotlist.txt` + `plates.json` + `graphics.json` skeleton |
| stock | `stock-search P "query" …` → look → `stock_picks.txt` → `stock-fetch P` | Pixabay (`PIXABAY_API_KEY`, free) + `06-assets/clips/` |
| evidence | `refs-search P TAG "query" …` → look → `refs.txt` → `refs-fetch P` | Wikimedia Commons, credits recorded |
| plates | `images P` → `plates P` | generator from `faceless login images`; depth maps (Depth-Anything-V2 or a pseudo depth) |
| sound | `kit --via procedural\|elevenlabs`, `sound P --yes` | shared SFX kit; story SFX + chapter music from `style.json` |
| plan | `plan P [--allow-missing]` | every cut/overlay on its word; auto jump-cuts; reports reuse and missing assets |
| grade | `grade P` | bakes the chapter grade into stock segments; flags too-dark clips |
| render | `render P [--chunks 0 3]` | ~60 s chunks, frame-count + decode verified, only changed chunks re-render |
| mix | `mix P` | voice + score + beds + SFX, sidechain ducking, −14 LUFS |
| master | `assemble P` | per-chunk verified encode, glitch RGB split baked, concat, verified |
| finish | `thumbnail P`, `qa P [--transcribe local]`, `package P` | QA: decode, frames, loudness, black/freeze, narration audible |

`status P` shows what exists and what the shot list still needs.

## Directing (the creative part)

Grammar and examples: [shotlist grammar](../skills/faceless-wild-doc/references/shotlist-grammar.md).
Graphics and their props: [graphics catalogue](../skills/faceless-wild-doc/references/graphics.md).

```text
L5: S:moon_clouds@6 ; lions,=P:P10:crash +t=punch ; hyenas,=P:P18:crash +t=glitch
O L5 lions, threat 1.1 {"n":1,"name":"LIONS","sci":"Panthera leo"}
X L5 lions, lion_roar -8
```

## Style settings (`style.json`)

| Key | Default | Meaning |
|---|---|---|
| `channel` | name/tagline/cta | title kicker and end card |
| `theme` | red/ice/gold/cream/hot | graphics palette |
| `captions` | `false` | on-screen karaoke subtitles (script spelling) |
| `cut.max_shot_s` | 3.3 | longer shots become jump cuts of `split_to_s` (2.4) |
| `chapters.<name>` | `look`, `title`, `bed`, `music`, `music_file` | per chapter; `"*"` is the default |
| `story_sfx` | `{}` | `name: [prompt, seconds]` for ElevenLabs story sounds and beds |
| `plate_prompt_prefix` | documentary still… | prepended to drafted plate prompts |
| `mix` | margin 11.5, floor 9.5, −14 LUFS | music under voice, loudness |
| `render` | concurrency 2, swangle, 60 s chunks | keep 2 on laptops |
| `thumbnail` | bg, lines, tag | centred text block |

## Costs

Free path: local Whisper, Codex/ChatGPT plan images, Pixabay + Commons, procedural SFX kit, your own music files.
Paid (always estimated and confirmed first): ElevenLabs Scribe (~$0.40 per hour of audio), ElevenLabs SFX/music
(your ElevenLabs credits), OpenAI Images API, Google Flow clips (Flow credits).

## Limits

- 16:9 long-form only (the graphics are laid out for 1920×1080).
- The procedural SFX kit is a placeholder; generate the ElevenLabs kit (`kit --via elevenlabs --yes`) for delivery.
- Without onnxruntime + the depth model, plates use a pseudo depth (gentler parallax). `pip install onnxruntime` and
  `faceless wild-doc setup --depth`.
- Editor handoff (Premiere XML package): see [`faceless-premiere-handoff`](../skills/faceless-premiere-handoff/SKILL.md).
