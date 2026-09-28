---
name: faceless-package
description: Create the publishing package for a Faceless Video OS video - title, description, tags, hashtags, chapters, captions file, pinned comment and thumbnail - using the vidIQ MCP tools when they are connected (keyword research, title generation and scoring, thumbnail scoring) and built-in packaging rules when they are not. Use for the package stage, "write the title/description", "make a thumbnail", or YouTube SEO for a finished video.
---

# Faceless Package

```bash
faceless package draft <p>     # chapters from script sections, 09-package/captions.srt, skeleton JSON with TODOs
```
Fill every `TODO` in `09-package/publishing_package.json`, then `faceless complete <p> package`.

## Is vidIQ connected?

Check your available tools for names starting with `vidiq_` (in Claude Code they appear as `mcp__…__vidiq_*`; search for "vidiq" if tools are deferred). If present, set `"vidiq_used": true` and use:

1. `vidiq_keyword_research` on the topic → pick a `primary_keyword` with real volume and beatable competition; store the rows in `keyword_research`.
2. `vidiq_outliers` / `vidiq_similar_videos` → what titles and thumbnails are over-performing in this niche right now.
3. `vidiq_generate_titles` → candidates; `vidiq_score_title` → score yours and theirs. Keep the top 3-5 in `title_candidates[{title, score, source}]`.
4. `vidiq_score_thumbnail` (after the thumbnail exists) → iterate once if the score is weak.
Never call vidIQ tools that change a live video (`vidiq_update_video`, `vidiq_video_upload`, thumbnail updates) without explicit instruction.

No vidIQ? Apply the rules below yourself and say "packaged with built-in rules (vidIQ not connected)".

## Rules

**Title**
- ≤ 70 characters (hard limit 100). The stake + the question: what's at risk, and why it matters.
- A curiosity gap the video actually pays off. No clickbait the payoff can't honour.
- Put the primary keyword naturally inside one clean sentence; don't pipe-stack keywords.
- Shorts: a punchy hook line; `#shorts` goes in the description.

**Description**
- First 150 characters: restate the promise with the primary keyword — this shows in search and under the video.
- Then 2-4 lines of context, chapters (long-form), a comment question, and 3-5 hashtags (never > 15: YouTube then ignores all).
- Tags: primary keyword, 2-3 variants, the topic, the series name. ≤ 500 characters total.

**Chapters (long-form)**: from `package draft`; first at 0:00, ≥ 3, ≥ 10s apart. Rename them as hooks, not labels.

**Thumbnail**
- Generate it with the same image host as the keyframes (it must fit the video's style), 1280×720, < 2 MB.
- One face or one subject, big and emotional, high contrast; 2-4 words of text max, and the text must be part of the generated image (ask the image model to render it). Don't composite text in code.
- Use a device: a contradiction, a withheld identity, or a counted stake ("3 ships", "1 mistake").
- The title and thumbnail should say different things that add up to the curiosity gap.
- Save as `09-package/thumbnail.png` and set `youtube.thumbnail_path`.

**Pinned comment**: the question from the script's CTA.

Packaging buys the click; retention in the first 30 seconds decides whether the platform keeps showing it. If early retention was weak on past videos, fix the hook next time — not the tags.
