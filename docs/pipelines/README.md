# End-to-end pipelines

Seven proven pipelines. Each lists stages, the tools that run them, the gates, and where the details live. All share the same skeleton: **voice is the clock → beats → media → compose → mix → verify → deliver**, with paid steps announced first.

| # | Pipeline | Input → output | Tools |
|---|---|---|---|
| A | [Topic → Short/Reel](#a-topic--shortreel) | a topic → vertical video + package | `faceless` CLI (this repo's core) |
| B | [Fast tech reel (images → Flow clips)](#b-fast-tech-reel-chatgpt-storyboards--flow-clips) | script + voice → ~45 s reel with real motion | `studio_os fast`, Flow adapter, Remotion |
| C | [2.5D keyframe reel](#c-25d-keyframe-reel) | script + voice → one-keyframe-per-line parallax reel | ChatGPT adapter, depth model, WebGL engine |
| D | [Live-action dialogue film](#d-live-action-dialogue-film-flow-native-audio) | researched screenplay → speaking-actors reel/film | ChatGPT sheets → Flow Ingredients + native voices |
| E | [Long-form from the creator's recording](#e-long-form-from-the-creators-recording) | raw VO → 8–20 min film | Scribe, Remotion, `video_tools`, mix |
| F | [Motion-graphics campaign](#f-motion-graphics-campaign-motion-studio) | brief + sources → N variants, QA'd | `automation/motion_studio` |
| G | [Editor handoff](#g-editor-handoff-premiere-project) | finished film → Premiere project zip + links | `video_tools/premiere_export.py`, R2, mail |

## A. Topic → Short/Reel
brief (CP1) → script → voice (AI or ingest) → word-timed transcript → visual bible → directed beats → keyframes → compose (captions, overlays, CTAs) → CP2 → package. See [`docs/02-how-it-works.md`](../02-how-it-works.md) and [`03-workflows.md`](../03-workflows.md).

## B. Fast tech reel (ChatGPT storyboards → Flow clips)
1. script approved → narration + mix → word timestamps
2. `shot_plan.json` (beats from word times; each beat has `clip_s` 4/6/8/10, refs, transition `cut | first_last:<next> | loop:<id>`, overlay, motion/camera prompt)
3. `studio_os fast storyboards` ×2: references first (human approves), then one storyboard per beat on 3 parallel tabs; `fast sheet` contact sheet (human approves)
4. `studio_os fast clips --dry-run` (free) → `--credit-cap N` (paid, approved): submit all clips back-to-back, harvest through Flow's media API
5. `fast match` (every clip starts on its own storyboard) → `fast props` → `fast render` (Remotion composition driven by the plan)
Time: ~40 min end to end, ~25 min unattended. Details: [learnings 2](../learnings/02-chatgpt-image-generation.md), [3](../learnings/03-google-flow-video.md).

## C. 2.5D keyframe reel
script + voice → word times → one directed beat per line → keyframe per beat (fresh chat for characters) → depth map → WebGL parallax scenes → cuts on words + SFX cue sheet → capture/render → mix → QA (faces vs source keyframe) → deliver link. Details: [learnings 4](../learnings/04-keyframe-reels-2p5d-parallax.md).

## D. Live-action dialogue film (Flow native audio)
research & film architecture (source-led, no invented plot) → screenplay → character/location sheets (ChatGPT, fresh chat per character) → **two-clip native-audio proof gate** → keyframes per clip → Flow Ingredients clips (one speaker per clip, ≤ 6 s, saved voice via `@Voice`) → transcription + ear check (≤ 2 retakes) → edit in the motion studio with SFX/score/narrator layers (dialogue stays Flow audio). Details: [learnings 3](../learnings/03-google-flow-video.md), [11](../learnings/11-agent-operating-rules.md).

## E. Long-form from the creator's recording
isolate → word timings → EDL (last take) → cut (pauses only) → shot list on words → plan.json → graded stock + plates → chapter-chunk renders (software GL, sealed) → sidechain mix → verified assembly → QA by transcribing the final mix → creator approval → upload → link → client mail. Re-timing to a re-edited voice by sequence diff. Details: [learnings 6](../learnings/06-longform-from-creator-voice.md), [7](../learnings/07-audio-voice-and-mix.md), [8](../learnings/08-media-integrity-and-flaky-hardware.md).

## F. Motion-graphics campaign (Motion Studio)
`studio.py doctor` → `assets pull` → `new` → sources + quoted claims → plan → `validate` → `build` one → `check`/`snapshot` → `build` all → `render` (2 workers) → QA review → `deliver` (R2 + 7-day links). Details: [learnings 5](../learnings/05-motion-studio-code-driven-video.md), [`automation/motion_studio/README.md`](../../automation/motion_studio/README.md).

## G. Editor handoff (Premiere project)
final picture + stems → `premiere_export.py` (xmeml + EDL + CSV) → package library + README → zip (stored, zip64) → CRC + decode checks → R2 upload + sha → presigned forced-download links → mail the client with honest limits. Details: [learnings 9](../learnings/09-premiere-and-editor-handoff.md), [10](../learnings/10-delivery-and-publishing.md).
