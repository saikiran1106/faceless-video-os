# 2. How it works

## Division of labour

| Layer | Owns | Lives in |
|---|---|---|
| **Agent** (Claude Code / Codex) | Creative judgement: script, visual direction, prompts, review, talking to you | reads `skills/` |
| **Skills** | The know-how: rules, recipes, what "good" looks like | `skills/*/SKILL.md` |
| **CLI** (`faceless`) | State, contracts, gates, provider calls, rendering | `faceless/` |
| **Composer** | Drawing frames from props | `composer/` (Remotion) |

Python never makes creative decisions; the agent never bypasses the CLI's state and gates.

## Stages

```
tts:     brief → script ⏸CP1 → voice → transcript → visual_bible → beats → keyframes → compose ⏸CP2 → package
upload:  brief → voice → transcript → script ⏸CP1 → visual_bible → beats → keyframes → compose ⏸CP2 → package
```

Each stage produces one artifact, validated by a JSON Schema and a deterministic gate:

| Stage | Artifact | Produced by |
|---|---|---|
| brief | `01-brief/brief.json` | agent |
| script | `02-script/script.json` | agent (tts) / `faceless script from-transcript` + agent (upload) |
| voice | `03-voice/voice_manifest.json` + `narration.wav` | `faceless voice generate` / `faceless voice ingest` |
| transcript | `04-transcript/transcript.json` | `faceless transcribe` |
| visual_bible | `05-visual-bible/visual_bible.json` | agent (+ optional reference sheets) |
| beats | `06-beats/beat_manifest.json` | `faceless beats build` + agent direction |
| keyframes | `07-keyframes/keyframe_manifest.json` + `images/` | host (Codex / browser / API / manual) + `faceless images manifest` |
| compose | `08-compose/render_report.json` + `renders/*.mp4` | `faceless compose render` + `report` |
| package | `09-package/publishing_package.json` + `captions.srt` | `faceless package draft` + agent |

## State and resumability

`projects/<slug>/.faceless/run.json` records the stage order, each stage's status (`pending → completed | failed | awaiting_human`), the artifact hash each gate passed on, approvals, locks, budget and every paid provider operation. `events.jsonl` is the append-only history.

- `faceless complete` validates + gates the artifact and advances. A failed gate keeps you on the stage with the findings.
- A gate report is bound to the artifact's sha256. Edit the artifact after it passed and approval is refused until you complete again.
- `faceless reopen <p> <stage> --reason` goes back and invalidates everything after it.
- Paid operations are keyed by an operation id, so a crashed run re-executed never charges twice for the same chunk/frame.

## Sync model

1. The narration master is normalised to mono 48 kHz WAV. It is the only clock.
2. The transcript gives every word a start/end time.
3. Beats are cut at sentence ends, then clause pauses, then word count, targeting the profile's pace (≈3s Shorts, ≈5s long-form) and covering the audio with no gaps.
4. Each beat owns exactly one keyframe (`B007` ↔ `KF007`).
5. Compose converts every time to frames in Python; the React composition only draws.
6. Captions take their text from the script (exact spelling) and their timing from the transcript.

## Checkpoints

| Gate | When | The human approves |
|---|---|---|
| `cp1_story` | after the script stage | the story: hook, promise, narration (tts) or the agent's understanding of the recording (upload) |
| `cp2_final_preview` | after compose | the finished cut |

Paid voice generation waits for CP1. Publishing is never automatic.

## Project folder

```
projects/<slug>/
  .faceless/        run.json, events.jsonl, image_jobs.json, browser_jobs.json
  01-brief/ 02-script/ 03-voice/ 04-transcript/ 05-visual-bible/ 06-beats/
  07-keyframes/     images/, receipts/, contact_sheet.jpg, PROMPTS.md
  08-compose/       public/ (render assets), props_*.json, renders/, render_sheet_*.jpg
  09-package/       publishing_package.json, captions.srt, thumbnail.png
```
