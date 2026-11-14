---
name: ai-voice-overspecification
description: "Over-specifying a character's voice (dialect + register + age + emotion) makes AI video dialogue sound synthetic; keep voice specs minimal"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2bf13675-1195-4620-9363-0cc605931685
  modified: 2026-08-14T23:10:12.752Z
---

On AI video generation (Seedance 2.5 / Higgsfield), stacking voice directions on one
character makes the dialogue sound obviously AI. the owner flagged this on THE BOSE EFFECT:
the early clips sounded good, the later ones "feel like AI".

The difference was in the prompt. Early scenes said only *"natural Indian English, never
American and never British."* Later scenes said *"eastern Uttar Pradesh Indian English,
medium tenor, cracked and quiet from dehydration, not persuading and not pleading."*

**Why:** given many vocal descriptors at once, the model performs the description instead
of speaking the line. Performance is what the ear hears as synthetic.

**How to apply:** name the accent's nationality, ban the wrong accents, stop. Do NOT
specify regional dialect, vocal register, pitch, timbre or stacked emotional textures.
Keep the words-per-second window and the clarity clause - those solve a different problem
(garbled fast speech) and do work. Same principle applies to faces: fewer competing
directions per element, not fewer total bytes. the owner's instruction was *"keep prompts simple
as at first... voice thing must be proper... don't over complicate it."*

**Refinement after research (2026-08-15):** naming ONE specific regional accent variety is
fine and beats a bare "English" — Seedance's own guidance says a bare label gives a flat
neutral read. The damage comes from stacking register, pitch, age and emotional textures
*on top* of the accent. Also confirmed: Seedance is a ByteDance model, so the spoken
language must be named explicitly before every non-Chinese line.

**The real fix for voice is not prompt wording at all.** Seedance 2.5 accepts audio
references and lip-syncs the picture to a supplied track. Generating dialogue in a speech
tool and attaching it solves pronunciation, robotic delivery and cross-clip voice
consistency in one move — prompt text cannot hold one character's voice across a chained
film.

Recorded in the skill at `.agents/skills/seedance-2-5-higgsfield/SKILL.md` under Hard
Model Limits. Related: [[elevenlabs-v3-tag-format-rule]], [[elevenlabs-credit-waste-rules]].
