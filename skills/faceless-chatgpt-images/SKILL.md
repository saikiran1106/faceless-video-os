---
name: faceless-chatgpt-images
description: Generate keyframes, character sheets, covers and thumbnails by driving ChatGPT image generation through a Playwright browser (resumable job store, parallel tabs, API-read completion, JSON batch) when the host has no built-in image tool or hits plan limits. Use for visual-bible sheets, one-image-per-beat keyframes, regenerating a single beat, or bulk image jobs.
---

# Faceless ChatGPT Images

Read `docs/learnings/02-chatgpt-image-generation.md`. Code: `automation/studio_os/browser` (jobs, runner) and `automation/studio_os/fast` (parallel tabs).

## Procedure
1. `accounts doctor` for the image profile (see `faceless-browser-logins`). Set `FACELESS_CHATGPT_PROJECT_URL` to your ChatGPT *Project*.
2. Compile the image jobs (one beat = one job, prompt carries a plan tag with the beat id).
3. References/sheets first (human approves) → `python -m studio_os.cli fast storyboards --project P --queue Q --workers 2..3` → contact sheet → human approves → continue.
4. Bind results to beats **by content** (`automation/tools/browser/bind_keyframes.py`, `contact_sheet.py`); regenerate a beat rather than recasting a frame.

## Hard rules
- Run inside the Project, never a loose chat. **One image per message.** Never position-bind a batch.
- JSON-batch mode mis-binds on duplicate ids: eyeball every image vs its prompt.
- Fresh chat per **character** sheet (faces converge otherwise). Attach the right references; attachments apply to the whole batch.
- Rebuild derived queues after any plan change. Never resubmit on timeout (look for the image first). No paid fallback without approval and a min/worst-case cost.
- A guardrail reject is about the rendered pixels: re-stage the scene (garment, crop, camera), do not add negations; never put minors in force scenes; note what tripped.
- Keep the top 30 % and a lower-middle band clear for text; thumbnail text centred.
