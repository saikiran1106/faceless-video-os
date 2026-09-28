# Faceless Forge

**Agent-driven, plug-and-play production pipeline for faceless YouTube, Shorts, Reels and TikTok.**
Bring a topic, or your own voiceover. Your AI coding agent (Claude Code or Codex) runs the rest:
script → voice → transcript → beat-synced keyframes → captions & overlays → render → publish-ready package.

```
            ┌─────────── AI voice (ElevenLabs / OpenAI) ───────────┐
 topic ──▶ script                                                   ▼
                                                           narration master ──▶ word-timed transcript
 your own recording ─────────────────────────────────────────────▲    (Scribe → Whisper → local)
                                                                                   │
        package ◀── render ◀── captions + overlays ◀── keyframes ◀── directed beats ◀┘
   (vidIQ / rules)  (Remotion)   (word-highlighted)   (Codex / ChatGPT / API / manual)
```

- **Two voice modes.** `tts`: the agent writes the script and generates the voice. `upload`: you record, the pipeline *understands* your narration and builds the video around it.
- **Works with whatever you have.** No keys at all? Upload your voice, transcribe locally for free, generate images in Codex or by hand, render with Remotion. Each API key you add unlocks more automation.
- **Host-aware image generation.** In Codex it uses Codex's built-in image tool. In Claude Code it drives ChatGPT in a signed-in browser. With an OpenAI key it can call the Images API directly. Same jobs, same outputs.
- **Sync you can't break.** The narration is the only clock. Beats are measured from word timings, each beat gets exactly one keyframe, and deterministic gates block gaps, overlaps, recast frames and wrong aspect ratios.
- **Human in the loop only where it matters.** Two checkpoints (approve the story, approve the cut) plus publishing. Every paid call is estimated first, capped by a budget, and needs `--yes`.
- **Short and long form.** 9:16 Shorts/Reels/TikTok and 16:9 long-form with chapters, from the same pipeline.

## Quick start

```bash
git clone <this repo> faceless-forge && cd faceless-forge
make install          # Python CLI (.venv) + Remotion composer + channel.json/.env
make demo             # a free, offline end-to-end video: no API keys needed
```
The demo writes `projects/demo-short/08-compose/renders/demo-short_youtube.mp4`. If you see a 9:16 video with synced, word-highlighted captions, a CTA and an end card, the install works.

Then open the folder in **Claude Code** or **Codex** and say:

> Make a 60-second Short about why the Titanic's sister ship survived.

or

> Here's my voiceover: ~/Desktop/episode3.m4a. Turn it into a long-form video.

The agent reads [`AGENTS.md`](AGENTS.md), runs `faceless doctor`, picks the right mode and host, and walks the stages with you.

Requirements: Python 3.10+, ffmpeg, Node.js 18+ (for Remotion). Optional: `pip install -e ".[browser]"` for the Claude Code image host, `".[local-asr]"` for free offline transcription.

## What you need for each capability

| Capability | Free / no key | With keys |
|---|---|---|
| Narration | Your own recording | ElevenLabs (`ELEVENLABS_API_KEY`) or OpenAI TTS (`OPENAI_API_KEY`) |
| Transcription | Local faster-whisper | ElevenLabs Scribe → OpenAI Whisper |
| Keyframes | Codex built-in, ChatGPT via browser (your subscription), or manual | OpenAI Images API |
| Render | Remotion (Node) or ffmpeg fallback | — |
| Packaging | Built-in YouTube rules | vidIQ MCP connected in your agent |

## Repository layout

```
faceless/            Python control plane: state machine, gates, providers, compose, CLI
  providers/         TTS, transcription, image API adapters
  browser/           ChatGPT image adapter (Playwright) for the Claude Code host
  schemas/           JSON Schema for every stage artifact
  profiles/          short.json (9:16) and longform.json (16:9) pacing/caption/format rules
composer/            One Remotion composition (StoryVideo) that renders any project from props
skills/              The reusable agent skills (canonical)
.claude/skills/      Mirror for Claude Code        .agents/skills/  Mirror for Codex
docs/                Full documentation
examples/            Example brief, script, visual bible, beats
projects/            Your productions (gitignored)
```

## Documentation

Start at [docs/README.md](docs/README.md):
[Getting started](docs/01-getting-started.md) ·
[How it works](docs/02-how-it-works.md) ·
[Workflows](docs/03-workflows.md) ·
[Voice & audio](docs/04-voice-and-audio.md) ·
[Providers & costs](docs/05-providers.md) ·
[Keyframes & hosts](docs/06-keyframes-and-hosts.md) ·
[Compose & render](docs/07-compose-and-render.md) ·
[Packaging & vidIQ](docs/08-packaging-and-vidiq.md) ·
[Configuration](docs/09-configuration.md) ·
[CLI reference](docs/10-cli-reference.md) ·
[Skills](docs/11-skills.md) ·
[Extending](docs/12-extending.md) ·
[Quality gates](docs/13-quality-gates.md) ·
[Troubleshooting](docs/14-troubleshooting.md)

## License

MIT. You are responsible for the rights to the content you generate and the terms of the AI services you connect.
