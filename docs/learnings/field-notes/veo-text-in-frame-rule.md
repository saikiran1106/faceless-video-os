---
name: veo-text-in-frame-rule
description: "Veo CAN spell short text correctly but composes it wider than a 9:16 frame; command its share of frame width, not its margins"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2b55d1d3-2a82-4e93-85e8-6d3a535738bd
  modified: 2026-09-14T07:08:45.081Z
---

Veo 3.1 spells short English text (`THE ONE`, `GANESHA`, `HAPPY VINAYAKA CHAVITHI`) correctly
on the first take. The failure is **framing, not spelling** — it composes the lettering wider
than the vertical frame, so `GANESHA` renders as `ANESH` with both ends cut off.

**Why:** on the Vinayaka Chavithi title card this cost 4 extra generations (₹563 each pair)
before it converged. I had assumed text would fail at spelling and planned to composite it
locally; that assumption was wrong and the real defect took two retakes to diagnose.

**How to apply:**
- Asking for "a clear empty margin on the left and right edges" does NOT work. Take 2 obeyed
  the margin by **stacking the word vertically** down the frame instead (`G-A-N-E-H`).
- What works is commanding the text's **share of frame width** plus its orientation:
  *"written HORIZONTALLY on ONE SINGLE LINE, left to right, never stacked or vertical. The
  word is SMALL — it spans only the middle HALF of the frame width, with a very large empty
  area of smoke on the left side and on the right side of it."*
- Also name every letter as present and in order: *"All seven letters G A N E S H A are
  present, in order, complete."*
- Vertical 1080p **is** accepted on Vertex (`aspectRatio 9:16` + `resolution 1080p`) — the
  "9:16 caps at 720p" belief is wrong.
- `veo-3.1-generate-001` (full tier) is available on project-debc2ba0, not just lite.

Related: [[veo-keyframe-video-pipeline]], [[ask-before-paid-api-calls]],
[[credit-spend-announce-first]], [[ganesha-mass-title-card]]
