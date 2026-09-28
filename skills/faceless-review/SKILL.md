---
name: faceless-review
description: Independently review a Faceless Video OS stage before it is locked or shown to the human - script, narration, beats, keyframes, render and package - against the brief, the locked artifacts and the rendered pixels. Use before CP1, before CP2, after any regeneration, and whenever asked to audit, QA or double-check a video.
---

# Faceless Review

Review as if you did not make it. Gates catch mechanical defects; you catch meaning.

## Always

- Read the artifact AND what it must agree with (brief → script → transcript → beats → keyframes → render).
- **Look at pixels, not labels.** Use `faceless review contact-sheet <p>` for keyframes and `faceless review render-sheet <p>` for the final cut. A keyframe manifest that says "pass" proves nothing.
- Report findings as: location, what is wrong, why it matters, the smallest fix. Critical = would embarrass the channel or break sync/facts. Fix critical findings or get the human to accept them explicitly — never pass with open criticals.

## Per stage

**Script**: Does the first line hook in ≤ 3s (short) / ≤ 15s (long)? Is there exactly one promise, and is it paid off? Could a stranger follow it (setup present)? Any unsourced factual claim? Anything the TTS will read literally (symbols, dashes, abbreviations)?

**Narration**: Listen if you can; otherwise read `script_match.missing`. Flag names and foreign words for a human ear — ASR agreement is not proof of good pronunciation.

**Beats**: Every `visual_objective` is concrete and shows THIS line (not the next). Framing varies. Emotional beats get closer shots; reveals get a cut or flash. No holds past the max without a reason.

**Keyframes** (contact sheet): For each frame — does it depict its line? Right characters with the same face/wardrobe as the bible? Right place and era? Anatomy (hands, eyes, extra limbs)? Text or watermarks baked in? Same image twice? Mark `--pass`/`--fail --note`, regenerate only failures.

**Render** (render sheet + watch): Image changes land on the spoken line; captions readable and not covering faces or the platform's UI zones; overlays/CTAs at sensible moments; no black or placeholder frames; end card correct for the platform; audio clean, music under the voice.

**Package**: Title ≤ 70 chars and honest; description's first 150 chars carry the promise + keyword; 3-5 hashtags; chapters valid; thumbnail readable at phone size.

## After human feedback

Apply exactly the requested changes and nothing else. Then re-run the affected stage's gate. If a correction reveals a rule worth keeping for future videos, add it to `channel.json` notes or your agent memory with the reason.
