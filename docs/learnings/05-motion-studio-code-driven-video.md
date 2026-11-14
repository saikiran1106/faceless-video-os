# 5. Motion Studio: code-driven motion graphics

Code: [`automation/motion_studio`](../../automation/motion_studio) (README there is the runbook). A video is **HTML whose every pixel is a pure
function of time `t`** (`seek(t)`), rendered frame by frame; the same cue list that places visuals also places the sounds.

## Why it works

- **The voice take is the clock.** Every scene, cue, shake and flash is keyed to a *spoken word*; change the voice, re-time, done.
- One brief → every **hook × format × CTA** variant (3 × 3 × 2 = 18 MP4s by default), each QA'd (contact sheet, 5 frames around every seam, phone-size sheet,
  LUFS/peak/duration, `REVIEW.md`).
- **Numbers on screen must come from quoted sources.** `validate.py` rejects an on-screen figure unless a claim's quote is found word for word in the source file.
- Stages never spend money; only `deliver` uploads (to your R2 bucket) and prints 7-day forced-download links.
- Media inputs (SFX, footage, music) live in object storage pinned by `assets.lock.json` (sha256 + bytes) so any machine can rebuild a campaign.

## Lessons

1. **Original motion graphics beat scraped footage.** A reel assembled from screen captures and internet footage turned into pans was rejected as "odd, AI-slop".
   Tell the story with drawn scenes, icons, type and diagrams, with SFX landing on picture events; credit the source in small text, never show its page.
2. **Mix:** engine impact-bass sounds are ~2 s of loud bass; fifteen of them drowned the voice until cut to a short hit. Keep the effects bus ~5 dB under the voice and the
   music bed 12–14 dB under it.
3. **Render with 2 workers** (4 ran out of memory). If the HyperFrames renderer crashes in its lint worker for a directory, **capture `window.__render(t)` with Playwright and pipe
   frames to x264** — same pixels, no renderer dependency.
4. **Voice pace for tech explainers:** ~160 wpm with ≥ 0.45 s at sentence ends reads better than the 185–210 wpm first tried; karaoke captions (the spoken word lit) and a keyword CTA.
5. One accent colour, no gradients on UI, no glows, no particle bursts, no bouncy easing on UI.
6. Plain text overlays read as "boring": every beat needs a visual event (shape morph, cursor, camera move) plus a sound.
7. Use the loudness/peak you measure; say "measured, not heard" when you cannot listen.

## Related

- `faceless-motion-studio` skill; HyperFrames (HTML → video) and Remotion are the two renderers used across this repo.
- A cover/thumbnail: text centred vertically **and** horizontally so the profile-grid crop and the feed crop both show it.
