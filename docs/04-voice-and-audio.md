# 4. Voice & audio

Pick the mode at `faceless init --voice tts|upload`. It sets the stage order (see [How it works](02-how-it-works.md)).

## Your own recording (`upload`)

```bash
faceless voice ingest <p> path/to/narration.(mp3|wav|m4a|aac|flac|ogg|opus|webm|mp4|mov)
```
- The original is copied untouched to `03-voice/original.*`.
- The master `03-voice/narration.wav` is mono 48 kHz, loudness-normalised to −16 LUFS (true peak −1.5 dB).
- Record in a quiet, soft-furnished room; keep a constant distance from the mic; leave ~0.5s of silence at the start; don't re-read a line on the same take (the transcript will contain both reads — edit the file first).
- Video files are accepted: the audio track is extracted.

After transcription, `faceless script from-transcript` drafts the script from what you said. The agent fills in section titles, the hook and the promise — it never rewrites your words.

## AI voice (`tts`)

Only after the script is approved (CP1):
```bash
faceless voice generate <p> --dry-run        # provider, model, chunks, characters, estimated + worst-case USD
faceless voice generate <p> --yes
```

| Provider | Select with | Configure in `channel.json` → `voice` |
|---|---|---|
| ElevenLabs | `--provider elevenlabs` or auto when key + voice id exist | `elevenlabs_voice_id`, `elevenlabs_model` (`eleven_multilingual_v2` default; `eleven_v3` more expressive) |
| OpenAI | `--provider openai` or auto fallback | `openai_voice` (alloy, ash, coral, echo, fable, nova, onyx, sage, shimmer…), `openai_model`, `style_instructions` |

### How generation works

1. `pronunciation` respellings are applied to the TTS input only.
2. The narration is split into whole-sentence chunks under the provider's limit.
3. Each chunk is synthesised with the neighbouring text as context (ElevenLabs non-v3), saved to `03-voice/chunks/C###.mp3`, and recorded against the budget with a unique operation id.
4. Chunks are concatenated and normalised into `narration.wav`.

Re-running reuses every chunk whose text, voice and model are unchanged — you only pay for what changed.

### Retakes

```bash
faceless voice generate <p> --retake C004 --yes
```
Forces one paid retake of one chunk. A chunk can be taken at most 3 times in total; after that the CLI refuses and asks you to listen and change the text.

### Pronunciation

Respell phonetically in the script:
```json
"pronunciation": {"Mjolnir": "Myol-neer", "Nguyen": "Win", "GIF": "jif"}
```
Respelling is the reliable lever. Speed controls, SSML break tags and pronunciation dictionaries are inconsistent across models and languages.

### Expressive tags (ElevenLabs v3)

Use single-word tags only — `[whispers]`, `[excited]`, `[sad]` — and sparingly. Long descriptive tags garble nearby words, and stacking accent + register + emotion makes the voice sound synthetic.

## Verification

- Gate FF-VOICE-006 catches truncated chunks (> 25 characters per second).
- The transcript stage compares the heard words to the script (`script_match`); under 85% blocks.
- **A human should listen.** Transcription agreeing with the script does not prove names, accents or emotion sound right.

## Music

Put a licensed track at `projects/<slug>/08-compose/music.mp3`, or set `music.default_track` in `channel.json` (e.g. a file in `music_library/`). It plays under the voice at `music.volume` (0.12 default) with fades. Only use music you have the rights to.
