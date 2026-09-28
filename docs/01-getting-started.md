# 1. Getting started

## Prerequisites

| Tool | Why | Install |
|---|---|---|
| Python 3.10+ | the `faceless` CLI | python.org, `brew install python`, `apt install python3-venv` |
| ffmpeg + ffprobe | audio/video processing | `brew install ffmpeg` · `sudo apt install ffmpeg` · `winget install ffmpeg` |
| Node.js 18+ | Remotion rendering | nodejs.org or `brew install node` |
| An AI coding agent | runs the pipeline | Claude Code or Codex (either works) |

## Install

```bash
git clone <repo-url> faceless-forge
cd faceless-forge
make install
```

`make install` creates `.venv/`, installs the CLI in editable mode, runs `npm install` in `composer/`, and runs `faceless setup` (creates `channel.json`, `.env`, `projects/`, and syncs the skills into `.claude/skills` and `.agents/skills`).

Without `make` (e.g. Windows):
```bash
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"      # macOS/Linux: .venv/bin/pip
cd composer && npm install && cd ..
.venv\Scripts\faceless setup
```

Optional extras:
```bash
.venv/bin/pip install -e ".[browser]" && .venv/bin/playwright install chromium   # Claude Code image host
.venv/bin/pip install -e ".[local-asr]"                                         # free offline transcription
```

Put `.venv/bin` on your PATH (or activate the venv) so `faceless` works directly.

## Check your setup

```bash
faceless doctor
```
Prints `capabilities` (what works now), `checks` that failed with a `fix`, and `one_step_upgrades` (what one key or install would unlock).

## Prove it works (free, offline)

```bash
faceless demo                       # 9:16 short with Remotion
faceless demo --format longform --engine ffmpeg
```
The demo speaks a script with your OS voice, draws placeholder keyframes, and runs every real stage and gate. Output: `projects/demo-short/08-compose/renders/demo-short_youtube.mp4`.

## Configure your channel

Edit `channel.json` — channel name, language, voice, caption colours/font, CTA text, default hashtags. See [Configuration](09-configuration.md). Add whatever keys you have to `.env`.

## Your first real video

Open the repo in Claude Code or Codex and ask in plain words. Two typical openings:

**AI voice, from a topic**
> Make a 50-second Short about the Olympic, the Titanic's twin that survived. Budget $2.

The agent will: write a brief and script → ask you to approve the story (CP1) → estimate the voice cost and ask → generate the voice → transcribe → build the visual bible and beats → generate keyframes on your host → render → ask you to approve the cut (CP2) → package.

**Your own voice**
> I recorded narration at ~/Desktop/ep1.m4a. Make a long-form video from it.

The agent will: ingest your audio → transcribe → summarise its understanding of your story for CP1 → visuals → render → CP2 → package.

At any point: `faceless next <project>` tells you (and the agent) exactly where things stand.
