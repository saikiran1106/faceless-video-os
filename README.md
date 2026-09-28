# Faceless Video OS

**An agent-driven, plug-and-play production system for faceless YouTube videos, Shorts, Reels and TikToks.**

Give it a topic, or your own voiceover. Your AI coding agent (Claude Code or Codex) runs the whole pipeline:
**script → voice → transcript → beat-synced keyframes → captions & text overlays → render → publish-ready package.**

```
            ┌──────────── AI voice (ElevenLabs / OpenAI) ────────────┐
 topic ──▶ script                                                      ▼
                                                              narration master ──▶ word-timed transcript
 your own recording ────────────────────────────────────────────────▲    (Scribe → Whisper → free local)
                                                                                      │
        package ◀── render ◀── captions + overlays ◀── keyframes ◀── directed beats ◀─┘
   (vidIQ / rules)  (Remotion)   (word-highlighted)   (Codex / ChatGPT browser / API / manual)
```

## Install — one command

```bash
git clone https://github.com/saikiran1106/faceless-video-os
cd faceless-video-os
./install.sh            # macOS / Linux      (Windows: powershell -ExecutionPolicy Bypass -File install.ps1)
faceless demo           # free, offline test video — no API keys needed
```

`install.sh` installs **everything**: Python, ffmpeg, Node.js, Remotion and its headless browser, Playwright + Chromium for the Claude Code image host, free offline transcription, the `faceless` CLI, your config files, and the agent skills. It's idempotent: re-run it any time to repair or update. → [Installation details](docs/01-getting-started.md)

Then open the folder in **Claude Code** or **Codex** and say:

> Make a 60-second Short about why the Titanic's sister ship survived.

> Here's my voiceover: ~/Desktop/episode3.m4a. Turn it into a long-form video.

## Why it works

- **Two voice modes.** `tts`: the agent writes the script and generates the voice. `upload`: you record; the pipeline transcribes your narration, *understands* its story, and builds the video around it.
- **Start free, add keys when you want.** With no keys: upload your voice, transcribe locally, make images in Codex / your ChatGPT / by hand, render with Remotion. Each key unlocks more automation.
- **Host-aware images.** Codex → its built-in image tool. Claude Code → ChatGPT in your signed-in browser ([setup](docs/15-claude-code-browser-setup.md)). OpenAI key → the Images API. Or copy-paste prompts anywhere. Same jobs, same output paths.
- **Sync you can't break.** The narration is the only clock. Beats are measured from word timings; every beat owns exactly one keyframe; captions use your script's spelling with the audio's timing. Gates block gaps, overlaps, recast frames, wrong aspect ratios.
- **Human only where it matters.** Two checkpoints (approve the story, approve the cut) plus publishing. Every paid call is estimated first (minimum + worst case), capped by a budget, and needs `--yes`. Crashed runs never pay twice.
- **Short and long form.** 9:16 Shorts/Reels/TikTok with punchy 3-word captions; 16:9 long-form with chapters. Platform-specific end cards (Subscribe / Follow).

## What you need for each capability

| Capability | Free / no key | With keys or subscriptions |
|---|---|---|
| Narration | your own recording | ElevenLabs (incl. cloned voices) · OpenAI TTS |
| Transcription | local faster-whisper | ElevenLabs Scribe · OpenAI Whisper |
| Keyframes | Codex built-in · manual | ChatGPT via browser (your plan) · OpenAI Images API |
| Render | Remotion · ffmpeg fallback | — |
| Packaging | built-in YouTube rules | vidIQ MCP (keywords, title & thumbnail scoring) |

## The pipeline

| # | Stage | Output | Who |
|---|---|---|---|
| 1 | brief | topic, promise, format, target length | agent |
| 2 | script | narration with hook → payoff, sections, CTA — **CP1: you approve** | agent / derived from your audio |
| 3 | voice | `narration.wav` (normalised) | ElevenLabs / OpenAI / your file |
| 4 | transcript | word timings (+ script match check) | Scribe / Whisper / local |
| 5 | visual bible | style, characters, locations, reference sheets | agent + image host |
| 6 | beats | measured beats, each directed: what to show, shot size, camera move, overlay | CLI + agent |
| 7 | keyframes | one image per beat, reviewed on a contact sheet | image host |
| 8 | compose | MP4 per platform — **CP2: you approve** | Remotion |
| 9 | package | title, description, tags, hashtags, chapters, SRT, thumbnail | agent (+ vidIQ) |

→ [How it works](docs/02-how-it-works.md) · [Step-by-step workflows](docs/03-workflows.md)

## Repository layout

```
install.sh / install.ps1  one-command installers (macOS/Linux, Windows)
AGENTS.md / CLAUDE.md     the agent contract (Codex / Claude Code entry points)
faceless/                 Python control plane: state machine, gates, providers, compose, CLI
  providers/              TTS, transcription and image-API adapters
  browser/                ChatGPT image adapter (Playwright) for the Claude Code host
  schemas/                JSON Schema for every stage artifact
  profiles/               short.json (9:16) and longform.json (16:9)
composer/                 one Remotion composition (StoryVideo) that renders any project from props
skills/                   the 9 agent skills (canonical)  →  mirrored to .claude/skills and .agents/skills
docs/                     documentation (below)
examples/                 filled-in example artifacts
tests/                    pytest suite (offline, no keys)
projects/                 your productions (gitignored)
```

## Documentation

| | |
|---|---|
| [1. Getting started](docs/01-getting-started.md) | installer, options, first video, uninstall |
| [2. How it works](docs/02-how-it-works.md) | stages, artifacts, gates, checkpoints, sync model |
| [3. Workflows](docs/03-workflows.md) | recipes: AI-voice short, own-voice long-form, fixes, re-renders |
| [4. Voice & audio](docs/04-voice-and-audio.md) | recording tips, TTS providers, retakes, pronunciation, music |
| [5. Providers & costs](docs/05-providers.md) | provider matrix, selection order, budgets, rates |
| [6. Keyframes & hosts](docs/06-keyframes-and-hosts.md) | visual bible, directing beats, image hosts, binding law |
| [7. Compose & render](docs/07-compose-and-render.md) | motion, captions, overlays, CTAs, fonts, platforms |
| [8. Packaging & vidIQ](docs/08-packaging-and-vidiq.md) | titles, descriptions, chapters, thumbnails |
| [9. Configuration](docs/09-configuration.md) | `channel.json`, `.env`, format profiles |
| [10. CLI reference](docs/10-cli-reference.md) | every `faceless` command |
| [11. Skills](docs/11-skills.md) | how the skills work; customising them |
| [12. Extending](docs/12-extending.md) | new providers, overlay styles, gates, formats |
| [13. Quality gates](docs/13-quality-gates.md) | every FF-* rule |
| [14. Troubleshooting](docs/14-troubleshooting.md) | fixes for common problems |
| [15. Claude Code browser setup](docs/15-claude-code-browser-setup.md) | ChatGPT image generation via Playwright |
| [16. Using with Claude Code and Codex](docs/16-agents.md) | what to say, what the agent asks you |

## License

MIT. You are responsible for rights to the content you generate and for following the terms of the AI services you connect.
