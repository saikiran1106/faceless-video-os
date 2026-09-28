---
name: faceless-visuals
description: Build the look of a Faceless Video OS video - visual bible (style, characters, locations, reference sheets), directed beats (what each narration slot must show, shot scale, camera move, overlays), and one keyframe image per beat generated on the current host (Codex built-in image tool, ChatGPT via Playwright browser in Claude Code, OpenAI Images API, or manual). Use for the visual_bible, beats and keyframes stages, and for any keyframe regeneration or image-prompt work.
---

# Faceless Visuals

Three stages, in order: **visual bible → beats → keyframes**.

## 1. Visual bible (`05-visual-bible/visual_bible.json`)

```json
{
  "version": "1.0",
  "aspect": "9:16",
  "style_contract": "Painterly cinematic realism, warm low-key light, film grain, muted teal-and-amber palette, 35mm lens look",
  "negative_contract": "cartoon, 3D render look, text, watermark, extra fingers, modern objects",
  "characters": [
    {"character_id": "captain", "name": "Captain Smith", "prompt_contract": "white-bearded man, 60s, stern blue eyes, navy double-breasted captain's uniform with gold buttons, white cap", "reference_paths": []}
  ],
  "locations": [
    {"location_id": "bridge", "name": "Ship's bridge at night", "prompt_contract": "wood-panelled bridge, brass telegraphs, fogged windows, lamp glow", "reference_paths": []}
  ]
}
```

- `aspect` must match the format (short 9:16, long-form 16:9).
- **Research canonical looks before writing contracts.** Real people, historical periods, mythology and brand characters have a correct appearance (dress, ornaments, colours, props, era). Write it down concretely; vague contracts drift frame to frame.
- Optional reference sheets (strongly recommended for recurring characters):
  `faceless images jobs <p> --sheets` → generate them on your host → `faceless images apply-sheets <p>` adds them to `reference_paths`.
- **A reference image outranks any prompt wording.** A wrong sheet attached to a frame beats every correct word. If one generated frame nails a character, crop it and use that as the reference.

## 2. Beats (`06-beats/beat_manifest.json`)

`faceless beats build <p>` measures beats from word timings (sentence ends → clause pauses → word count; short ≈ 3s, long-form ≈ 5s). Timings are measured — **never edit `start_s`/`end_s` by feel.** Then DIRECT every beat:

- `visual_objective` — what the viewer must SEE while this line is spoken. Concrete, literal, one moment. Match the emotion of THIS line, not the next one.
- `shot_scale` — `extreme_wide|wide|medium|close|extreme_close|insert|overhead`. Vary it: > 60% of one scale reads as "static imagery" even with fast cuts. Use a ladder: establish wide → medium → close on emotion → insert on the key object.
- `camera.kind` — `push_in` (tension, reveal), `pull_out` (isolation, aftermath), `pan_left/right` (journey, scanning), `pan_up/down` (scale, descent), `drift` (calm, dreamy), `static` (shock beat). Don't repeat one move 3+ times in a row. `intensity` 0-1.
- `character_ids`, `location_id` — must exist in the bible. Leave `character_ids` empty for empty places (don't attach character refs to a shot with nobody in it).
- `transition` — `crossfade` default, `cut` for shocks, `dip_to_black` for time jumps, `flash` for reveals.
- `overlay` (optional) — `{"text": "1912", "style": "label|title|stat|lower_third|quote"}`. Put reveals/numbers near ~35% and ~75% of the runtime where retention recovers; keep the first 10% clean and fast.

Complete the stage; the gate checks coverage, gaps, holds, unknown ids and framing variety.

## 3. Keyframes (`07-keyframes/`)

```bash
faceless images jobs <p>          # compile one job per beat -> .faceless/image_jobs.json
```
Never hand-edit `image_jobs.json`; change the beat/bible and recompile.

Generate on your host — read the matching reference:
- Codex → [references/host-codex.md](references/host-codex.md)
- Claude Code (ChatGPT in a browser) → [references/host-claude-code.md](references/host-claude-code.md)
- OpenAI Images API → [references/host-api.md](references/host-api.md)
- Anything else (Midjourney, Gemini, Leonardo, a designer) → [references/host-manual.md](references/host-manual.md)

Then:
```bash
faceless images manifest <p>        # scans the files on disk
faceless review contact-sheet <p>   # LOOK at every frame beside its line
faceless images qa <p> KF001 KF002 --pass
faceless images qa <p> KF007 --fail --note "wrong era uniform"
faceless complete <p> keyframes
```

## The binding law (why videos go wrong)

1. One keyframe per beat; `KF007` belongs to `B007` forever.
2. **Never recast** a good-looking frame onto another beat to avoid a regeneration. Regenerate the failing beat.
3. **Bind by content, never by filename or order.** A bulk download has no frame identity, and batched generations come back out of order (measured: 0 of 9 in the requested slot). If you batch, you must identify each image by looking.
4. One reference set governs every frame in a batch — only batch frames that share characters/location.
5. Content-policy refusals trigger on the RENDERED picture, not the prompt. Adding "no nudity/violence" does nothing; specify garments, crop tighter, separate limbs, imply action instead of showing impact, and keep minors out of any peril frame.
6. Max 2 creative attempts per frame, then rewrite the prompt (usually the visual_objective) instead of re-rolling.
