---
name: faceless-longform-from-voice
description: Turn a creator's own long recording into a finished long-form video: isolate, word timings, EDL of last takes, pause-only trimming, shot list on words, plan builder, chapter-chunk renders, sidechain mix, verified assembly, QA by transcribing the final mix, and re-timing the whole film when the creator sends an edited voice. Use for any 5-30 minute narrated video from a human recording.
---

# Faceless Long-form From Voice

Read `docs/learnings/06-longform-from-creator-voice.md` and `07-audio-voice-and-mix.md`.

## Procedure
1. Isolate the voice → Scribe word timings → `edl.txt` (last fluent take per line; segment ids) → cut → master -16 LUFS → `timeline.json`.
2. Shot list (`L<line>: spec ; word=spec`) → plan builder → `plan.json` (all cuts/overlays/SFX on anchor words) → bake graded stock (`automation/video_tools/grade_stock.py`).
3. Render chapter chunks with `automation/video_tools/render_queue_guarded.sh` (software GL, sealed per chunk) → mix → `assemble_verified.py`.
4. QA: transcribe the final mix and diff vs the clean-voice transcript; `blackdetect`/`freezedetect`; per-shot luma; frame-count check.
5. Creator approval → upload → link → client mail (only after approval).

## Hard rules
- **Never time-stretch or pitch-shift the creator's voice.** "Faster" = trim pauses only. Use the creator's own edit as-is.
- When the voice changes, **re-time by sequence diff** (difflib over normalised words), do not rebuild: matched words inherit line ids, deleted lines stay as placeholders (lines are indexed by position), re-run the builder, bake new grades, re-render.
- Music ~11.5 dB under the voice (min 9.5), SFX louder than music but ≥ 5 dB under voice.
- Never send an unapproved cut to a client.
