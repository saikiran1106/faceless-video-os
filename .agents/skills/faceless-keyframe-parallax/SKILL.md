---
name: faceless-keyframe-parallax
description: Build 2.5D depth-parallax motion from one keyframe per narration line - depth maps, WebGL parallax engine with first-hit ray-march (no doubled faces), layered rig depth factors, move vocabulary, cuts on words and SFX cue sheet. Use for stills-based reels/long-form that must not read as a slideshow or Ken Burns.
---

# Faceless Keyframe Parallax

Read `docs/learnings/04-keyframe-reels-2p5d-parallax.md`.

## Procedure
1. Beats from word times (1 per line) → keyframes bound by beat id (see `faceless-chatgpt-images`).
2. Depth per keyframe (Depth-Anything-V2-small ONNX); **dilate + blur** the depth.
3. One scene per beat in a seek(t) WebGL engine using a **first-hit ray-march** (a fixed-point solver folds at depth edges and draws faces twice).
4. Camera move from the vocabulary (PUSH/PULL/DRIFT/SETTLE/SNAP/SLAM/SHAKE/RACK/TILT/BREATH) chosen by framing + emotion; magnitude 4–9 %, decelerating, alternating direction, no repeat within 3 shots.
5. Cuts ~0.18 s before the line; SFX cue sheet from word times; capture/render; mix.

## Verify
- Compare rendered faces with the source keyframe (doubling, swimming).
- Prove real parallax: block-match two frames of a dolly; displacement-vs-radius correlation must be well below 1.0.
- Planned framing ladder: ≤ 2 same-scale shots in a row; wide and close in every 20 s.
- Fixes go into the build plan or that one keyframe, then rebuild and re-render.
