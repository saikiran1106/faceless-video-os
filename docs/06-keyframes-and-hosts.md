# 6. Keyframes & image hosts

## The visual bible

`05-visual-bible/visual_bible.json` is the contract every frame is generated against:

| Field | Purpose |
|---|---|
| `aspect` | `9:16` for shorts, `16:9` for long-form (gate-checked) |
| `style_contract` | the look, repeated in every prompt: medium, lighting, palette, lens, texture |
| `negative_contract` | what must never appear |
| `characters[]` | `character_id`, `name`, `prompt_contract` (face, age, build, hair, wardrobe, props), `reference_paths` |
| `locations[]` | `location_id`, `name`, `prompt_contract`, `reference_paths` |

Reference sheets: `faceless images jobs <p> --sheets` compiles one job per character (turnaround) and location (plate). Generate them on your host, then `faceless images apply-sheets <p>` prepends them to `reference_paths`. Reference images outrank words — a wrong reference beats a perfect prompt, so check sheets carefully.

## Directing beats

`faceless beats build <p>` gives measured beats. The agent fills, per beat:

`visual_objective` (what to show) · `shot_scale` · `camera {kind, intensity}` · `character_ids` · `location_id` · `mood` · `transition` · optional `overlay`.

Gates enforce: a direction on every beat, known ids, no hold longer than the profile max without `long_hold_reason`, and warn on monotonous framing or repeated camera moves.

## Image jobs

`faceless images jobs <p>` compiles `.faceless/image_jobs.json` — one job per beat with:
the full prompt (style + character/location contracts + the narration line + what to show + framing + mood + safe-area note + negatives), absolute reference paths, the aspect, and the `output_path` (`07-keyframes/images/KF###.png`). Don't edit it by hand; change the bible/beats and recompile.

## Hosts

| Host | How | Guide |
|---|---|---|
| `codex` | Codex's built-in image tool, one job at a time, then `faceless images record` | `skills/faceless-visuals/references/host-codex.md` |
| `claude-code` | `faceless browser generate` drives ChatGPT in a persistent signed-in Chromium | `.../host-claude-code.md` |
| `api` | `faceless images generate` calls OpenAI Images (edits endpoint when references exist) | `.../host-api.md` |
| `manual` | `faceless images prompts` → PROMPTS.md → any tool → `faceless images ingest` | `.../host-manual.md` |

### The Claude Code browser adapter

- Operates only the normal ChatGPT UI. It never exports cookies/tokens, never replays private endpoints, never solves CAPTCHAs; the human signs in once with `faceless browser setup`.
- Profile at `~/.faceless/browser-profiles/chatgpt-imagegen` (outside the repo, `0700`).
- One conversation per project (persisted), so the model keeps continuity. Optional `FACELESS_CHATGPT_PROJECT_URL` points it at a ChatGPT Project holding your channel context.
- Takes generated images from the page's own network responses (resilient to UI changes), ignores its own uploads by hash, and verifies decode + aspect.
- Durable job states (`queued → uploading → submitted → generating → downloaded → qa_pending → passed/failed`) in `.faceless/browser_jobs.json`; `resume` recovers a result from an in-flight job instead of resubmitting.
- Batch mode (`--batch N`) is faster but stages images **unbound** because ChatGPT reorders them; file each by looking.
- Diagnostics (sanitised screenshot + DOM excerpt) land in `~/.faceless/diagnostics/` on failure.

## Recording and QA

- `faceless images record <p> <KF|beat|SHEET-id> <file>` — decodes, fits the aspect (an image up to 20% off, e.g. a 2:3 portrait for a 9:16 job, is centre-cropped to exact; further off is rejected), saves PNG, keeps the previous file as `.prev.png`, writes a receipt (with `cropped_from` when cropped).
- `faceless images manifest <p>` — scans outputs; files a host wrote directly (browser adapter, a human) are recorded the same way; unchanged pixels keep their QA verdict, changed pixels reset to `pending`.
- `faceless review contact-sheet <p>` — every frame beside its line; look at it.
- `faceless images qa <p> <ids...|all> --pass|--fail --note "..."`.

## Binding law

One keyframe per beat, bound by id. Never recast a frame to a different beat; never bind by filename or arrival order. Regenerate the beat that's wrong.
