# 1. Browser automation and logins (Playwright)

Image and video generators (ChatGPT images, Google Flow) have no usable public API for what we need, so we drive
their web UI with Playwright. Everything below was learned the hard way; the code is in
[`automation/studio_os`](../../automation/studio_os) (`accounts.py`, `browser/`, `flow/`, `fast/`).

## The security model (non-negotiable)

- **The human signs in, once, by hand.** The agent never types a password, 2FA code or cookie. `accounts login <profile>`
  opens a headed window with one tab per service; you sign in, close the window, done.
- **The login lives only in a persistent profile directory outside every git repo** (`~/.faceless/browser-profiles/<name>`,
  mode 0700). `BrowserConfig.profile_inside_repo()` is the guard to call: a profile must never resolve inside a git worktree. Never read, log, copy or export
  cookies/storage; never "borrow" the cookies of your daily browser profile.
- **One profile per account and purpose** (e.g. an images profile, a video profile, a social-posting profile). A profile can only
  be opened by one process at a time: "could not open profile" almost always means another run still holds it.
- Config that maps profile → account → services lives in `automation/config/accounts.json` (copy the `.example.json`).
  It holds *no* secrets, but it is personal (emails, business IDs), so it is git-ignored.

## Choosing the browser

| Situation | Use |
|---|---|
| ChatGPT | Playwright Chromium works with a persistent profile |
| Google (Flow, YouTube Studio, Gmail) | **Real Google Chrome** (`channel="chrome"`) with `ignore_default_args=["--enable-automation"]` and `--disable-blink-features=AutomationControlled`. Bundled Chromium is more likely to be challenged |
| A site that blocks Playwright outright (Canva was one) | Start real `google-chrome --user-data-dir=<profile> --remote-debugging-port=9222`, then `chromium.connect_over_cdp("http://127.0.0.1:9222")` |
| Large file uploads (hundreds of MB), e.g. posting a reel | Launch Playwright **locally** and set files on the chooser. CDP-attached uploads time out around 45 MB |

## Login doctor: read-only, and it can lie

`accounts doctor` visits each service in a headless profile and checks for a logged-in marker (composer present and no
"Log in" button; `flow.google.com` not on `/about`; `studio.youtube.com`, `business.facebook.com/latest`, …).
- **"signed out" is often a false negative** under heavy machine load (a 10 s composer check times out). Before asking the
  human to log in again, run one real action (open the app, check the composer) and look at the page.
- `accounts keepalive` (run daily from a timer) visits every service so the sites refresh session cookies, and raises a
  desktop notification for anything signed out. Profiles busy in another run are skipped, not alerted.

## Headless profile cannot decrypt its own cookies (Linux)

Playwright's default `--password-store=basic --use-mock-keychain` can't read cookies that real Chrome encrypted with the
desktop keyring, so a perfectly signed-in profile shows the Google sign-in page when launched headless. Fix:
```python
launch_persistent_context(user_data_dir, channel="chrome", headless=True,
    ignore_default_args=["--password-store=basic", "--use-mock-keychain"],
    args=["--password-store=gnome-libsecret"])
```
Related: the same profile also signs Gmail in, so a delivery mail can be sent from it (see [10](10-delivery-and-publishing.md)).

## Remote / SSH shells

A headed browser needs a display. From an SSH or phone session set `DISPLAY=:0` and `XAUTHORITY=$(ls /run/user/$UID/.mutter-Xwaylandauth.*)`
(GNOME/Wayland) before launching. Reaching the machine at all: Tailscale in userspace mode as a user systemd unit
(`tailscaled --tun=userspace-networking --socket=... `, linger enabled) plus Tailscale SSH, with no router port-forwarding.

## Known failure modes

| Symptom | Cause / fix |
|---|---|
| Playwright's node process crashes at start | Point `PLAYWRIGHT_NODEJS_PATH` at a working node binary (a second project's node worked when the venv's did not) |
| ChatGPT shows a Cloudflare interstitial after ~10 fresh chats in a row | Slow down, keep chats longer-lived, or fall back to another image source (Flow's image model costs 0 credits) |
| Adapter crashes on a truncated base64 download | Re-run only the missing beats; never assume the batch finished |
| `while pgrep -f <pattern>` wait loop never ends | The loop matches its own command line. Wait on a PID or an output file instead |
| Browser freezes the laptop / GPU hang (`i915 GPU HANG`) | Launch with `--no-browser-gpu`; use software GL for renders (see [8](08-media-integrity-and-flaky-hardware.md)) |
| Selectors stop matching after a UI update | Selectors are discovered from the **live signed-in UI** (`doctor` surveys it), keep them in one file, select by role + accessible name, never by generated ids (`mat-button-toggle-7`) |

## Posting from a business UI (Meta Business Suite recipe that worked)

Open the composer URL in the right profile → untick the Facebook Page if posting to Instagram only → set files through the
"Add video" chooser → click the caption box **with the mouse** (it is a Draft.js editor) and use `keyboard.insert_text` → press
Escape to close the hashtag popup → thumbnail: "Upload image" tab → "Upload Image" link opens the chooser → Next → Public →
**Share publishes immediately; there is no confirm step, so never click twice** (it duplicates the post).
Caption: keywords in line 1; at most 5 hashtags (Instagram's cap).
