# Faceless Forge — agent contract

You are operating an agent-driven video pipeline. Codex reads this file; Claude Code reads
`CLAUDE.md`, which points here. Same rules for both.

## First action, every session

1. `faceless doctor` (or `.venv/bin/faceless doctor`). If it fails to run: `make install`.
2. If the user names an existing video or says continue/resume → read `skills/faceless-resume/SKILL.md`.
3. If the user wants a new video, short, reel, or has a voiceover to turn into a video →
   read `skills/faceless-produce/SKILL.md` and follow it. It routes every stage to its skill.
4. Vague request ("what can you do?") → run `faceless doctor`, explain the capabilities in plain
   words, and offer: (a) AI-voiced Short from a topic, (b) video from their own recording,
   (c) `faceless demo` to see the pipeline work with no keys.

## Skills (canonical copies in `skills/`, mirrored to `.agents/skills/` and `.claude/skills/`)

| Skill | Use it for |
|---|---|
| faceless-produce | Orchestrating a whole video, stage by stage |
| faceless-script | Brief + script, or understanding an uploaded narration |
| faceless-voice | AI narration or ingesting the creator's recording |
| faceless-transcribe | Word-timed transcript (Scribe → Whisper → local) |
| faceless-visuals | Visual bible, directed beats, keyframes on any host |
| faceless-compose | Remotion render: motion, captions, overlays, CTAs, end card |
| faceless-package | Titles, description, tags, chapters, thumbnail; vidIQ MCP when connected |
| faceless-review | Independent QA on pixels before every checkpoint |
| faceless-resume | Continuing a project in a new session |

Edit skills in `skills/` and run `faceless skills sync`; never edit the mirrors directly.

## Hard rules

- Every production goes through `faceless` stages; don't hand-roll scripts that skip gates.
- Paid calls: announce provider, model, count, minimum AND worst-case cost; wait for a yes; the CLI
  requires `--yes` and enforces the project budget. Never raise a budget yourself.
- Keyframes are bound to beats by content, never by filename/order; never recast a frame onto
  another beat.
- Only three human moments: CP1 story, CP2 final cut, publishing. Never upload or publish unasked.
- Do only the changes the human asked for. No bundled "improvements".
- Never store API keys in artifacts, commits or memory. `.env` and `channel.json` are gitignored.
- Files beat memory: `projects/<slug>/.faceless/run.json` is the source of truth.

## Image generation by host

- **Codex**: use your built-in image generation tool on the compiled jobs
  (`skills/faceless-visuals/references/host-codex.md`).
- **Claude Code**: `faceless browser generate` drives ChatGPT in a persistent browser
  (`.../host-claude-code.md`).
- **Any agent with OPENAI_API_KEY**: `faceless images generate` (`.../host-api.md`).
- **Otherwise**: `faceless images prompts` for a human (`.../host-manual.md`).
