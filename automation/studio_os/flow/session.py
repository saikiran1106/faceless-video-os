"""Headed persistent Chrome session for Google Flow."""
from __future__ import annotations

import os
from contextlib import contextmanager

from .config import FlowConfig


@contextmanager
def flow_session(cfg: FlowConfig):
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    # Rootless Chrome (unpacked .deb): FACELESS_CHROME_PATH overrides the system-wide "chrome" channel.
    chrome_path = os.environ.get("FACELESS_CHROME_PATH")
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(cfg.profile_dir),
        **({"executable_path": chrome_path} if chrome_path else {"channel": cfg.channel}),
        headless=False,                      # Flow is always driven headed
        accept_downloads=True,
        ignore_default_args=["--enable-automation"],
        args=["--disable-blink-features=AutomationControlled"],
        viewport={"width": 1440, "height": 900},
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.set_default_timeout(cfg.nav_timeout_s * 1000)
    try:
        yield ctx, page
    finally:
        try:
            ctx.close()
        except Exception:  # noqa: BLE001 - the window was already closed by hand
            pass
        pw.stop()


def signed_in(page) -> bool:
    """True when we are on a Flow page, not a Google sign-in or marketing page."""
    url = page.url
    return url.startswith("https://flow.google.com/project/")
