---
name: faceless-script
description: Write the brief and narration script for a faceless video (Shorts/Reels or long-form) in any language - hook, one promise, retention structure, sections, CTA - or, when the creator uploaded their own audio, derive the script from the transcript. Use for the brief and script stages of Faceless Video OS, or whenever asked to write/fix a voiceover script.
---

# Faceless Script

## Brief (`01-brief/brief.json`)

```json
{
  "version": "1.0",
  "topic": "Why the Titanic's sister ship survived",
  "title": "The Titanic Had a Twin. Here's Why It Survived",
  "format": "short",
  "language": "en",
  "audience": "history-curious viewers, 18-40",
  "angle": "the overlooked sister ship, not the famous wreck",
  "promise": {"question": "Why did the twin survive what sank the Titanic?", "payoff": "It was rebuilt after the disaster with a double hull"},
  "target_duration_s": 55,
  "voice_mode": "tts"
}
```

Pick ONE promise: a question the opening makes the viewer ask and the ending answers. Everything else serves it.

## Script (`02-script/script.json`) — AI-voice mode

Required: `language`, `title`, `source: "written"`, `narration`, `hook{text, seconds}`, `promise{question, payoff}`, `sections[]` (that partition the narration exactly — they become chapters), optional `claims[]{text, source_refs[]}`, `cta{mid,end}`, `pronunciation{word: respelling}`.

Length: target seconds × words-per-minute (en ≈ 150-160, hi ≈ 130-140, te/ta ≈ 105-110, es ≈ 155-165). The gate enforces ±25%.

### Structure that holds viewers

1. **Hook (0-3s short / 0-15s long):** open on the most surprising true line, then the question. No greetings, no channel intro, no "in this video".
2. **Setup:** the minimum context a stranger needs to care. A story nobody can follow loses them at 0:15-0:20.
3. **Escalation:** each section raises the stakes or reveals a new piece. Change something every few seconds (a new fact, place, character or number).
4. **Pattern interrupts at ~35% and ~75%:** a reveal, number, or open loop. These are where retention recovers — also where CTAs go.
5. **Payoff:** answer the promise clearly. Don't trail off.
6. **CTA:** one ask (comment prompt works best on Shorts). Long-form: a soft mid-roll ask after the first payoff, not at the start.

### Writing for the ear

- Short sentences. One idea per sentence. Name things instead of "it/this".
- Write numbers as they should be spoken if the voice misreads digits.
- No spaced dashes, brackets or symbols that TTS reads aloud. Use full stops for pauses.
- Mispronounced names go in `pronunciation` as a phonetic respelling. Captions keep the real spelling.
- Cite `source_refs` for factual claims; soften anything you cannot source.

Present the script to the human for **CP1** before any paid voice call.

## Script — uploaded-audio mode ("understand the narration")

1. `faceless script from-transcript <p>` drafts `script.json` from what was actually said, with sections cut at the speaker's longest pauses.
   - If the creator gave you the **script they read from**, pass it: `faceless script from-transcript <p> --script-file <file>`. Its exact spelling and punctuation become the captions; the recording still supplies every timing. It is refused if under 70% of it was actually heard (wrong script, or heavy ad-libbing) — tell the creator which words were missing.
2. Read the whole transcript. Replace every `TODO`: section titles, the promise question/payoff, and fix the hook if the first sentence is not it.
3. **Never rewrite the narration text** — it must match the recording. You may correct ASR misspellings of names/terms in `narration`; those corrections flow into the captions as long as the text still matches the audio (≥ 70%). Rewrites that stop matching are ignored and the raw transcript is shown instead.
4. Summarise for the human at CP1: what the video is about, its hook, sections, and anything unclear or factually doubtful you noticed.
