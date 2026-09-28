# 16. Using with Claude Code and Codex

Faceless Video OS is designed to be driven by an AI coding agent. The agent is the director; the CLI is the crew.

## Claude Code

1. Install Claude Code (desktop app, CLI or IDE extension) and open the `faceless-video-os` folder.
2. It reads `CLAUDE.md` → `AGENTS.md` automatically, and the skills in `.claude/skills/`.
3. Ask for a video. Useful openers:
   - "Run faceless doctor and tell me what I can make."
   - "Make a 45-second Short about <topic>. Budget $1. Use my ChatGPT for images."
   - "Here's my voiceover: <path>. Make a long-form video."
   - "Continue my project <slug>." / "What's next on <slug>?"
4. Images: `--host claude-code` uses ChatGPT in the browser ([setup](15-claude-code-browser-setup.md)). No ChatGPT? Use `--host api` (OpenAI key) or `--host manual`.
5. vidIQ: add the vidIQ connector in Claude's settings; the package skill will find its `vidiq_*` tools.

Permissions: the agent will run `faceless …`, `ffmpeg`, `npx remotion …`. Allow those commands for the folder so it isn't asking every time; keep network-spending commands (`--yes` runs) on ask if you want a second look before money is spent.

## Codex

1. Open the folder in Codex (app or CLI).
2. It reads `AGENTS.md` and the skills in `.agents/skills/`.
3. Use `--host codex`: Codex generates each keyframe with its built-in image tool from the compiled jobs and files it with `faceless images record`. No browser or image API needed.
4. vidIQ: add it under `[mcp_servers]` in `~/.codex/config.toml`.

## Any other agent

Point it at `AGENTS.md`. Everything is plain files + a JSON-speaking CLI, so any agent that can run shell commands and read Markdown can drive it.

## What the agent will ask you

| Moment | Why |
|---|---|
| Format, voice mode, language, budget | only if you didn't say |
| **CP1** — approve the story | before any money is spent on voice |
| Every paid call | provider, model, count, minimum and worst-case cost |
| **CP2** — approve the cut | before packaging |
| Publishing | never done unless you ask |

Everything else — beats, prompts, retries within limits, QA on the pixels — it handles, checked by the gates.

## Tips

- Keep one project per video; series episodes share `channel.json` and can reuse a visual bible (copy it in).
- Ask for changes precisely ("KF007: make it night") — the skills tell the agent to change only what you asked.
- `faceless next <slug>` is the fastest way to see state; share its output if you ask another agent for help.
