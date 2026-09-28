# 5. Providers & costs

## Matrix

| Capability | Provider | Needs | Picked automatically when |
|---|---|---|---|
| Voice | ElevenLabs TTS | `ELEVENLABS_API_KEY` + `voice.elevenlabs_voice_id` | both are set |
| Voice | OpenAI TTS (`gpt-4o-mini-tts`) | `OPENAI_API_KEY` | ElevenLabs isn't fully configured |
| Voice | Your recording | nothing | `--voice upload` |
| Transcription | ElevenLabs Scribe (`scribe_v2`) | `ELEVENLABS_API_KEY` | key present |
| Transcription | OpenAI `whisper-1` | `OPENAI_API_KEY` | no ElevenLabs key |
| Transcription | faster-whisper (local) | `pip install -e ".[local-asr]"` | no keys |
| Keyframes | Codex built-in image tool | running in Codex | `--host codex` |
| Keyframes | ChatGPT via Playwright | `.[browser]` + a signed-in ChatGPT account | `--host claude-code` |
| Keyframes | OpenAI Images (`gpt-image-1`) | `OPENAI_API_KEY` | `--host api` |
| Keyframes | Anything else | a human | `--host manual` |
| Render | Remotion | Node 18+, `composer/node_modules` | default |
| Render | ffmpeg | ffmpeg | `--engine ffmpeg` |
| Packaging | vidIQ MCP | vidIQ connected to your agent | the agent sees `vidiq_*` tools |

Override any automatic choice with `--provider`. `faceless doctor` shows what is available.

## Cost control

- **Budget.** `faceless init --budget-usd N` sets the approved ceiling; `faceless budget <p> --usd N --approver you` changes it. Every paid call is recorded first and refused if it would exceed the budget. Default budget is 0: nothing paid runs until a human sets one.
- **Estimate first.** `voice generate`, `transcribe` and `images generate` print an estimate (and a worst case) and stop unless `--yes` is passed.
- **Idempotent.** Each paid call has an operation id (project + unit + content hash). Re-running after a crash doesn't pay twice for finished units.
- **Caps.** Voice chunks: 3 takes max. Keyframes: the skills cap creative attempts at 2 per frame.

### Estimate rates

The defaults are conservative placeholders. Set your plan's real rates in `.env`:

| Variable | Default | Meaning |
|---|---|---|
| `FACELESS_ELEVENLABS_USD_PER_1K_CHARS` | 0.30 | ElevenLabs TTS |
| `FACELESS_OPENAI_TTS_USD_PER_1K_CHARS` | 0.015 | OpenAI TTS |
| `FACELESS_SCRIBE_USD_PER_MIN` | 0.0067 | ElevenLabs Scribe |
| `FACELESS_WHISPER_USD_PER_MIN` | 0.006 | OpenAI Whisper |
| `FACELESS_OPENAI_IMAGE_USD` | by quality (0.02 / 0.07 / 0.25) | one image |

Subscriptions (ChatGPT Plus for the browser host, Codex) are not metered by the CLI. Record them manually with `faceless cost` if you want a full picture.

## Model overrides

`FACELESS_SCRIBE_MODEL`, `FACELESS_OPENAI_ASR_MODEL`, `FACELESS_OPENAI_IMAGE_MODEL`, `FACELESS_OPENAI_IMAGE_QUALITY`, `FACELESS_LOCAL_WHISPER_MODEL`, `FACELESS_LOCAL_WHISPER_DEVICE`, `OPENAI_BASE_URL` (for compatible gateways).
