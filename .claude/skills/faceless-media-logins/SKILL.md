---
name: faceless-media-logins
description: Connect and use the media generators with one command each - images through ChatGPT in a signed-in browser profile or through the Codex CLI (installed and signed in automatically), and Google Flow video with any number of Google accounts (one browser window per account) - then generate with `faceless gen images` / `faceless gen clips`. Use when someone says "set up image generation", "log in to ChatGPT / Codex / Flow", "use my 3 Flow accounts", "connect my accounts", when a generator says it is not connected, or before the first image/clip of a project.
---

# Faceless Media Logins

Code: `faceless/logins.py` (connect) and `faceless/gen.py` (generate). Config: `~/.faceless/media.json` (no secrets).
Profiles: `~/.faceless/browser-profiles/<name>`. Deeper browser rules: `faceless-browser-logins`; generation rules:
`faceless-chatgpt-images`, `faceless-flow-video`.

## Connect (the human signs in; you never type credentials)
| Goal | Command | What happens |
|---|---|---|
| choose interactively | `faceless login images` | asks: 1) ChatGPT in the browser 2) Codex CLI |
| ChatGPT browser | `faceless login images --via browser [--accounts 2]` | opens chatgpt.com in profile `chatgpt-1..N`; already signed in → detected and closed; else waits for the human |
| Codex CLI | `faceless login images --via codex` | installs `@openai/codex` with npm if missing (falls back to `~/.local`), runs `codex login` if signed out (`--device-auth` code when no terminal), checks the image tool |
| Google Flow | `faceless login flow --accounts 3` | opens 3 windows (`flow-1..3`), one Google account each; after sign-in the human opens/creates the Flow project in each window - its URL is saved |
| fix one account | `faceless login flow --only flow-2` | re-opens just that window |
| set a project URL | `faceless login flow --project-url flow-2 https://flow.google.com/project/...` | no window |
| check | `faceless login status [--live]` | config + Codex status; `--live` opens each profile headless (read-only) |

Tell the human exactly what to do in the windows ("sign in with the account you want for Flow, open the project, close
the window"), then wait. Run from a desktop session (on SSH set `DISPLAY`/`XAUTHORITY`). One process per profile.
A headless "signed out" can be a false negative under load: confirm headed before asking the human to log in again.

## Generate
- Images: `faceless gen images --jobs jobs.json --out DIR [--via codex|browser|api] [--workers 2]` with
  `[{"id": "P01", "prompt": "...", "aspect": "16:9", "refs": []}]` → `DIR/<id>.png` + `gen_manifest.json`.
  Codex binds each image by its Codex session id; browser shards jobs across ChatGPT accounts (one image per message,
  bound through the conversation API); `api` (OpenAI Images) shows the cost and needs `--yes`.
  Wild-doc does this for you: `faceless wild-doc images <project>`.
- Flow clips: `faceless gen clips --project DIR --credit-cap N [--accounts flow-1 flow-3] [--dry-run] [--copy-to DIR]`.
  Beats from `DIR/05-visuals/shot_plan.json` are split across accounts; each account runs in its own folder
  (`06-video/accounts/<name>`, own ledger) and clips are gathered in `06-video/clips`. Landscape films: set
  `FACELESS_FLOW_ASPECT=16_9` and the composer to 16:9 first. For a wild-doc film, `--copy-to <wild-doc>/06-assets/clips`
  makes every clip usable as `S:<clip name>`.

## Hard rules
- **State the minimum and worst-case credits and get an explicit yes before `gen clips`.** Always `--dry-run` first, then
  watch the first clip's real burn before trusting the plan.
- Never resubmit a timed-out job (it can still finish and charge twice): look for the result, then re-run with `--only`.
- Look at every image against its prompt before it goes into a film.
- Profiles stay outside git; `automation/config/accounts.json` is git-ignored. Never copy cookies between profiles.
