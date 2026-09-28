---
name: faceless-resume
description: Resume an existing Faceless Video OS video project safely in a new Claude Code or Codex session - load its run state, approvals, locks, spend and pending image jobs, and continue from the current stage without redoing or re-buying finished work. Use when the user says continue, resume, where were we, what's next, or opens an existing project.
---

# Faceless Resume

1. Find the project: `ls projects/` (or the path the user gives).
2. `faceless next <p>` — current stage, status, the skill to read, and exact commands.
3. `faceless status <p>` — approvals, locks, budget spent vs approved, provider operations already paid for.
4. Check in-flight work before generating anything:
   - Voice: `03-voice/chunks/index.json` — existing chunks are reused automatically.
   - Images: `faceless browser status --project <p>` (Claude Code host) and `ls 07-keyframes/images/` — existing frames are skipped; `faceless browser resume --project <p>` recovers a crashed run without re-submitting.
5. If the status is `failed`, read `critical_findings` from `faceless next` and fix those first.
6. If the status is `awaiting_human`, do nothing except present the artifact and ask for the decision.
7. Continue the loop from `faceless-produce`.

Trust files over memory: if your notes disagree with `.faceless/run.json` or the artifacts, the files win.
Never delete a project's images, audio or chunks to "start clean" — they are paid-for work.
