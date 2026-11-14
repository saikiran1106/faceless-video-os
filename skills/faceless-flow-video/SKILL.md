---
name: faceless-flow-video
description: Generate video clips in Google Flow (Gemini Omni) from keyframes through the guarded Playwright adapter - Frames vs Ingredients, spend guards, credit cap, dry run, API harvest, native-audio dialogue clips, never-resubmit recovery. Also covers Veo operation persistence. Use for any paid image-to-video run, dialogue films, or recovering clips after a timeout.
---

# Faceless Flow Video

Read `docs/learnings/03-google-flow-video.md`. Code: `automation/studio_os/flow`, `automation/studio_os/fast/clips.py`.

## Procedure
1. Sign-in profile (see `faceless-browser-logins`), then `python -m studio_os.cli flow doctor` (read-only UI survey, generates nothing).
2. Write the shot plan (beats, `clip_s`, refs, transition, motion prompt in five parts: anchor → timecoded beats → camera → light/style → audio).
3. **State minimum and worst-case credits and get an explicit yes.** Then `fast clips --dry-run` (free), then `fast clips --credit-cap N`; halt after clip 1 and check the burn rate.
4. Harvest/recover with `flow harvest` or the fast pipeline's API harvest; bind a clip to a beat by its **start-frame filename**.

## Hard rules
- NORMAL mode only (Agent chip off), planned settings, frames attached, prompt landed whole, **UI price equals expected price**, else stop.
- Frames mode for narration beats; Ingredients for dialogue (saved voice via `@Voice`, one speaker per clip, ≤ 6 s, native audio only, ≤ 2 retakes, A/B/A voice test before bulk).
- Affirmative prompts, one continuous shot, no generated text, humans still unless motion is the point; check the **last** frame for must-persist elements.
- Never resubmit on a timeout; never mint tokens (submit through the real button). Policy block = neutral re-staging, not charged.
- Veo API: persist the operation name to disk before polling; write the video before the ledger.
