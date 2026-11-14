---
name: git-main-hygiene
description: Never merge stale branches into main; before committing, prove every local change is newer than main's version and restore unexplained deletions
metadata:
  type: feedback
  updated: 2026-10-01T10:02:16
---

the owner (2026-10-01): don't disturb main code; old code that is stale locally must not go to main.

**Why:** 10 old claude/cursor/codex branches (Jul-Sep) all conflict with current main; merging them would overwrite newer work. Unexplained local deletions (14 Navagunjara stills) would silently remove assets.

**How to apply:**
- Never merge an old branch into main unless the owner names it; dry run: git merge-tree --write-tree --name-only main <branch>.
- Before committing, compare each modified file's mtime with git log -1 --format=%ct -- <file>; a file edited before main last changed it is STALE and must not be committed.
- Restore deletions nobody can explain (git checkout -- <path>).
- Keep scratch dirs (tmp_*) out of git; secret-scan before every commit.
