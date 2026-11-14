---
name: chatgpt-batch-order-not-reliable
description: A numbered 10-image ChatGPT batch returns images in a DIFFERENT order than requested — never bind narrative keyframes to beats by position
metadata:
  type: feedback
---

**Measured 2026-09-20, Bhishma project.** A 9-item character-sheet batch, explicitly numbered
"IMAGE 1 of 9 … IMAGE 9 of 9" and asked for in order, returned **every item in a different slot**:

    requested  CS01 CS02 CS03 CS04 CS05 CS07 CS08 CS09 CS10
    delivered  CS09 CS01 CS08 CS10 CS03 CS05 CS02 CS07 CS04

Zero of nine matched. Explicit numbering does **not** make ChatGPT preserve order.

**Why:** binding by position is then a guess. For narrative keyframes that guess lands frames on
the wrong beat — the exact disaster behind [[keyframe-beat-binding-law]] (86% wrong beats, 49
defects). Related: [[chatgpt-drop-never-map-by-filename]], [[chatgpt-batch-drops-entries]].

**How to apply:**
- **Reference sheets / character sheets — batching is fine.** They are visually distinct, so each
  can be identified by content and filed correctly. Always verify by looking.
- **Narrative keyframes — one image per message.** Slower (~100s/frame) but identity is
  unambiguous. Do not batch-and-position-bind.
- A batch also returns progressive render frames: a 10-image reply showed 31 `<img>` elements.
  Dedup by **content hash**, not URL, and expect ~3 frames per final image.
