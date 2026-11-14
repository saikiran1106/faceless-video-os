# 11. Operating rules for coding agents (Claude Code, Codex)

These rules came from real corrections. They apply to any video pipeline an agent runs.

## Money
- **Ask before every paid call** (TTS, speech-to-text, image generation, video generation, API inference). State provider, model, count, **minimum and worst-case cost**, then **stop and wait for a yes**.
  Include single-chunk re-rolls and "cheap" verification calls. Batch the ask for a whole stage; drip-feeding approvals is how a run reaches 3–4× its budget.
- Prefer free/local work where it substitutes (forced alignment of a known script instead of paid transcription for timing).
- Never raise a budget or cap yourself; halt after unit 1 of any new paid setup; never resubmit after a timeout.

## Scope and honesty
- **Do only what was asked.** No bundled "improvements"; propose them separately.
- **Paste the gate's actual RESULT line** before claiming a pass. A gate that cannot resolve its inputs can pass silently; make gates resolve every root a project can live in.
- **Read every project artifact before a long run** (recipes, consistency notes, voice manifests); diff any docs against the knowledge base before trusting them.
- **Fix at the source, not by splicing.** Corrections go into the build plan/timeline source *and* the final file; grep the compose script for a removed shot id before saying "done"; keep backups of replaced exports.
- **Source-led writing:** no invented plot or facts; tag each line as source / paraphrase / dialogue / flavour; research characters, costumes, props, locations before any image; check period accuracy of every prompt.
- Say what you verified and what you could not (e.g. "audio was measured, not heard"; "XML validated by script, not opened in Premiere").
- When a creator says an artifact is wrong ("very bad", "cartoon", "slideshow"), find the *mechanism* (what the pipeline did) and change that, rather than tweaking surface settings.

## Process
- **Script first:** approval of the script (CP1) precedes any paid media; final cut (CP2) precedes publishing. Hash-bind approvals to the artifact they approved.
- **One-sentence story spine** (protagonist + escalation + withheld reveal) before writing; a chain of causes is not a spine. One promise across title, thumbnail, first 25 s.
- **Reference first:** when the creator names a reference, study it before composing; when they supply a recording or an edit, use it as-is.
- **Version everything:** `plan_v*_delivered.json`, the voice master per version, a feedback ledger of approvals/rejections with the reason, and promote repeated lessons into rules.
- **Resumability:** every external step has a durable job store (queued → submitted → generating → downloaded → reviewed). A crash must never re-buy a unit.
- Write handoff notes (`HANDOFF.md`) with paths, state, spend, gotchas and next steps so a fresh session can continue.

## Environment
- Keep multi-GB scratch off a tmpfs `/tmp`; keep browser profiles and `.env` outside git; confirm `git` is on `main` and clean before committing; never `--force` unasked.
- Long jobs: run in the background with a log; wait on a PID/output file; one heavy render at a time.
- Unattended agent sessions (started at boot by a timer/watchdog) can come up **signed out** because the stored login credential expired. Have the startup script run `claude auth status`, report a blocked state with a non-zero exit instead of looping, and relaunch only the signed-out pane after the human completes the native sign-in; never copy tokens around.

## Memory / learning loop
Capture approvals, rejections, corrections and post-publication analytics immediately as one-line notes; promote repeats to lessons; sync lessons into skills. Keep memory **about the work** (what worked, what was rejected and why), not secrets.
See [`12-universal-lessons-digest.md`](12-universal-lessons-digest.md).
