# automation/

Battle-tested automation extracted from real production runs. Everything here is **de-branded and secret-free**; you bring your own accounts (signed in by hand, once) and your own keys.

| Folder | What it is | Docs |
|---|---|---|
| [`studio_os/`](studio_os) | Browser automation for AI generation: **login manager** for persistent Playwright profiles (`accounts`), **ChatGPT image adapter** with a resumable job store (`browser`), **Google Flow video adapter** with spend guards and API harvest (`flow`), and the **fast pipeline** (parallel storyboards, batch clips) (`fast`) | [learnings 1–3](../docs/learnings) |
| [`motion_studio/`](motion_studio) | Code-driven motion graphics: HTML `seek(t)` engine → variants → QA → delivery, with an example campaign and a neutral brand template | [README](motion_studio/README.md), [learnings 5](../docs/learnings/05-motion-studio-code-driven-video.md) |
| [`video_tools/`](video_tools) | Chunked guarded renders, verified assembly (frame-count + decode checks), stock grading, **Premiere Pro handoff exporter** (xmeml + EDL + CSV), `Fix_Paths.py` | [learnings 8–9](../docs/learnings) |
| [`tools/`](tools) | `media/media_guard.py` (seal/check media), `storage/r2.py` (R2/S3 upload + forced-download presign), `browser/` (keyframe binding, contact sheets, ASR verify), `capture/` (screen capture), `publishers/` (YouTube/Instagram Graph API) | [learnings 8, 10](../docs/learnings) |
| [`config/`](config) | `accounts.example.json`: copy to `accounts.json` (git-ignored) | – |

## Quick start

```bash
cd automation
pip install -r requirements.txt && python -m playwright install chromium
cp config/accounts.example.json config/accounts.json        # edit emails/profile dirs; no secrets belong here
python -m studio_os.cli accounts login images                # YOU sign in, in the window that opens; then close it
python -m studio_os.cli accounts doctor
python -m studio_os.cli flow doctor                          # read-only survey of the Flow UI; generates nothing
python tools/media/media_guard.py seal path/to/video.mp4     # sha256 + full decode check
```

## Rules baked into the code

- Nothing types credentials or reads cookies; profiles live outside git (0700).
- Every paid action is guarded (price equals expected, credit cap, never resubmit on timeout, dry-run first).
- Every long job is resumable and every media file can be sealed and re-verified.

Agent playbooks for all of this: [`skills/faceless-browser-logins`](../skills/faceless-browser-logins), `faceless-chatgpt-images`, `faceless-flow-video`, `faceless-motion-studio`, `faceless-media-integrity`, `faceless-premiere-handoff`, `faceless-delivery`.
