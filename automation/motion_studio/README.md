# Motion Studio

A motion system for tech content: AI news, tool demos, explainers and launch clips. One campaign
brief goes in. Out comes every hook × format × CTA combination as a finished, QA-checked MP4, with download
links. It's built on HyperFrames (HTML rendered to video) and modelled on @e1genqq's "automated motion design
system" article and @twoclipping's seek(t) prompt.

Use it for explainers, news, tool demos and launch clips. Footage-led reels made from generated video clips use the fast pipeline in `automation/studio_os` instead; stills-based reels use the keyframe-parallax approach.

```
 brief + sources ──> campaign.json ──validate──> build ──> HyperFrames project per variant
   (claims quoted)        │            (numbers must      (layout per format,    │
                          │             trace to quotes)   sounds on the frame)   │
                   make_campaign.py                                   check · snapshot · look
                   (VO word times = clock)                                        │
                                                    render (motion blur) ──> qa ──> REVIEW.md ──> deliver (R2 links)
```

One command drives every stage. Run it from the repo root with the repo venv, which has numpy, Pillow and
boto3:

```bash
venv/bin/python motion-studio/tools/studio.py <stage> ...
```

## End to end

| # | Stage | Command | What you get / check |
|---|---|---|---|
| 0 | Set up the machine | `studio.py doctor`, then `studio.py assets pull` | deps, node ≥ 20, ffmpeg, the 12 engine sounds and campaign media pulled from R2 and verified by sha256 |
| 1 | New campaign | `studio.py new <id> --title "..."` | `campaigns/<id>/` with `campaign.json` (copied from seek-t), `sources/notes.md`, a `PLAN.md` table to fill |
| 2 | Sources + claims | edit `sources/notes.md` and `claims` | every number on screen must sit in a claim whose quote is found word for word in the source file |
| 3 | Plan | fill `PLAN.md` | beat grid: what the hero shape becomes in each scene, cursor, camera, sound. Show it to the owner before building |
| 4 | Validate | `studio.py validate <id>` | rejects unsourced numbers, lines too wide for the frame, more than ~5–8 words a line, items outside their scene |
| 5 | Build one | `studio.py build <id> --hooks A --formats 9:16 --ctas A` | `campaigns/<id>/build/<variant>/index.html` |
| 6 | Look | `studio.py check <id>` and `studio.py snapshot <id> --variant <vid> --at 0.5,4,8` | HyperFrames lint/registry check; PNGs at every scene and seam. Fix and repeat 5–6 |
| 7 | Build all | `studio.py build <id>` | 3 hooks × 3 formats × 2 CTAs = 18 variants by default |
| 8 | Render + QA | `studio.py render <id>` (2 workers) | `exports/<variant>.mp4` (~75 s per 32 s variant), `qa/<variant>/`: contact sheet, 5 frames around every seam, phone-size sheet, LUFS/peak/duration, `REVIEW.md` |
| 9 | Review | read `qa/*/seams.jpg` and the hero contact sheet; fill `REVIEW.md` | tick `- [x] Approved for delivery by:`. Say the audio was measured, not heard |
| 10 | Status | `studio.py status <id>` | built / rendered / QA / approved / delivered, per variant |
| 11 | Deliver | `studio.py deliver <id> --hero <vid> [--extra thumb.png caption.txt]` | uploads to R2 `motion-studio/<id>/`, a zip of all, 7-day download links (forced attachment, works on a phone) |
| 12 | Post | post from your social profile (see `docs/learnings/01-browser-automation-and-logins.md`) | caption: keywords in line 1, at most 5 hashtags |

New media (footage, a voice take, a music bed) → `studio.py assets lock`, then `studio.py assets push`, so
the next machine can rebuild the campaign.

## Two ways to write a campaign

- **Beat-grid campaign** (`campaigns/seek-t`, "This video is code"). The campaign is written by hand on a
  120 BPM grid (one beat = 0.5 s, so a 120 BPM track drops straight in). It has 3 hooks, 3 formats and
  2 CTAs, making 18 MP4s of 32 s each.
- **Voiceover-as-clock campaign** (`campaigns/genie-4`, "Genie 4: worlds generated live"). `make_campaign.py`
  reads the ElevenLabs Scribe word times of the chosen VO take. It gives every sentence end at least 0.45 s
  of air and places scenes, punch-ins, karaoke captions and sounds on the spoken words. It then writes
  `campaign.json` with bpm 60, so one beat = one second. Real footage plays inside the hero shape, and the
  music bed sits 12–14 dB under the voice. Re-run it after any change to the take:
  `venv/bin/python motion-studio/campaigns/genie-4/make_campaign.py`.

## Layout

| Path | Job |
|---|---|
| `brand/brand.json`, `brand/logo.svg`, `brand/mark.svg` | Your brand colours (near-black `#0A0A0B`, orange `#FF7F00`, white), Inter + JetBrains Mono, your logo and mark (a neutral placeholder is included; replace it with your own) |
| `engine/runtime.js` | `render(t)`: a pure function of time. Closed-form springs; one hero shape that morphs through every scene with its edges on separate springs (the leading edge moves first); word-by-word blur entrances; typing code; a scrubber driven by a real cursor drag; number rolls; footage windows (karaoke captions are text items that `make_campaign.py` places on word times) |
| `engine/style.css` | the look: near-black grid ground, white Inter, one orange accent, JetBrains Mono for code |
| `engine/sfx/` | Pixabay UI sounds (12; see `CREDITS.md`). Media, so they're in R2, not git |
| `tools/studio.py` | the stage runner above |
| `tools/validate.py` | campaign gate: assets, claims ↔ quotes, line widths per format, scene bounds |
| `tools/build.py` | campaign → `build/<variant>/index.html`. Times are beats; positions are fractions of each format's safe band; 16:9 splits into a caption column and a stage column instead of cropping. Item kinds: `text`, `code`, `count`, `scrub`, `nodes`, `tabs`, `frames`, `logo`, `footage`, `keys`, `chip`, `wave`. Any key can be overridden per format with `key@16:9` |
| `tools/render.py` | renders every built variant (HyperFrames 0.8.210, delivery quality, motion blur on, hero off), runs QA, writes `exports/delivery_manifest.json` (hashes, settings, QA result) |
| `tools/qa.py` | the per-variant QA pack and `REVIEW.md` with a human-approval line |
| `tools/deliver.py` | R2 upload + links, through the repo's `tools/storage/r2.py` |
| `tools/assets.py` | `assets.lock.json` (sha256 + bytes of every media input) and push/pull/status against R2 `motion-studio/` |
| `campaigns/<id>/` | `campaign.json`, `sources/notes.md`, `PLAN.md`, `qa/*/REVIEW.md`, `exports/delivery_manifest.json` and the caption are in git. `footage/`, `audio/` media, `build/`, renders and QA images are not |

## Rules the engine follows

- Every visible property is computed from `t`: no timers, CSS transitions, randomness or state carried
  over from earlier frames. `tests/motion` enforces this.
- A value that changes target many times is `initial + Σ change × spring(t − changeTime)`.
- Words leave before new words arrive. Boxes sit under the hero, words over it.
- Each sound's measured peak lands one frame after its picture event.
- Banned: gradients on UI, glows, particle bursts, bouncy UI easing, synthesised tones.
- Numbers on screen come only from quoted sources (validate.py).

## Gotchas already hit

- HyperFrames scene clips are stacking contexts, so boxes go in the `under` layer and words in the `over`
  layer. build.py does this.
- Render-time motion blur composites moving elements on top, so `#hero` has `data-motion-blur="off"`;
  otherwise it hides the labels on it.
- The runtime must be inline in index.html, or `check` reports `missing_timeline_registry`.
- `#root` needs an explicit px size (`--W`/`--H`).
- Text containers start at opacity 0; drawText makes the box visible and animates the words.
- Render with 2 workers on a laptop: 4 ran out of memory.
- One heavy render at a time. Hot renders flip bits on unstable hardware, so check exports with
  `tools/media/media_guard.py` before delivering.
- Voice: your own consented voice (never clone anyone without consent), about 160 wpm, at least 0.45 s at
  sentence ends. CTA: "follow for more AI news" on a clean profile card.
- Music: your own track, or ElevenLabs Music (instrumental). Ask before any paid generation.
