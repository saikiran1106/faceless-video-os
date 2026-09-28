---
name: faceless-compose
description: Assemble and render a Faceless Video OS video - beat-synced keyframes with camera motion and transitions, word-highlighted captions, text overlays, CTAs, end card and optional music - with Remotion (or an ffmpeg fallback), for YouTube, Shorts, Instagram Reels or TikTok. Use for the compose stage, re-renders, caption/overlay placement fixes, or "render the video".
---

# Faceless Compose

One generic Remotion composition (`composer/src/StoryVideo.tsx`) renders every project from a props file. Python computes all frame numbers from the beats and word timings, so sync cannot drift.

## Render

```bash
faceless compose render <p> --platform youtube        # 16:9 long-form or 9:16 Shorts, per the project format
faceless compose render <p> --platform instagram      # same cut, "FOLLOW" end card
faceless review render-sheet <p> --platform youtube   # frames sampled at every beat midpoint
faceless compose report <p>                           # probes renders -> render_report.json
```
First time: `cd composer && npm install`. No Node? `--engine ffmpeg` renders a fallback (slow push-ins, hard cuts, **no captions/overlays**) — say so to the human.

## What goes on screen (and where it comes from)

| Element | Source | Notes |
|---|---|---|
| Shots | `06-beats` + `07-keyframes` | Each image appears exactly while its line is spoken; crossfades lead in so the image is fully visible on the first word |
| Camera | `beat.camera` | All moves decelerate (ease-out); `intensity` 0-1 |
| Captions | transcript timings + script spelling | Short: 3 words/page at 62% height; long-form: 6 words at the bottom. Active word highlighted |
| Overlays | `beat.overlay` | title / stat / lower_third / quote / label |
| CTAs | `channel.json` `cta` + `script.cta.end` | Vertically centred. Long-form subscribe ask at ~35%, comment ask at ~75% |
| End card | `channel.json` | Channel name + Subscribe (YouTube) / Follow (Instagram, TikTok) |
| Music | `08-compose/music.mp3` or `channel.music.default_track` | Constant bed at `music.volume` (default 0.12) with fades; keep it under the voice |

Non-Latin scripts (Telugu, Hindi, Arabic, Thai...): set `style.font_file` in `channel.json` to a TTF/OTF that covers the script (e.g. Noto Sans Telugu). System fallback fonts render these poorly.

## Hand tweaks

`faceless compose props <p> --platform youtube` writes `08-compose/props_youtube.json`. Edit it (overlay text, CTA timing, colours), then `faceless compose render <p> --platform youtube --keep-props`. Rebuilding props without `--keep-props` discards hand edits. Live preview: `cd composer && npx remotion studio src/index.ts --props=<abs path to props> --public-dir=<project>/08-compose/public`.

## Before CP2

1. Watch the render end to end with sound (or, if you cannot play video, inspect the render sheet frame by frame against the narration).
2. Check: every frame matches its line; captions never cover faces or platform UI; no black/placeholder frames; the end card is correct for the platform; audio does not clip.
3. `faceless compose report <p> --reviewed --notes "watched; ..."` then `faceless complete <p> compose` and present CP2 to the human with the render path and render sheet.
