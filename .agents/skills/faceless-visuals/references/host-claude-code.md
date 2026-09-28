# Keyframes on Claude Code (ChatGPT through a Playwright browser)

Claude Code has no built-in image model, so Faceless Forge drives the ChatGPT web app in a
persistent, signed-in Chromium profile. It operates the normal UI only: it never reads
cookies or tokens, never replays private endpoints, and never solves CAPTCHAs.

## One-time setup (the human does the sign-in)

```bash
pip install -e ".[browser]" && playwright install chromium
faceless browser setup          # a window opens; the HUMAN signs in to ChatGPT, completes any MFA
faceless browser doctor         # non-consuming health check: signed in, composer found, uploads OK
```
The profile lives in `~/.faceless/browser-profiles/` (outside the repo, owner-only).
Optional: set `FACELESS_CHATGPT_PROJECT_URL` in `.env` to a ChatGPT Project URL. A Project
carries your channel's style notes and characters across chats and keeps frames on-model.

## Generate

```bash
faceless images jobs <p>
faceless browser generate --project <p>            # one image per message, sequential, one conversation
faceless browser status --project <p>
faceless browser resume --project <p>              # after a crash/timeout: recovers results, never double-submits
```
- All frames for one video run in ONE conversation (its URL is persisted), so the model keeps continuity.
- Each job's images land directly at its `output_path`. Receipts go to `07-keyframes/receipts/`.
- `--batch N` sends N prompts per message (faster). Batched images come back **out of order**, so
  they are staged unbound in `07-keyframes/_staging/`. Open each one, decide which beat it depicts,
  and file it: `faceless images record <p> KF012 07-keyframes/_staging/batch01_slot03.png`.
  Only batch character/location sheets or runs of beats that share one reference set.
- Failure classes: `authentication_required`/`captcha_or_mfa_required` → hand the window to the
  human; `rate_limit` → stop and report; `generation_refusal` → rewrite the visual, don't re-roll.
- Headed is the default: headless stalls on bot-check interstitials.

Then `faceless images manifest <p>` → contact sheet → QA → complete.
