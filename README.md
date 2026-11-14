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

> Here's my voiceover: ~/Desktop/episode3.m4a. Transcribe it with local Whisper and turn it into a long-form video.

More ready-made prompts: [Prompting guide](#prompting-guide--how-to-ask-for-a-video) below.

## Prompting guide — how to ask for a video

You don't run the commands yourself; you tell your agent what you want. Whatever you **name** (voice, transcriber, image source, budget…) is binding; whatever you leave out is chosen for you and announced before any money is spent. The agent stops for you only at **CP1** (approve the story), **CP2** (approve the final cut), and before each paid call.

### The master prompt

Copy it, fill in what matters to you, delete the rest:

```text
Make a [Short (9:16) | long-form (16:9)] video.

SOURCE      Topic: <what it's about>                       ← AI writes + voices it
            — or — My narration: <path/to/audio>             ← I recorded it
                     My script (what I read): <path>          ← optional: exact caption spelling
VOICE       [AI: ElevenLabs voice <id> | AI: OpenAI voice <name> | use my recording]
TRANSCRIBE  [local Whisper (free) | ElevenLabs Scribe | OpenAI Whisper | auto]
LANGUAGE    <en | hi | te | es …>          LENGTH  <~55 seconds | ~8 minutes>
AUDIENCE    <who>, TONE <e.g. suspenseful documentary>
IMAGES      [my ChatGPT in the browser | your built-in image tool (Codex) | OpenAI Images API | give me prompts]
STYLE       <visual style>; recurring characters: <names + looks>
BUDGET      $<N> for paid calls — show min and worst-case cost and ask before each paid step.
DELIVER     YouTube render [+ Instagram + TikTok] and a publishing package [using vidIQ].
```

### Case 1 — You upload your own audio

**1a. Your voice + local Whisper (free, offline, no keys)**
```text
Here's my voiceover: ~/Desktop/titanic_twin.m4a
Make a vertical Short from it. Transcribe it with local Whisper (free, offline) — no paid APIs.
Use my ChatGPT in the browser for the images, cinematic painterly 1910s style.
Deliver YouTube Shorts and Instagram renders plus the posting package.
```

**1b. Your voice + ElevenLabs Scribe (most accurate, 90+ languages)**
```text
My narration is ./audio/ep07_telugu.wav — it's in Telugu. Make a long-form 16:9 video.
Transcribe with ElevenLabs Scribe, budget $1. Images: your built-in image generation (Codex).
Captions font: fonts/NotoSansTelugu-Bold.ttf. Package it for YouTube with chapters.
```

**1c. Your voice + OpenAI Whisper**
```text
Turn ~/Podcasts/clip.mp3 into a 9:16 Short. Transcribe with OpenAI Whisper.
Use the OpenAI Images API for keyframes. Budget $4 total, ask before generating.
```

**1d. Your voice + the script you read from (your spelling on screen)**
```text
Voiceover: ~/rec/olympic.wav. The script I read is ~/rec/olympic_script.txt — use its spelling
for the captions. Transcribe locally. Make a Short. Images via my ChatGPT.
```

**1e. No keys at all, any image tool**
```text
I have no API keys. My recording is ./ep1.mp3. Make a long-form video with free local
transcription, and just give me the image prompts — I'll make them in Midjourney.
```

### Case 2 — The entire pipeline is AI-generated

**2a. ElevenLabs voice, verified with Scribe**
```text
Make a 50-second YouTube Short: "The Titanic had a twin — why did she survive?"
Write the script: hook in the first 3 seconds, one question answered at the end, comment CTA.
Voice: ElevenLabs voice id <voice-id>. Verify the audio with Scribe.
Images: my ChatGPT in the browser. Budget $2.
```

**2b. OpenAI voice + OpenAI Whisper + vidIQ packaging**
```text
Create an 8-minute long-form explainer on how lighthouses work, for curious adults.
OpenAI voice "onyx", calm documentary delivery. Transcribe with OpenAI Whisper.
Images: OpenAI Images API. Budget $6. Add chapters; use vidIQ for keywords and title scoring.
```

**2c. AI voice reading YOUR finished script**
```text
Here's my finished script: ./scripts/ep12.md. Don't rewrite it — only fix what TTS would misread
and show me. Voice: my cloned ElevenLabs voice <voice-id>. Short for YouTube, Instagram and TikTok.
```

**2d. AI voice + free local verification**
```text
Make a 45-second Short about the Voynich manuscript. OpenAI voice "nova".
Verify the narration with local Whisper. Images: my ChatGPT.
```

### What happens in each case

| | Upload (Case 1) | AI-generated (Case 2) |
|---|---|---|
| Order | brief → **voice ingest** → **transcribe** → script (the agent *understands* your narration) → **CP1** | brief → **script** → **CP1** → **voice generate** → **transcribe** (checks every word was spoken) |
| Then | visual bible → directed beats → keyframes → contact-sheet review → render → **CP2** → package | same |
| Captions | your recording's timing, script spelling if you gave one | the script's spelling, the audio's timing |
| Paid calls | only the transcriber (if not local) and images (if API) | voice + transcriber (if not local) + images (if API) |

### Replies at checkpoints and follow-ups

| Say | Effect |
|---|---|
| "Approved." / "Approve the cut." | passes CP1 / CP2 |
| "Reject: open on the iceberg line and cut paragraph two in half." | rewrites only that |
| "Do one chunk / one frame first so I can check it." | tests quality + real cost before the batch |
| "KF007 should be night; regenerate only that frame." | one regeneration, nothing else changes |
| "It says 'Olympic' wrong — fix only that word." | respelling + one-chunk retake |
| "Make the Instagram and TikTok versions too." | extra renders with the right end card |
| "Continue titanic-twin." / "Where are we?" | resumes from the saved state |

**→ Full guide with every case, the setting each phrase maps to, and tips: [docs/17-prompting-guide.md](docs/17-prompting-guide.md)**

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

## Automation & learnings

Beyond the core pipeline, this repo carries the **automation and field knowledge** from real productions, de-branded and free of secrets:

- **[`automation/`](automation/README.md)** — a login manager for persistent Playwright profiles (the human signs in once; nothing types credentials), a **ChatGPT image adapter** (resumable, parallel tabs, API-read completion), a guarded **Google Flow video adapter** (spend guards, credit cap, API harvest, native-audio dialogue), a **code-driven Motion Studio**, chunked **guarded renders with verified assembly**, and a **Premiere Pro handoff exporter**.
- **[`docs/learnings/`](docs/learnings/README.md)** — 12 distilled guides (browser logins, ChatGPT images, Flow, 2.5D parallax, motion studio, long-form from a creator's voice, audio/mix, media integrity on flaky hardware, Premiere handoff, delivery, agent operating rules, universal lessons) plus sanitised field notes.
- **[`docs/pipelines/`](docs/pipelines/README.md)** — seven end-to-end pipelines mapped stage by stage.
- Nine more **agent skills** (`faceless-browser-logins`, `-chatgpt-images`, `-flow-video`, `-keyframe-parallax`, `-motion-studio`, `-longform-from-voice`, `-media-integrity`, `-premiere-handoff`, `-delivery`).

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
skills/                   the 18 agent skills (canonical)  →  mirrored to .claude/skills and .agents/skills
automation/               battle-tested browser + media automation: login manager, ChatGPT image + Google Flow adapters,
                          motion studio, guarded renders, Premiere handoff exporter, media integrity tools
docs/                     documentation (below); docs/learnings = field-tested lessons; docs/pipelines = end-to-end maps
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
| [17. Prompting guide](docs/17-prompting-guide.md) | master prompt, every audio/transcription case, checkpoint replies |
| [18. Learnings](docs/learnings/README.md) | browser logins, ChatGPT images, Flow, parallax, motion studio, long-form, audio, integrity, Premiere, delivery |
| [19. End-to-end pipelines](docs/pipelines/README.md) | seven proven pipelines, stage by stage |

## License

MIT. You are responsible for rights to the content you generate and for following the terms of the AI services you connect.
