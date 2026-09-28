# 8. Packaging & vidIQ

```bash
faceless package draft <p>
```
Creates `09-package/publishing_package.json` with:
- `youtube.title` (from the brief), a description starting with the hook, default tags/hashtags from `channel.json`, `pinned_comment` from the script CTA;
- `youtube.chapters` for long-form, computed from the script sections' real start times (≥ 3 chapters, first at 0:00, ≥ 10s apart — otherwise none);
- `09-package/captions.srt` (upload it as subtitles — it helps accessibility and search);
- `shorts` and `instagram` blocks for short-form;
- `TODO`s the agent must fill — the gate refuses the stage while any remain.

## With vidIQ

If your agent has the vidIQ MCP server connected (tools named `vidiq_*`), the `faceless-package` skill uses:

| Tool | For |
|---|---|
| `vidiq_keyword_research` | the primary keyword (volume vs competition) |
| `vidiq_outliers`, `vidiq_similar_videos` | what's over-performing in the niche now |
| `vidiq_generate_titles`, `vidiq_score_title` | title candidates and scores → `title_candidates` |
| `vidiq_score_thumbnail` | thumbnail check after generation |

It sets `vidiq_used: true`. Tools that modify a live channel (`vidiq_update_video`, `vidiq_video_upload`, thumbnail updates) are never called without an explicit instruction.

Connect vidIQ: add its MCP server in your agent's MCP settings (Claude: Settings → Connectors; Codex: `~/.codex/config.toml` `[mcp_servers]`). Without it the skill applies the built-in rules below.

## Built-in rules (what the gate and skill enforce)

| Item | Rule |
|---|---|
| Title | ≤ 100 chars (hard), ≤ 70 recommended; the stake + a question the video answers; keyword inside one clean sentence |
| Description | first 150 chars carry the promise + keyword; then context, chapters, a comment question |
| Hashtags | 3–5 (more than 15 makes YouTube ignore all) |
| Tags | ≤ 500 characters total |
| Chapters | first 0:00, ≥ 3, ≥ 10s apart |
| Thumbnail | 1280×720, < 2 MB, one big subject, 2–4 words rendered by the image model, a curiosity device (contradiction / withheld identity / counted stake) |

## Thumbnail

Generate it on the same image host as the keyframes so it matches the video's look. Ask the model to render the text inside the image. Save to `09-package/thumbnail.png` and set `youtube.thumbnail_path`.

## Publishing

Faceless Forge does not upload. Upload the render from `08-compose/renders/`, paste the package fields, attach `captions.srt` and the thumbnail.
