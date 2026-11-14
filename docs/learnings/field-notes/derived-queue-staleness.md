---
name: derived-queue-staleness
description: The ChatGPT image queue is DERIVED from shot_plan.json; edit one without rebuilding the other and you generate from stale prompts
metadata:
  type: feedback
---

On the Bhishma long-form the shot plan was rebuilt at 01:15 but the derived
`.faceless/keyframes_all_queue.json` was still the 00:56 copy. The runner reads the
QUEUE. All 44 keyframes generated that night came from prompts that still said
"BARE FOREHEAD with no tilak" — the owner's verdict: "these are waste keyframes".

**Why:** nothing tied the two files together, so a plan edit looked applied and wasn't.

**How to apply:** the queue carries `built_from_shot_plan_sha`; the runner refuses to
start if it does not match `sha256(shot_plan.json)`, or if the plan is simply the newer
file. Never hand-edit the queue — regenerate it with `_work/build_queue.py`, which
writes the plan first and the queue second so the queue is always newer.

Two more bugs in the same family, both fixed:
* `reset_for_new_conversation` rewound `qa_pending` jobs to `queued`. qa_pending means
  the IMAGE EXISTS and a reviewer hasn't ruled — regenerating it spends the daily limit
  on a picture already on disk. It now skips `passed`, `failed_terminal` AND `qa_pending`.
* 9 shots still carried literal "BARE FOREHEAD" text for Jitavati and the fisher chief
  even after the tilak bible was locked, and 3 of those had NO character sheet attached.
  Grep the whole plan for the old instruction after any policy change — the CROWD block
  saying "No blank foreheads" does NOT override an explicit per-character instruction.

Related: [[keyframe-beat-binding-law]], [[chatgpt-batch-order-not-reliable]],
[[reference-image-beats-more-words]], [[character-design-research-rule]].
