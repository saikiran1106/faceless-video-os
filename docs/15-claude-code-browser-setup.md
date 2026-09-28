# 15. Claude Code browser setup (ChatGPT image generation)

Claude Code has no image model of its own. Faceless Video OS gives it one by driving the ChatGPT web app in a real, persistent Chromium browser with Playwright — using **your** ChatGPT subscription, so there is no per-image API bill.

Codex users don't need this (Codex has a built-in image tool). API users can use `--host api` instead.

## How it works

```
image_jobs.json ──▶ faceless browser generate ──▶ Chromium (your signed-in ChatGPT profile)
                                                   │  attach reference images
                                                   │  type the job's prompt, send once
                                                   │  watch the page's own network responses for the new image
                                                   ▼
                     07-keyframes/images/KF###.png + receipt + durable job state
```

- **Normal UI only.** It clicks and types like a person. It never reads or exports cookies/tokens, never calls private endpoints, never solves CAPTCHAs or bot checks, and never bypasses rate limits.
- **One conversation per video.** The chat URL is saved, so every frame for a project lands in the same conversation and the model keeps characters and style consistent.
- **Crash-safe.** Each job moves through `queued → uploading → submitted → generating → downloaded → qa_pending → passed/failed`, saved atomically to `.faceless/browser_jobs.json`. A job is never submitted twice; `resume` recovers a finished image instead of paying for it again.
- **Resilient to UI changes.** Controls are found through an ordered list of strategies (ARIA role → label → test id → CSS). Results come from network responses, not page markup.

## 1. Install

The installer already did this. To (re)install just this part:
```bash
.venv/bin/pip install -e ".[browser]"
.venv/bin/playwright install chromium          # Linux: sudo .venv/bin/playwright install-deps chromium first
```

## 2. Sign in once (you do this, not the agent)

```bash
faceless browser setup
```
A Chromium window opens on chatgpt.com. Log in yourself, completing any email code, MFA or "verify you are human" check. When you can see the chat box, you're done — close the window (or wait; it reports `signed_in: true`).

The login is stored in a dedicated profile at `~/.faceless/browser-profiles/chatgpt-imagegen` (owner-only permissions, outside the repo, never committed). Your normal Chrome is not touched.

Already have a signed-in Playwright profile elsewhere? Point at it: `FACELESS_BROWSER_PROFILE=/path/to/profile` in `.env`.

## 3. Health check (free)

```bash
faceless browser doctor
```
Opens ChatGPT, confirms you're signed in, locates the message box, send button and image-upload input, and types then clears a probe string — **nothing is ever sent**. Expect:
```json
"reachable": true, "signed_in": true,
"composer_strategy": "...", "send_button_strategy": "...", "file_input_strategy": "...",
"passed": true
```

## 4. (Optional) Use a ChatGPT Project

A ChatGPT Project keeps instructions and files (your style guide, character sheets) available to every chat inside it, which keeps frames on-model across episodes.
1. In ChatGPT create a Project (e.g. "My Channel images") and add your style notes.
2. Copy its URL (`https://chatgpt.com/g/g-p-…/project`) into `.env`:
   ```
   FACELESS_CHATGPT_PROJECT_URL=https://chatgpt.com/g/g-p-XXXX/project
   ```
New videos then start their conversation inside that Project.

## 5. Generate keyframes

```bash
faceless init my-video ... --host claude-code
# ... brief → script → voice → transcript → visual bible → beats (see Workflows)
faceless images jobs my-video --sheets              # optional: character/location reference sheets first
faceless browser generate --project my-video --sheets
faceless images apply-sheets my-video
faceless images jobs my-video
faceless browser generate --project my-video --limit 1   # do ONE, look at it
faceless browser generate --project my-video             # then the rest (already-done frames are skipped)
faceless images manifest my-video
faceless review contact-sheet my-video
```

| Command | Use |
|---|---|
| `faceless browser status --project P` | counts per state, the conversation URL |
| `faceless browser resume --project P` | after a crash, timeout or closed window — recovers finished images, never double-submits |
| `faceless browser generate --project P --only KF007 KF012` | just these frames |
| `faceless browser generate --project P --new-conversation` | start a fresh chat (keeps finished frames) |
| `faceless browser generate --project P --batch 4` | several prompts per message — faster, see below |

### Batch mode — read this before using it

`--batch N` sends N numbered prompts in one message. It's much faster, but ChatGPT **returns batch images out of order** and sometimes returns fewer than asked. So batched images are saved **unbound** to `07-keyframes/_staging/batchNN_slotNN.png`. You (or the agent) must open each one, decide which beat it shows, and file it:
```bash
faceless images record my-video KF012 07-keyframes/_staging/batch01_slot03.png
```
Use batches for reference sheets (easy to tell apart) or runs of beats that share one location and cast. For story keyframes, one-per-message is the safe default.

## Settings (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `FACELESS_BROWSER_PROFILE` | `~/.faceless/browser-profiles/chatgpt-imagegen` | profile directory |
| `FACELESS_CHATGPT_PROJECT_URL` | empty | ChatGPT Project to generate in |
| `FACELESS_BROWSER_HEADLESS` | `0` | keep `0`: headless stalls on bot checks |
| `FACELESS_BROWSER_GEN_TIMEOUT` | `180` | seconds to wait per image |
| `FACELESS_BROWSER_UPLOAD_TIMEOUT` | `120` | seconds for reference uploads |
| `FACELESS_BROWSER_MAX_CREATIVE` | `2` | attempts per frame before it's marked failed |
| `FACELESS_BROWSER_TRACE` | `1` | save a Playwright action trace on technical failures |

## When something goes wrong

| Result | Meaning | Do |
|---|---|---|
| `blocked: authentication_required` | signed out | `faceless browser setup` |
| `captcha_or_mfa_required` / "Just a moment…" | bot check | clear it yourself in the window, then `resume` |
| `rate_limit` | ChatGPT's image limit reached | wait (hours), then `resume` |
| `generation_refusal` | content policy tripped on the picture | rewrite the beat's visual (garments, framing, imply rather than show); don't re-roll |
| `selector_drift` | ChatGPT's UI changed | `faceless browser doctor --headed`; update `faceless/browser/selectors.py` |
| `generation_timeout` | slow generation or missed detection | `faceless browser resume` (it looks for the finished image first) |

Failure screenshots and a sanitised DOM excerpt are saved to `~/.faceless/diagnostics/`; secrets are redacted.

## Etiquette

Keep to one video's queue at a time, generate sequentially, and stay within ChatGPT's terms and your plan's limits. The adapter is a convenience for your own account — not a way to scale beyond it.
