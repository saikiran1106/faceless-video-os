---
name: faceless-wild-doc
description: Turn a client's finished script + narration audio into a complete fast-cut wildlife / natural-history / prehistoric documentary in the "wild-doc" style (built and proven over 7 client iterations) - real stock footage graded per chapter, AI plates in 2.5D depth parallax, real-photo evidence cards, English motion graphics, a cut every <= 3 s, word-locked SFX, chapter score under the voice, verified render, QA and YouTube package. Use when someone gives a script and a voiceover (any language) and wants "the full video", "in the wild animals style", "documentary from my audio", or a re-edit/re-time of such a film.
---

# Faceless Wild-Doc

The client gives **a script and the narration audio**. You deliver a finished 16:9 film. The CLI does the mechanics
(`faceless wild-doc ...`, code in `faceless/wilddoc/`, Remotion style in `styles/wild-doc/`); you do the directing.
Read `references/iteration-lessons.md` once: every default below exists because a client asked for it.

## Procedure
1. **Intake.** `faceless wild-doc new <slug> --script S --audio A --lang <code> --channel "<NAME>"`. The audio is used
   **as delivered** - never trim, level, time-stretch or pitch-shift it.
2. **Clock.** `faceless wild-doc run <slug>` → transcribe → align → draft, then it stops. Transcription: `--provider local`
   is free; ElevenLabs Scribe is the most accurate (paid, small; needs `--yes`). Check `match_ratio` (≥ 0.85 is normal;
   < 0.6 = wrong script/language) and read `01-audio/lines.txt` - the `L<i>` ids are what you direct against.
3. **Plan the film** (write it down before touching assets): chapters in the script (`## Title`), and for each chapter in
   `style.json`: `look` (dusk/ice/night/fire/dawn/jungle/desert/ocean/neutral), `title` (YouTube chapter name),
   `bed` (ambience `[name, gain]`), `music` prompt or `music_file`. Set `channel`, `theme`, `thumbnail`, `story_sfx`.
4. **Direct `02-direction/shotlist.txt`** (grammar: `references/shotlist-grammar.md`). The draft is plates-only; upgrade it:
   - **Real footage first** (`S:`) for anything a camera can film: landscapes, weather, living animals, fire, night sky.
     `faceless wild-doc stock-search <slug> "snow wolf" "blizzard plain" ...` (English queries) → **look at every sheet** in
     `06-assets/stock/sheets/` → `02-direction/stock_picks.txt` (`<id> <name>`) → `stock-fetch`. Footage must match the
     setting and era (a snowy story gets snow-only footage; no modern objects; no tropical forest on a steppe).
   - **AI plates** (`P:`) for what footage cannot show (extinct animals, the narrator's "you" in the past, reconstructions).
     Prompts in `02-direction/plates.json`, written in **English** describing the scene (translate meaning, never paste the
     narration), same visual world every time, subject in the lower two thirds. `faceless wild-doc images <slug>` uses the
     generator from `faceless login images`; LOOK at every plate against its prompt; delete and re-run a bad one.
   - **Evidence** (`R:`) whenever the narration claims something is real (fossil, skull, cave art, artifact, real photo):
     `refs-search <slug> TAG "query"` → look → `02-direction/refs.txt` with an honest badge (REAL FOSSIL / RECONSTRUCTION /
     REAL CAVE ART / REAL PHOTO). Never badge a reconstruction or an AI image as real.
   - **Graphics**: `O` overlays in **English** on key nouns, numbers and threats (kw, threat, danger, time, year, clock, thermo,
     fact, stamp, poll...), `M:title` right after the hook question, `M:endcard` on the last line, one `poll` mid-film.
     Catalogue + props: `references/graphics.md`; props for `M:` go in `02-direction/graphics.json`.
   - **Story sounds** (`X`) on animal/action words (howl, roar, footsteps, fire). Define each in `style.json` `story_sfx`.
   - Pace: a new picture every 1-3 s. The builder auto-splits anything > 3.3 s into punch-in jump cuts, but vary sources;
     don't reuse a clip within 60 s (`plan` reports reuse).
5. **Preview.** `faceless wild-doc plan <slug> --allow-missing` → `grade` → `render <slug> --chunks 0` → pull stills
   (`ffmpeg -ss T -i chunk.mp4 -frames:v 1 x.jpg`) and look: text legible, nothing near-black, faces not doubled.
6. **Full build.** `faceless wild-doc run <slug> --yes` (generates missing kit/story SFX/music with ElevenLabs if a key is set,
   else a free procedural kit), plan, grade, render (verified chunks), mix, assemble, thumbnail, QA, package.
   `faceless wild-doc qa <slug> --transcribe local` proves the narration survives the mix (≥ 90% word match).
7. **Watch the master end to end**, then send it to the human for approval. Never send an unapproved cut to a client.

## Revisions (client note → change)
| Note | Do |
|---|---|
| "voice is slow / fast / uneven" | ask for their re-edited voice; never stretch or pitch it. `faceless wild-doc voice <slug> new.wav` re-times everything (anchors are script words) |
| "cut faster" | more `word=spec` cuts per row; lower `style.cut.max_shot_s` |
| "music too loud / quiet" | `style.mix.music_margin_db` (default 11.5 dB under the voice; floor 9.5) |
| "more sound design" | more `X` rows; overlay/transition SFX are automatic |
| "no subtitles / native-script text" | default already: `captions: false`, English graphics |
| "this shot is wrong" | change that row only; only the chunks it touches re-render |

## Hard rules
- Script = text truth (spelling, line ids); audio = time truth. Don't rewrite the client's script.
- Look at pixels: every contact sheet, every plate, preview stills, the final master. "Passed QA" ≠ watched.
- Paid steps (Scribe, ElevenLabs SFX/music, OpenAI images, Flow clips) show the estimate first and need an explicit yes.
- Credit every Pixabay clip and Commons image (`package` writes them into `youtube.md`).
- One heavy render at a time; keep `render.concurrency` at 2 on laptops. If a chunk fails 3x, read its log before retrying.
