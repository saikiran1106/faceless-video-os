---
name: faceless-voice
description: Produce the narration master for a Faceless Forge project - either generate it with an AI voice (ElevenLabs or OpenAI TTS) from the approved script, or ingest and normalise the creator's own recording. Use for the voice stage, for voice retakes, pronunciation fixes, or when someone says "use my voiceover/audio".
---

# Faceless Voice

The narration master (`03-voice/narration.wav`, mono 48 kHz, loudness-normalised) is the clock for the entire video. Once later stages are built on it, changing it means redoing beats and keyframe timing — get it right here.

## Mode A — creator's own recording (`--voice upload`)

```bash
faceless voice ingest <p> ~/path/to/narration.m4a
faceless complete <p> voice
```
Accepts mp3/wav/m4a/aac/flac/ogg/opus/webm/mp4/mov. The original is kept untouched as `03-voice/original.*`. Advise creators: quiet room, consistent mic distance, trim long silences at the start, one take per file.

## Mode B — AI voice (`--voice tts`)

Requires CP1 approval of the script.

```bash
faceless voice generate <p> --dry-run      # chunks, characters, estimated AND worst-case cost
faceless voice generate <p> --yes          # only after the human says yes to that cost
```

Provider choice (`--provider auto` picks in this order):
- **ElevenLabs** — best quality, cloned voices, strongest for non-English. Needs `ELEVENLABS_API_KEY` + `voice.elevenlabs_voice_id` in `channel.json`. Default model `eleven_multilingual_v2` (stable, supports context stitching). `eleven_v3` is more expressive but needs careful tagging — see below.
- **OpenAI** — cheap and fast (`gpt-4o-mini-tts`), `voice.style_instructions` in `channel.json` steers delivery.

### Rules that save credits

- Chunks are whole sentences; unchanged chunks are **reused, never re-bought** on a re-run.
- Something wrong in one place? Retake ONE chunk: `faceless voice generate <p> --retake C004 --yes`. Never regenerate the whole track for a local defect.
- Max 2 retakes per chunk; the CLI refuses a 3rd. Stop, listen, and change the text (respelling) instead of rolling the dice.
- Mispronunciation fix = **respell the word** in `script.pronunciation` (e.g. `"Mjolnir": "Myol-neer"`). Speed settings, SSML breaks and pronunciation dictionaries are unreliable.
- ElevenLabs v3 audio tags: single words only (`[whispers]`, `[excited]`). Long descriptive tags garble surrounding words. Do not stack accent + register + emotion on one voice — over-specification is what makes AI voices sound synthetic.
- Do not bundle pacing "improvements" into a requested fix.

### Verification

1. The gate flags chunks speaking > 25 chars/s (truncated output).
2. The transcript stage compares what was heard to the script (`script_match`).
3. **ASR read-back is not proof it sounds right.** A human must listen to the master before CP2 — especially names and non-English lines. Say so explicitly when you hand over.
