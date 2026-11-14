---
name: faceless-motion-studio
description: Run the code-driven Motion Studio (HTML seek(t) engine on HyperFrames): campaign brief with quoted claims to validated, built, rendered, QA'd variants and delivered links; or hand-written scene-by-scene story reels with SFX keyed to spoken words. Use for tech/news explainers, launch clips, product demos, and any voice-synced motion graphics.
---

# Faceless Motion Studio

Read `docs/learnings/05-motion-studio-code-driven-video.md` and `automation/motion_studio/README.md`.

## Procedure
`python automation/motion_studio/tools/studio.py doctor` → `assets pull` → `new <id>` → sources + **quoted claims** → plan (show the beat grid to the human before building) → `validate` → `build <id> --hooks A --formats 9:16 --ctas A` → `check` + `snapshot` → `build` (all) → `render` (2 workers) → read the QA contact sheets/seams → `REVIEW.md` → `deliver`.

## Hard rules
- Voice take = the clock; every scene/cue keyed to a spoken word; the same cue list drives the SFX mix.
- Every number on screen needs a claim whose quote exists word-for-word in the source file.
- Original motion graphics, not scraped footage/screenshots. Credit sources in small text.
- Effects bus ~5 dB under the voice, music 12–14 dB under; replace long impact-bass hits with short ones.
- 2 render workers; if the renderer crashes, capture `window.__render(t)` with Playwright and pipe to x264.
- Stages never spend money; `deliver` is the only upload and needs the human's go-ahead.
