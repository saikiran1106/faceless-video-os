# 1. Getting started

## One-command install

**macOS / Linux**
```bash
git clone https://github.com/saikiran1106/faceless-video-os
cd faceless-video-os
./install.sh
```
or without cloning first (the script clones into `./faceless-video-os`):
```bash
curl -fsSL https://raw.githubusercontent.com/saikiran1106/faceless-video-os/main/install.sh | bash
```

**Windows 10/11** (PowerShell)
```powershell
git clone https://github.com/saikiran1106/faceless-video-os
cd faceless-video-os
powershell -ExecutionPolicy Bypass -File install.ps1
```
or `irm https://raw.githubusercontent.com/saikiran1106/faceless-video-os/main/install.ps1 | iex`.

A full install takes 1–3 minutes on a fast connection. It is **safe to re-run** at any time: finished steps are detected and skipped, so re-running is also how you repair or update an install.

## What the installer does

| Step | macOS | Linux | Windows |
|---|---|---|---|
| Package manager | Homebrew (offers to install it) | apt / dnf / pacman / zypper | winget |
| git, curl | ✔ | ✔ | ✔ |
| Python 3.10–3.13 (prefers 3.12) | `python@3.12` | `python3` + `python3-venv` | `Python.Python.3.12` |
| ffmpeg + ffprobe | ✔ | ✔ | `Gyan.FFmpeg` |
| Node.js 18+ | `node` | distro, else **nvm** (no sudo) | `OpenJS.NodeJS.LTS` |
| Chromium runtime libraries | — | ✔ (for Remotion + Playwright) | — |
| `.venv` + the `faceless` CLI | ✔ | ✔ | ✔ |
| faster-whisper (free offline transcription) | ✔ | ✔ | ✔ |
| Playwright + Chromium (Claude Code image host) | ✔ | ✔ (+ system deps) | ✔ |
| Remotion composer deps + Remotion's headless browser | ✔ | ✔ | ✔ |
| `channel.json`, `.env`, `projects/`, skill mirrors | ✔ | ✔ | ✔ |
| `faceless` on your PATH | `~/.local/bin` symlink | `~/.local/bin` symlink | user PATH |
| `faceless doctor` summary | ✔ | ✔ | ✔ |

Why Python 3.10–3.13: some dependencies (e.g. faster-whisper's engine) don't ship wheels for 3.14 yet. If your default `python3` is newer, the installer uses an older one it finds, or installs 3.12, and rebuilds `.venv` if needed.

### Options

| `install.sh` | `install.ps1` | Effect |
|---|---|---|
| `--minimal` | `-Minimal` | CLI + Remotion only (no browser host, no local transcription) |
| `--no-browser` | `-NoBrowser` | skip Playwright/Chromium |
| `--no-local-asr` | `-NoLocalAsr` | skip faster-whisper |
| `--no-system` | `-NoSystem` | never install system packages; stop with instructions instead |
| `--recreate-venv` | `-RecreateVenv` | rebuild `.venv` from scratch |
| `--no-link` | — | don't touch PATH |
| `--demo` | `-Demo` | render the offline demo at the end |
| `--browser-login` | `-BrowserLogin` | open the one-time ChatGPT sign-in at the end |
| `--dir PATH` | `-Dir PATH` | clone location when run outside a checkout |
| `-y`, `--yes` | — | non-interactive (CI) |

If something fails, the installer prints which step broke; fix that and run it again.

## Check your setup

```bash
faceless doctor
```
Prints `capabilities` (what works now), failing `checks` with a `fix`, and `one_step_upgrades` (what one key or install would unlock).

## Prove it works (free, offline)

```bash
faceless demo                                   # 9:16 short, Remotion
faceless demo --format longform --engine ffmpeg # 16:9, ffmpeg fallback
```
The demo speaks a script with your OS voice, draws placeholder keyframes, and runs every real stage and gate. Output: `projects/demo-short/08-compose/renders/demo-short_youtube.mp4`.

## Configure

1. **`channel.json`** — channel name, language, voice, caption colours/font, CTA text, default hashtags. See [Configuration](09-configuration.md).
2. **`.env`** — optional keys. With none you can still: upload your own voice, transcribe locally, make images in Codex / ChatGPT (browser) / by hand, and render.
   - `ELEVENLABS_API_KEY` → AI voice (incl. cloned voices) + best transcription
   - `OPENAI_API_KEY` → OpenAI voice + Whisper + the Images API
3. **Claude Code image host** — sign in to ChatGPT once: `faceless browser setup` (see [Claude Code browser setup](15-claude-code-browser-setup.md)).
4. **vidIQ** (optional) — connect the vidIQ MCP server in your agent for keyword research and title/thumbnail scoring ([Packaging](08-packaging-and-vidiq.md)).

## Your first real video

Open the folder in Claude Code or Codex (see [Using with Claude Code and Codex](16-agents.md)) and ask in plain words:

**AI voice, from a topic**
> Make a 50-second Short about the Olympic, the Titanic's twin that survived. Budget $2.

**Your own voice**
> I recorded narration at ~/Desktop/ep1.m4a. Make a long-form video from it.

The agent walks the stages, stops for your approval of the story (CP1) and the final cut (CP2), and asks before every paid call. At any point `faceless next <project>` says exactly where things stand.

## Manual install (if you can't run the script)

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev,browser,local-asr]"
.venv/bin/playwright install chromium
cd composer && npm ci && npx remotion browser ensure && cd ..
.venv/bin/faceless setup && .venv/bin/faceless doctor
```

## Uninstall

Everything lives inside the folder except: `~/.local/bin/faceless` (symlink), `~/.faceless/` (browser profile, diagnostics), Playwright's browser cache (`~/Library/Caches/ms-playwright` or `~/.cache/ms-playwright`), the faster-whisper model cache (`~/.cache/huggingface`), and a `# faceless-video-os PATH` line the installer may have added to `~/.zshrc`/`~/.bashrc`. Delete those and the folder.
