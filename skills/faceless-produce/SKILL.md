---
name: faceless-produce
description: Run or continue an end-to-end faceless video production (YouTube long-form, Shorts, Reels, TikTok) with Faceless Forge - brief, script, AI voice or the creator's own recording, transcript, visual bible, beat-synced keyframes, captions/overlays, render and publishing package. Use whenever someone asks to make, produce, create or continue a faceless/narrated video, short or reel, or says "make a video about X", "I have my voiceover", "turn this audio into a video".
---

# Faceless Produce — the orchestrator

The repository is the brain; `faceless` (the CLI) is the control plane. Never rebuild the workflow from memory or improvise scripts that bypass it — every stage has an artifact, a schema, and a gate.

## 0. Start or resume

1. `faceless doctor` — read `capabilities` and `one_step_upgrades` to the user in plain words. Stop on critical checks.
2. Existing project? `faceless next <slug>` and continue from its `stage` (read `faceless-resume`). Never restart completed work.
3. New project — ask only what you cannot infer, then:
   ```bash
   faceless init <slug> --title "<working title>" --format short|longform \
     --voice tts|upload --host codex|claude-code|api|manual --language <iso> --budget-usd <approved>
   ```
   - **voice**: `tts` = AI voice from a script you write; `upload` = the creator already recorded narration.
   - **host**: who makes images. Inside Codex → `codex`. Inside Claude Code with Playwright → `claude-code`. Has `OPENAI_API_KEY` and wants it hands-off → `api`. Otherwise `manual`.
   - **budget**: the human's approved ceiling for paid calls. `0` blocks all paid calls — that is correct until they approve a number.

## 1. The stage loop

For every stage: `faceless next <p>` → read the named skill → produce the artifact → `faceless complete <p> <stage>` → fix critical findings (max 2 repair attempts, then surface ONE evidence-backed blocker to the human).

| Stage | Skill | Artifact |
|---|---|---|
| brief | faceless-script | `01-brief/brief.json` |
| script | faceless-script | `02-script/script.json` → **CP1: human approves the story** |
| voice | faceless-voice | `03-voice/voice_manifest.json` |
| transcript | faceless-transcribe | `04-transcript/transcript.json` |
| visual_bible | faceless-visuals | `05-visual-bible/visual_bible.json` |
| beats | faceless-visuals | `06-beats/beat_manifest.json` |
| keyframes | faceless-visuals | `07-keyframes/keyframe_manifest.json` |
| compose | faceless-compose | `08-compose/render_report.json` → **CP2: human approves the cut** |
| package | faceless-package | `09-package/publishing_package.json` |

Order differs by voice mode: `tts` writes the script before the voice; `upload` ingests + transcribes first and the script stage becomes *understanding the narration*.

## 2. Non-negotiables

- **The narration master is the only clock.** Beats come from measured word timings; nothing is timed by hand or by guess.
- **One keyframe per beat, bound forever.** Never move an image onto a different beat to "save" a generation — regenerate the beat that is wrong. Never bind images by filename or arrival order; bind by looking at them.
- **Ask before money.** Before any paid call state tool, provider, model, count, *minimum and worst-case* cost; wait for a yes. The CLI enforces this with `--yes` and the budget. Stop after the first unit to check the burn rate on big runs. Retakes are capped at 2.
- **Change only what was asked.** When the human requests specific fixes, do exactly those. Do not bundle "improvements" — unrequested changes cause full regenerations and wasted credits.
- **Humans only at CP1, CP2 and publishing.** Everything else is gated by code + `faceless-review`. Interrupt earlier only for a factual conflict, auth, budget, or an irreversible action.
- **Never publish or upload** without an explicit instruction naming the video. Packaging is not publishing.
- **Files beat memory.** If notes and artifacts disagree, trust `run.json` and the artifacts.

## 3. Checkpoints

- CP1 (`cp1_story`): show the hook, promise, full narration and target length. `faceless approve <p> cp1_story --approver <name>` or `faceless reject ... --note "..."`.
- CP2 (`cp2_final_preview`): show the render path, `faceless review render-sheet` image and any warnings. Same approve/reject.

## 4. Finish

After `package` completes, give the human: render paths, thumbnail, title, description, tags, chapters, SRT path, total spend (`faceless status` → budget). Offer (don't do) the upload.
