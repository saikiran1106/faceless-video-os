# 12. Universal lessons digest

Distilled from ~60 production lessons; language- and channel-independent. (Channel-specific ones — one language's grammar, a particular series — are left out.)

## Writing and structure
- **Hook:** state the conflict/mystery in one or two sentences and name the protagonist within the first 15 s; one stakes-raising line plus a concrete teaser of the twist by 25 s; welcome/intro comes after.
  No intro before ~30 s. Front-load the shock and cite the source early.
- **Shorts/Reels hooks** are a question built on an impossible-sounding claim; non-final episodes end on a cliffhanger naming what Part N+1 reveals; the final one on a platform-neutral follow CTA. Plan series at **3 parts** unless data justifies more.
- Read the spoken sentence before prompting each shot; **split any hold > 8 s** with intermediate beats; re-hook every 5–8 s, a new shot every 2–3 s.
- Treat the story as a person's arc, not a chain of causes. For an antagonist with a revenge motive, state what the source says they did *before* the wrong; never flatten them into a villain.
- Wording is authoritative once locked (see [7](07-audio-voice-and-mix.md)); pace via punctuation and pauses, not time-stretch.

## Visuals
- Character design research precedes any sheet: iconography, variants, weapon grip, period dress; fix sheets before scenes. One landscape model sheet per character (+ major state variants) with simplified/full ornament variants.
- Image QA checklist per image, logged in the scene manifest; render only after all pass. One single throttled batch with exponential back-off on 429.
- Image-to-video: effect persistence needs prompting *and* checking the last frame; fall back to a slow push-in of the approved still.
- Edit energy: first 25 s bright and high-contrast; BGM dynamics (subtle → build → resolve); 5–6 SFX at key moments only on narration-led pieces (heavy SFX on montage/motion-graphics pieces).
- Shot-scale ladder (≤ 2 same-scale shots in a row; wide + close in every 20 s).
- Overlays: ASCII digits for numerals; keep platform-specific CTA lines and safe zones; Flow/Veo watermark corner stays clear.

## Packaging
- Thumbnail: a **living face** with direct eye contact and readable emotion beats objects/statues; high-contrast text that survives 160×90; ≤ 4 words; text centred for grid/feed crops.
- Title: a single curiosity question with the broad keyword inside the sentence, not a pipe-stack. Tags: broad category keywords first, then narrow. Chapters from the real timeline.
- Cadence: ship the slot; do not skip a slot to perfect one video. Evaluate on retention at 15 s and early drop-off after 48 h.
- Never recommend a tool-testing format for news reels unless you actually ran the tool (news reels ≠ tool tests).

## Process gates
- Gate on **occurrence counts**, adjacent duplicates, duration bands and tail amplitude, run over **every** chunk, from the **transcript of the audio**.
- A release needs recorded locks (script, voice, character, scene manifest, edit, final delivery), a real checker result and a dated final verification.
- Retake budget discipline (≤ 2 takes; stop on first pass; state min and worst case).
