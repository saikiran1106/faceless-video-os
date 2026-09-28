# Faceless Video OS

**Read [AGENTS.md](AGENTS.md) before doing anything.** It is the single agent contract for this
repository (shared with Codex) and routes your first action.

Claude Code specifics:
- Skills are in `.claude/skills/` (mirrored from `skills/`; edit `skills/` then `faceless skills sync`).
- You have no built-in image model: use the `claude-code` host (`faceless browser ...`, ChatGPT via
  Playwright) or `api`/`manual`. See `skills/faceless-visuals/references/host-claude-code.md`.
- vidIQ: if `vidiq_*` MCP tools are available (search your deferred tools for "vidiq"), the
  `faceless-package` skill uses them for keyword research and title/thumbnail scoring.
