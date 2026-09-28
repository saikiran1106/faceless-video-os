# 7. Compose & render

## One composition for everything

`composer/src/StoryVideo.tsx` is a single Remotion composition. Its size, fps and length come from the props file (`calculateMetadata`), so no project ever needs its own React code.

```bash
faceless compose render <p> --platform youtube|instagram|tiktok [--engine remotion|ffmpeg] [--keep-props]
```
1. `compose.build_props` converts beats, keyframes, transcript and channel settings into frame-exact props → `08-compose/props_<platform>.json`.
2. Assets are staged into `08-compose/public/` and passed as `--public-dir`, so each render bundles only its own files.
3. `npx remotion render src/index.ts StoryVideo <out> --props=... --codec=h264 --crf=18`.

## Props contract

See `composer/src/types.ts` (TypeScript) — mirrored by `faceless/compose.py`:

| Key | Content |
|---|---|
| `fps`, `width`, `height`, `durationInFrames`, `narrationFrames` | from the format profile + narration length (+ end card) |
| `shots[]` | `src`, `from`, `durationInFrames`, `camera {kind, intensity}`, `transition`, `transitionFrames` |
| `captions` | `enabled`, `yPercent`, `fontSize`, `pages[{from,to,words[{text,from,to}]}]` |
| `overlays[]` | `text`, `style` (title, stat, lower_third, quote, label), `from`, `to` |
| `ctas[]` | `kind` (subscribe, comment, follow), `text`, `from`, `to` |
| `endCard` | `channelName`, `line`, `from`, `durationInFrames` |
| `narration`, `music` | staticFile paths; music `volume` |
| `theme` | `fontFamily`, `fontSrc`, `captionColor`, `highlightColor`, `accentColor` |

## Motion

Camera moves (`push_in`, `pull_out`, `pan_left/right/up/down`, `drift`, `static`) all ease out, so they settle like an operator rather than crawl like a slideshow. Pans are limited so the image edge never shows. Transitions: `crossfade` (the incoming image leads in so it's fully visible on its first word), `cut`, `dip_to_black`, `flash`.

## Captions

- Text = script spelling; timing = transcript. The active word is highlighted.
- Shorts: up to 3 words / 22 characters per page at 62% height (clear of the platform UI). Long-form: up to 6 words / 42 characters near the bottom. Change in `faceless/profiles/*.json`.
- Pages break at sentence ends and natural pauses, and stay up until the next page starts.
- `style.caption_case: "upper"` in `channel.json` for all-caps captions.
- Non-Latin scripts: set `style.font_file` to a font covering the script (e.g. `fonts/NotoSansTelugu-Bold.ttf`). The render waits for it to load.

## Overlays and CTAs

- Overlays come from `beat.overlay` in the beat manifest.
- CTAs come from `channel.json` `cta`: long-form gets a subscribe ask at ~35% and a comment ask at ~75%; shorts get the comment ask at ~75% (or `script.cta.end`). They are vertically centred.
- End card: channel name, your line, and a SUBSCRIBE (YouTube) or FOLLOW (Instagram/TikTok) button, for `cta.end_card_seconds` after the narration.

## Previewing and hand edits

```bash
faceless compose props <p> --platform youtube
cd composer && npx remotion studio src/index.ts --props=$(pwd)/../projects/<slug>/08-compose/props_youtube.json --public-dir=$(pwd)/../projects/<slug>/08-compose/public
faceless compose render <p> --platform youtube --keep-props
```

## ffmpeg fallback

`--engine ffmpeg` renders slow push-ins with hard cuts and the narration — **no captions, overlays, CTAs or end card**. Use it when Node isn't available, and tell the viewer-facing human it's a fallback.

## Verify

```bash
faceless review render-sheet <p> --platform youtube   # a frame from the middle of every beat
faceless compose report <p> --reviewed --notes "..."
```
The compose gate checks resolution, audio presence, that the render isn't shorter than the narration, and that someone reviewed it.
