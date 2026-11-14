---
name: plan-tags-beat-prompt-text
description: When a shot's structured tags contradict its prose description, the tags win — audit tags, not prose, when renders come back wrong
metadata:
  type: feedback
---

Four separate defect classes on the Bhishma film were all the same bug: a shot's
STRUCTURED FIELDS said one thing and its prose said another, and the render obeyed the
fields.

* `location_id: LOC01` (battlefield) on SH009 and SH050, whose neighbours were all
  celestial or night-ashram. Both rendered on Kurukshetra. The prose was right.
* `character_ids: ["CS08_ADULT_BHISHMA, in his thirties"]` on SH154/SH155 while the
  prose said "the older warrior". He fell from the chariot dark-haired at 453s and
  landed white-haired at 461s — fifty years in three seconds.
* `CS10` used for SATYAVATI in every prompt but for JITAVATI in three shots'
  `character_ids`. One id, two different women; attaching CS10.png would have put a
  fisherwoman's face and dress on a king's daughter.
* A literal `BARE FOREHEAD` clause surviving in 9 prompts after the tilak bible was
  locked — and the CROWD block saying "No blank foreheads" did NOT override it, because
  the per-character instruction is more specific.

**How to apply:** when a render is wrong, audit the structured tags before rewriting
prose. Run a cheap pre-flight over the whole plan for: location islands (a shot whose
location differs from both neighbours), ids used for two names, a character named in the
description but absent from `character_ids`, and any stale instruction from a superseded
policy. On this film that audit found 8 location islands of which 6 were deliberate
intercuts — so read the neighbours before "fixing" anything.

Related: [[derived-queue-staleness]], [[character-design-research-rule]],
[[batch-attachment-set-governs-all]].
