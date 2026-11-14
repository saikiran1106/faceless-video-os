---
name: faceless-browser-logins
description: Set up and operate persistent Playwright browser profiles for AI web tools (ChatGPT, Google Flow, YouTube Studio, Meta Business Suite, Gmail) - human-only sign-in, login doctor, keepalive, headless/keyring fix, CDP attach, remote shells, posting. Use whenever an automation must act inside a logged-in website, when a profile shows 'signed out', or before any browser-driven image/video generation, mail send or post.
---

# Faceless Browser Logins

Read `docs/learnings/01-browser-automation-and-logins.md` first. Code: `automation/studio_os/accounts.py`.

## Procedure
1. `cd automation && cp config/accounts.example.json config/accounts.json` (git-ignored; edit accounts, profile dirs, services).
2. **The human signs in.** `python -m studio_os.cli accounts login <profile>` opens a headed window with one tab per service. Never type credentials, read cookies, or copy another browser's profile. Ask the human to sign in; wait for them.
3. `python -m studio_os.cli accounts doctor [--profile NAME]` (read-only). "signed out" can be a false negative under load: confirm with a real page action before bothering the human.
4. Daily: `accounts keepalive` from a timer (refreshes sessions, desktop alert for sign-outs).

## Hard rules
- Profiles live outside git (`~/.faceless/browser-profiles/<name>`, 0700); one process per profile at a time.
- Google sites: real Chrome (`channel="chrome"`, drop `--enable-automation`). Sites that block Playwright: real Chrome + `--remote-debugging-port` + `connect_over_cdp`. Big uploads: launch Playwright locally, not over CDP.
- Headless Linux profile shows a login page? Use `--password-store=gnome-libsecret` and drop the basic/mock-keychain defaults.
- SSH/remote: set `DISPLAY` and `XAUTHORITY` before launching a headed browser.
- Select by role + accessible name, never generated ids; selectors live in one file and are re-surveyed from the live UI by `doctor`.
- Posting: never click Share twice (it publishes immediately). Never post/send/upload unless the human asked.
