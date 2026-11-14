"""Open the ChatGPT profile and get out of the way.

This script exists because automated polling was interrupting a human's login:
a pending `page.goto` aborts the moment the user clicks "Log in", and a retry
loop then re-navigates the tab and destroys the half-finished sign-in.

So this does exactly three things: launch the persistent profile, open
chatgpt.com once, and then sleep. It never navigates, clicks, types, polls the
DOM, or reads storage. Close the window yourself when you are signed in, then
run `studio_os browser doctor --headed` to confirm.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from studio_os.browser.config import BrowserConfig          # noqa: E402

from playwright.sync_api import sync_playwright              # noqa: E402


def main() -> int:
    cfg = BrowserConfig().ensure_dirs()
    print(f"profile: {cfg.profile_dir}")
    print("Opening a browser window. Sign in there, then just close the window.")
    print("Nothing will touch the page while it is open.", flush=True)

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(cfg.profile_dir),
            headless=False,
            accept_downloads=True,
            args=["--disable-blink-features=AutomationControlled"],
            viewport=None,                      # real window size, like a normal browser
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            # Fire and forget. If the user navigates first, that is fine.
            page.goto(cfg.chatgpt_url, wait_until="commit", timeout=120_000)
        except Exception as e:                  # noqa: BLE001
            print(f"(navigation note: {str(e)[:120]})", flush=True)

        print("READY - window is yours.", flush=True)
        try:
            while ctx.pages:                    # exits when the human closes it
                time.sleep(2)
        except KeyboardInterrupt:
            pass
        print("window closed", flush=True)
        try:
            ctx.close()
        except Exception:                       # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
