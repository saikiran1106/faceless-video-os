# 11. Skills

Skills are Markdown playbooks the agent loads on demand: the rules, recipes and judgement that make the output good. The CLI does the mechanics; the skills tell the agent what good looks like.

## Where they live

```
skills/<name>/SKILL.md          canonical — edit these
.claude/skills/<name>/          mirror loaded by Claude Code
.agents/skills/<name>/          mirror loaded by Codex
```
`faceless skills sync` (or `make skills`) copies `skills/` into both mirrors. `faceless doctor` warns when a mirror drifts. Both mirrors are committed so a fresh clone works immediately.

Each `SKILL.md` starts with YAML frontmatter — `name` and a `description` that says when to use it. Agents choose skills by that description, so keep it specific.

## The set

| Skill | Stage(s) | Key contents |
|---|---|---|
| `faceless-produce` | all | init/resume, stage table, non-negotiables, checkpoints, hand-off |
| `faceless-script` | brief, script | brief schema, retention structure, writing for the ear, upload-mode "understand the narration" |
| `faceless-voice` | voice | ingest vs generate, provider choice, credit-saving rules, pronunciation, verification |
| `faceless-transcribe` | transcript | provider order, reading `script_match`, what's a real defect |
| `faceless-visuals` | visual_bible, beats, keyframes | bible, directing beats, host references, the binding law |
| `faceless-compose` | compose | what goes on screen, fonts, tweaks, pre-CP2 checklist |
| `faceless-package` | package | vidIQ tool flow, title/description/thumbnail rules |
| `faceless-review` | before CP1/CP2 | per-stage review checklist on pixels |
| `faceless-resume` | any | safe continuation in a new session |

## Using them

Claude Code and Codex pick skills automatically from the descriptions. You can also name one: "use faceless-visuals to redo the beats". `AGENTS.md` (read by Codex, and by Claude Code through `CLAUDE.md`) routes the first action of every session.

## Customising for your channel

- Put channel-wide taste (tone, banned words, visual style, recurring characters) in `channel.json` and your visual bibles, not in the skills — skills stay generic and upgradeable.
- For rules that are genuinely about process ("always add a map shot for a new location"), edit the relevant `skills/*/SKILL.md`, then `faceless skills sync`.
- To add your own skill: create `skills/<new-name>/SKILL.md` with frontmatter, sync, and mention it in `AGENTS.md` if it should be part of the routing.

## Writing a good skill

- Lead with the commands and the artifact it produces.
- State rules with the reason — the agent generalises from the why.
- Prefer concrete checks ("≤ 70 characters") over adjectives ("concise").
- Keep it under ~150 lines; move host- or provider-specific detail into `references/*.md` and link it.
