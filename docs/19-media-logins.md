# 19. Media logins: images (ChatGPT browser or Codex CLI) and Google Flow accounts

One command connects each generator. **You sign in yourself, in a normal browser window.** Nothing types your
password, reads your cookies or stores credentials: logins live inside the browser-profile folders
(`~/.faceless/browser-profiles/<name>`, outside every repo) or in the Codex CLI's own auth store.

## Images

```bash
faceless login images
```
asks which generator to use:

```
How should images be generated?
  1) ChatGPT in the browser (sign in once in a window)
  2) Codex CLI (installs if needed, signs in with ChatGPT)
```

**1 - ChatGPT in the browser** (`faceless login images --via browser`): a window opens on chatgpt.com in the profile
`chatgpt-1`. Already signed in from an earlier run? It is detected and the window closes by itself. Otherwise sign in;
the window closes when the composer appears. Several ChatGPT accounts (more images per hour):
`--accounts 2` opens `chatgpt-1` and `chatgpt-2` side by side.

**2 - Codex CLI** (`faceless login images --via codex`): if `codex` is missing it is installed
(`npm install -g @openai/codex`, or into `~/.local` without admin rights). If you are not signed in, `codex login` runs
and opens the ChatGPT sign-in page (on a remote shell it prints a device code instead). Images use Codex's built-in
image tool on your ChatGPT plan.

## Google Flow (video clips)

```bash
faceless login flow --accounts 3
```
opens **three windows** (`flow-1`, `flow-2`, `flow-3`), one per Google account. In each one: sign in, then open (or
create) the Flow project you want to use; its URL is saved. Close the window when done. Leave out `--accounts` and you
are asked how many. Re-do one account: `faceless login flow --only flow-2`. Set a project URL without a window:
`faceless login flow --project-url flow-2 https://flow.google.com/project/...`.

Flow needs Google Chrome installed (Google rejects sign-ins from the bundled Chromium). For an unpacked Chrome without
root, set `FACELESS_CHROME_PATH=/path/to/chrome`.

## Check

```bash
faceless login status          # what is configured + Codex login state
faceless login status --live   # also opens each profile headless (read-only) and checks the sign-in
```
A headless "signed out" can be wrong when the machine is busy; open the profile with `login … --only NAME` to be sure.

## Generate

```bash
# images: one per job, to DIR/<id>.png  (+ DIR/gen_manifest.json: how each image was bound to its job)
faceless gen images --jobs jobs.json --out ./frames                 # uses the connected generator
faceless gen images --jobs jobs.json --out ./frames --via codex --workers 2
faceless gen images --jobs jobs.json --out ./frames --via browser   # shards jobs across chatgpt-1..N
faceless gen images --jobs jobs.json --out ./frames --via api --yes # OpenAI Images API (paid, estimate first)
```
`jobs.json`:
```json
[{"id": "P01", "prompt": "A woolly rhino crossing a frozen river at dusk ...", "aspect": "16:9", "refs": []}]
```

```bash
# Flow clips (PAID credits): beats from DIR/05-visuals/shot_plan.json split across the signed-in accounts
faceless gen clips --project ./my-flow-project --credit-cap 120 --dry-run       # every guard, nothing generated
faceless gen clips --project ./my-flow-project --credit-cap 120 --accounts flow-1 flow-2
```
Each account runs in its own folder with its own ledger; finished clips are collected in `06-video/clips`
(`--copy-to` copies them anywhere else, for example a wild-doc project's `06-assets/clips`). For landscape films set
`FACELESS_FLOW_ASPECT=16_9`. The shot-plan format and the spend guards are in
[`faceless-flow-video`](../skills/faceless-flow-video/SKILL.md).

## Where things are stored

| What | Where |
|---|---|
| choices, profile list, Flow project URLs | `~/.faceless/media.json` |
| browser profiles (your logins) | `~/.faceless/browser-profiles/<name>` (mode 0700) |
| studio_os account map (mirrored) | `automation/config/accounts.json` (git-ignored) |
| Codex auth | the Codex CLI's own store (`codex login status`) |

## Rules your agent follows
- It never signs in for you; it opens the window and waits.
- It shows the minimum and worst-case credits and asks before any Flow generation, and runs `--dry-run` first.
- It never resubmits a timed-out image or clip (it may still finish and charge twice).
