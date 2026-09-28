# 9. Configuration

Three layers, all optional: `channel.json` (your brand), `.env` (keys and knobs), format profiles (pacing and layout).

## `channel.json`

Created from `channel.example.json` by `faceless setup`. Gitignored. Missing fields fall back to defaults.

| Key | Meaning |
|---|---|
| `channel_name` | shown on the end card |
| `language` | default narration language (ISO code) |
| `niche` | context for the agent's writing |
| `voice.provider` | `auto`, `elevenlabs`, `openai` |
| `voice.elevenlabs_voice_id`, `voice.elevenlabs_model` | ElevenLabs voice + model |
| `voice.openai_voice`, `voice.openai_model`, `voice.style_instructions` | OpenAI voice, model, delivery direction |
| `style.caption_font` | CSS font family for captions/overlays |
| `style.font_file` | path (relative to repo) to a TTF/OTF to embed — needed for many non-Latin scripts |
| `style.caption_color`, `style.highlight_color`, `style.accent_color` | colours |
| `style.caption_case` | `as_spoken` or `upper` |
| `cta.subscribe_text`, `cta.follow_text`, `cta.comment_text` | CTA and end-card copy |
| `cta.end_card_seconds` | end card length (0 disables) |
| `music.default_track`, `music.volume` | background bed |
| `packaging.default_hashtags`, `packaging.default_tags` | seeds for every package |

## `.env`

See `.env.example`. Keys: `ELEVENLABS_API_KEY`, `OPENAI_API_KEY`. Everything else is an optional override (models, cost rates, browser adapter timeouts, `FACELESS_CHATGPT_PROJECT_URL`). Real environment variables win over `.env`.

## Format profiles

`faceless/profiles/short.json` and `longform.json`:

| Key | short | longform |
|---|---|---|
| `aspect`, `width`×`height`, `fps` | 9:16, 1080×1920, 30 | 16:9, 1920×1080, 30 |
| `duration_s` min/target/max | 20 / 55 / 120 | 180 / 480 / 1800 |
| `words_per_minute` | per language | per language |
| `hook_max_s` | 3 | 15 |
| `beats` min/target/max/max_hold (s) | 1.6 / 3 / 5 / 6 | 2.5 / 5 / 8 / 10 |
| `captions` | 3 words, 22 chars, 62% height, 78 px | 6 words, 42 chars, 86% height, 54 px |
| `chapters` | no | yes |

Edit them to change the house style for everyone using your fork. Add a language to `words_per_minute` to get accurate script-length checks.
