---
name: keyframe-beat-binding-law
description: NEVER re-cast keyframes onto different beats — a frame is born bound to one t_start and never moves; this single bug produced 49 defects in Maya Sabha EP02
metadata:
  type: feedback
---

A keyframe's `t_start` is part of its identity. The prompt that commissioned it
carried a timestamp and a narration line; the image must play at that beat and
nowhere else. If a frame is wrong for its beat, **regenerate it** — never move it
to a different beat, and never build a layer that redistributes frames.

**Why:** Maya Sabha EP02 (Sept 2026) generated 332 frames each bound to its own
beat, then I built a catalogue + shot-list layer that dropped `t_start` and
re-cast frames by matching my own *labels* against the script. Measured on the
shipped film: **only 14% of shots held the frame drawn for that beat**; 171 of
332 frames went unused. KF169 was drawn for Karna's insult at 4:56 and played at
0:26. KF120 was the Bhishma frame and got yanked to 0:08, so Bhishma was missing
from both the hook and his own scene. the owner logged 49 separate defects over an
hour; they were this one bug 49 times. Rebuilding from the declared bindings took
on-beat accuracy to 89%, distinct frames from 132/182 to 185/185, and deleted a
6-visual carousel that had been filling a whole minute.

Duryodhana Swargam and Khandava never failed this way because they had no
re-casting layer: `build_keyframes.py` keys authored direction by unit number,
`KF001` → unit 1 → 0.14s, permanently.

**How to apply:**
- Generate ~1 frame per slot. A large surplus (332 frames for 182 slots) is the
  signal that a re-casting layer is about to be invented — cut slots or drop
  frames instead. Merging adjacent beats on the same narration line is the only
  legal reduction; it is subtractive, never redistributive.
- Ship-gate: ≥95% of shots within 1.5s of their own declared `t_start`.
- Audit **pixels against narration**, never labels against narration. My label is
  a guess and will happily agree with the script while the picture disagrees —
  three rounds of audits passed this way.
- Measure block-level repetition (distinct visuals per minute), not just
  adjacency. Checking frames one at a time made a 6-visual/17-shot carousel
  invisible and I called it "verified frame by frame".
- Also check *subject* monotony, not just shot scale: six consecutive fist
  inserts passed a healthy framing ladder and a perceptual-hash dedupe.
- Characters sharing an archetype (Karna/Vikarna, Bhima/Dushasana) need an
  explicit separation contract in every prompt.

See [[chatgpt-drop-never-map-by-filename]], [[longform-motion-vocabulary]],
[[vidiq-longform-audit-rules]], [[maya-sabha-longform-status]].
Full post-mortem: `projects/maya-sabha-to-mahayuddham/_work/WHY_EP02_FAILED.md`
