---
name: chatgpt-bulk-image-generation
description: "When generating multiple corrected/reference shot images via ChatGPT, request them as one batched prompt yielding separate images, not a single grid/collage"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fffcfa42-853b-4297-8214-67d926a8e6ce
---

When the owner needs several images generated via ChatGPT's image tool in one go (e.g. regenerating multiple flagged shots for a longform video), package all of them into a **single message**: a JSON array with one `{"id": ..., "aspect": ..., "prompt": ...}` object per image, preceded by an explicit instruction like "Generate the following as N separate, individual standalone images — one full image per JSON object, NOT combined into a single collage, grid, or contact sheet." Attach every needed character reference sheet together in that same message.

**Why:** First attempt was a single multi-panel contact-sheet image (like the existing character sheets do full-body + face-inset in one canvas) — the owner rejected this and confirmed ChatGPT can actually call its image tool multiple times in one turn and return genuinely separate image files when asked directly to generate them "separately." That's the reliable path, not a grid the user has to crop apart afterward.

**How to apply:** Any time I'm producing image-generation prompts for the user to paste into ChatGPT for this project (or similar reel/longform video projects — see [[character-design-research-rule]]), default to this batched-separate-images JSON array format instead of one-prompt-at-a-time, unless only a single image is actually needed.
