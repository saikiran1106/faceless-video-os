---
name: batch-attachment-set-governs-all
description: In a ChatGPT image batch the shared attachment set governs EVERY frame in the message — it propagates a correct reference and an irrelevant one with equal force
metadata:
  type: feedback
---

A batch sends ONE set of reference images for all N prompts (`batch_references()` takes
the union). That single fact caused both a fix and three defects on the Bhishma film.

**It fixes things.** Six shots rendered Nandini as a WHITE cow because none of them listed
her in `character_ids`, so `CS_NANDINI.png` was never attached. The very next batch did
attach it (via one shot that listed her) and every cow in that batch came out the correct
fawn — including shots that still didn't list her.

**It breaks things the same way.** Later, a batch containing two legitimate Nandini shots
put the cow on the KURUKSHETRA BATTLEFIELD in two other frames. And SH020 — an EMPTY
ashram courtyard — came back twice with Dyu, his wife and Vasistha staged in it, because
their sheets rode along in the attachment set. Three reference images outweigh the words
"no principals" every time.

**How to apply:**
* Group a batch so a character sheet is only attached alongside shots that character is
  actually IN. `plan_batches` caps the reference union at 8; it should also refuse to mix
  a character's shots with shots set where that character cannot be.
* **Never batch a frame whose subject is an empty place.** Generate it ALONE with
  `reference_paths: []`. That fixed SH020 on the first try after two batch failures.

Related: [[reference-image-beats-more-words]], [[chatgpt-batch-order-not-reliable]],
[[derived-queue-staleness]], [[keyframe-beat-binding-law]].
