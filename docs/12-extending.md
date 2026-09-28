# 12. Extending

## Add a TTS provider

`faceless/providers/tts.py` — a class with `name`, `max_chars`, `estimate_usd(chars)` and `synthesize(text, dest, previous_text="", next_text="") -> Path`. Register it in `select_tts()` and add it to `--provider` choices in `faceless/cli.py`. Chunking, caching, budget and concatenation are handled for you in `faceless/voice.py`.

## Add a transcription provider

`faceless/providers/transcribe.py` — a function returning `{"provider", "model", "language", "text", "words": [{"text", "start", "end"}]}`. Add it to `transcribe()`, `select_transcriber()`, `estimate_usd()` and `available_providers()` in `providers/__init__.py`.

## Add an image API

`faceless/providers/images.py` — a class with `estimate_usd(count)` and `generate(prompt, aspect, dest, reference_paths)`. Wire it into `imagejobs.generate_api` (e.g. behind a `--provider` flag). Images are always filed through `imagejobs.record`, which enforces decode + aspect and writes receipts.

## Add an image host

A host is just a way of turning `.faceless/image_jobs.json` into files at each job's `output_path`. Write a `skills/faceless-visuals/references/host-<name>.md` guide, add the name to `HOSTS` in `faceless/stages.py`, and have the host call `faceless images record` per image.

## Add an overlay style

1. Add the name to the `overlay.style` enum in `faceless/schemas/beats.schema.json` and to `OverlayStyle` in `composer/src/types.ts`.
2. Add a `case` in `composer/src/components/Overlays.tsx`.
3. Mention it in `skills/faceless-visuals/SKILL.md` so the agent uses it.

## Add a camera move or transition

Enum in `beats.schema.json` + `types.ts`, then `cameraTransform()` or the transition logic in `composer/src/components/ShotLayer.tsx`, and `TRANSITION_FRAMES` in `faceless/compose.py` for transitions.

## Add or change a gate rule

`faceless/gates.py`: append a `_crit(...)` or `_warn(...)` finding in the stage's `check_*` function with a new `FF-*` id, a message and a fix. Add a test in `tests/test_gates.py`. Regenerate the table in `docs/13-quality-gates.md`.

## Add a format

Create `faceless/profiles/<name>.json` (copy `short.json`), add the name to `FORMATS` in `faceless/stages.py` and the `format` enum in `brief.schema.json`. Everything else reads the profile.

## Tests

```bash
make test        # pytest + TypeScript typecheck of the composer
```
`tests/test_demo.py` runs every stage up to compose offline; keep it green.
