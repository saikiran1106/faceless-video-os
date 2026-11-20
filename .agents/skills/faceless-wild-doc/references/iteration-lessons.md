# What 7 client iterations taught (and where each lesson lives in the code)

The style comes from one client long-form: an ~8-minute non-English narration of a prehistoric-wildlife survival story, built from
the creator's own recording. Each version answered a client note. These are now defaults, so a new film starts at v7.

| Ver | Client said / what happened | Lasting rule → where it lives |
|---|---|---|
| v1 | 30-min raw recording → 10-min film. Retakes cut to the last fluent take; 2.5D plates + stock + karaoke captions | the clock is the voice; anchors on words → `align.py`, `plan.py` |
| v2 | "follow my script"; footage must match the world (snow only) | script = text truth (spelling, chapter titles) → `align.py`; pick stock by eye per setting → skill step 4 |
| v3 | approved after QA replaced 5 near-black shots | QA without ears: transcribe the final mix vs the clean voice; blackdetect/freezedetect → `deliver.qa` |
| v4 | voice too slow; **no subtitles, no native-script text, English only**; **much faster cutting** (≤ 3-4 s); stock **and real fossil photos**; **heavy SFX on every text pop and transition**; music louder, **SFX louder than music** | `captions:false`; English cards → `Cards.tsx`; auto jump-cut > 3.3 s → `plan.py`; `R:` evidence cards; SFX per transition/overlay → `mix.py` |
| v4b | voice "sounds cartoon, too fast" (it had been time-stretched 1.12x and pitch-shifted) | **never time-stretch or pitch-shift the narrator** → `deliver.ingest_voice` uses it as-is |
| v5 | pauses-only edit: "a little slow", music "a little loud" | pace belongs to the creator's edit; music margin is a setting |
| v6 | tighter pauses (~149 wpm), 8:26; music 11.5 dB under the voice (never closer than 9.5) | `style.mix.music_margin_db = 11.5`, `music_min_db = 9.5` → `mix.py` |
| v7 | the client sent **their own edited voice** | use it as delivered; re-time by sequence diff, keep line slots → `faceless wild-doc voice` |

## Reliability lessons (the film was rendered on a laptop that flips bits when hot)
- Bake stock grades with ffmpeg: CSS filters/blend modes cost ~2 s/frame in software GL → `render.grade`.
- The night grade crushed already-dark clips to black: check per-segment luma (YAVG ≥ 20) → `grade` reports `too_dark`.
- Render with `--gl=swangle` (iGPU hangs), 2 workers, `nice`, ~60 s chunks, TMPDIR on disk → `render.render`.
- A seal is not enough: one chunk sealed "clean" with 1766/1767 frames. Check frame count + decode → `render.render`.
- Encode the master per chunk, verify each, then stream-copy concat; re-verify the sha before reusing a master → `render.assemble`.
- Fonts through `@remotion/google-fonts` (custom FontFace hung); never letter-space Devanagari.
- ChatGPT JSON-batch mode mis-binds images: one image per message, bound by id (`faceless gen images`).
- Never send an unapproved cut to the client; the creator watches first.
