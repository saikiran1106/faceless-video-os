# 4. Keyframe reels with 2.5D depth parallax

The look that replaced "slideshow with Ken Burns": **one generated keyframe per narration line, in one fixed art style, animated as
2.5D** (depth-parallax camera moves, cuts on spoken words, synced SFX). A cut-out-in-a-3D-set (Blender) route was tried and rejected as
"not looking good"; reusing old cut-outs with plain GSAP was rejected as templated.

## Pipeline

```
voice (the clock) → word timings → directed beats (1 per line) → keyframes (ChatGPT/Flow image) → depth map per keyframe
  → WebGL depth-parallax engine (one HTML scene per beat) → cuts on words + SFX cue sheet → capture/render → mix → QA
```
- **Depth:** Depth-Anything-V2-small ONNX, ~2 s/image on CPU.
- **Binding:** keyframes bind to beats by content (beat id), never by filename/order (see [2](02-chatgpt-image-generation.md)).
- **Corrections** are done at the source: edit the build plan/FX/CUES or regenerate that one beat's keyframe, then rebuild and re-render.
  Never splice a fix only into the final file.

## The doubled-face bug (and the fix)

A fixed-point depth solver *folds* at sharp depth edges and draws faces twice. Use a **first-hit ray-march** against a **dilated + blurred**
depth map. Always compare rendered faces against the source keyframe before delivery.

## Layered parallax rig (for stills-based long-form)

- Every plane (BG / MG cut-out / FG occluder / FX) gets the **same camera move multiplied by its own depth factor**, roughly 1.0 / 1.6 / 2.4 / 1.3;
  widen on wide shots, narrow on close-ups so faces don't swim. Total magnitude stays in a **4–9 %** band; bigger reads cheap.
- Plates come back authored full-frame, so two corrections are always needed: (1) foreground occluders covering > 35 % of the frame bury the
  subject. Offset each along its anchor edge until visible coverage is ~22 %, then nudge per shot away from the subject's head box; (2) hard-edged ink FX (smoke) read
  as squiggles at full opacity. Grade opacity and blur **by role**, not by area.
- **Prove it is parallax, not a zoom:** block-match a dolly shot between two frames and correlate displacement against radius from centre. One flat zoomed image ≈ 1.0;
  independent planes break it (we measured 0.62).

## Move vocabulary (what stops it reading as a slideshow)

PUSH · PULL · DRIFT · SETTLE · SNAP · SLAM · SHAKE · RACK · TILT · BREATH, chosen per shot from framing + emotion parsed from the beat text:
scheming → RACK (blur resolves), shock → SNAP (cut lands, camera reacts, dead still), silence → BREATH (near-still + light flicker), anger → SHAKE with decay.
Rules: every move decelerates on a bezier; direction alternates so consecutive moves never mirror; no move repeats within 3 shots; add a flicker light layer and
grain resampled every 2 frames.

## Edit grammar worth keeping

- Plan framing as a **ladder**: ≤ 2 consecutive shots at the same scale; every rolling 20 s block has a wide **and** a close/extreme close; medium ≤ ~55 % of shots.
- Cut ~0.18 s **before** the line it illustrates; a hold > 8 s gets intermediate beats.
- Replicating a real UI (e.g. a subscribe button): **measure the live page** (height, radius, padding, font, icon size, fill) instead of guessing.
- Teasers: withhold the payoff, eased dip-to-black, dialogue-led structure.
- Renders: use **software GL** and keep workers at 2–4 on laptops with an integrated GPU (see [8](08-media-integrity-and-flaky-hardware.md)).
