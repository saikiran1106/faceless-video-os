# 6. Long-form video from a creator's own recording

Worked example: a 30-minute self-recorded narration became a finished ~8–10 minute film (hundreds of cuts, 2.5D plates, stock footage, fossil/reference cards,
animated text, sound design) through seven versions. The reusable parts:

## Stage order that worked

1. **Isolate the voice** (cloud audio-isolation; same timeline, ~4 ms lag).
2. **Word timings** from a speech-to-text with word timestamps (Scribe v2). Keep that transcript as the single source of truth for time.
3. **EDL of takes** (`edl.txt`): per spoken line, keep the **last fluent take**. IDs are *segment ids*, not file line numbers.
4. **Cut the narration** from the EDL; trim dead air only (see rules); master at −16 LUFS; save a `timeline.json` (lines + words on the new clock).
5. **Shot list on words:** `L<line>: <spec> ; <word>=<spec>` where each spec is stock clip / AI plate / reference card / motion graphic with a transition. A builder turns it
   into `plan.json` where **every cut, overlay and sound cue sits on the first sound of its anchor word**.
6. **Render in chapter chunks** (Remotion, 24 fps, software GL), then **mix** (sidechain-duck music/beds/SFX under the voice, ≥ 12 dB voice margin, −14 LUFS),
   then **assemble** with a verifying joiner (see [8](08-media-integrity-and-flaky-hardware.md)).
7. **QA without ears:** transcribe the *final mix* and diff it against the clean-voice transcript (we got 96–98 % word match, ~4–20 ms median drift), run
   `blackdetect` + `freezedetect` over the film, scan for isolated outlier frames, and check per-shot average luma.

## Voice rules the creator set (lasting)

- **Never time-stretch or pitch-shift the creator's narration.** "Faster" means trimming pauses only (word gaps > 0.30 s → 0.125–0.20 s, line gap ~0.2, question ~0.36–0.5,
  chapter ~0.7–0.95). A 1.12× stretch plus pitch shifts was rejected as "cartoon". "Low pitch" complaints are fixed with level/EQ, not pitch.
- Target pace ~149 wpm for the narration of this format; ideal film length 8:20–8:30 for this story.
- Music ≈ 11.5 dB under the voice (min 9.5); SFX louder than music but ≥ 5 dB under the voice.
- **Never "improve" the creator's wording or audio** once they have edited it themselves; use their edit as-is.

## When the creator sends an edited voice (re-timing the whole film)

Do not rebuild from scratch: map the **new** word timeline onto the **old** one with a sequence diff (`difflib.SequenceMatcher` over normalised words). Words that match inherit the old
line id; 1:1 spelling-only replacements keep the old text so shot anchors still resolve; inserts join the neighbouring line; deleted lines stay as empty placeholders
(the builder indexes lines **by position**). Re-run the plan builder, bake any new graded stock segments, re-render, re-mix. A 96 %-identical edit re-timed ~270 shots and 79 text pops
automatically and kept every SFX anchor.

## Visual lessons

- Fast cutting (a new picture every ~1.7 s, nothing > ~3.3 s; long holds auto-split into jump cuts), English-only on-screen text when the audience reads the voice, real
  reference images (museum fossils, maps) as cards, heavy SFX (whoosh/click/glitch on every text pop and transition).
- Bake stock-clip grades with ffmpeg ahead of time (CSS filters/blend modes cost ~2 s/frame in software rendering). A "night" grade crushes already-dark clips to black:
  check per-shot luma and pick clips whose *graded* luma is ≥ 20.
- Fonts via the framework's font package (a custom `FontFace` + `delayRender` hung); never letter-space non-Latin scripts.
- Keep a version ledger (`plan_v*_delivered.json`) so any past cut can be reproduced and diffed (`plan_diff.py` re-renders only changed frame ranges).

## Delivery of each version

Build → verify → upload → link → mail only after the creator approves (they approved v3, rejected v4's voice, then iterated to v6/v7). Never email a client an unapproved cut.
