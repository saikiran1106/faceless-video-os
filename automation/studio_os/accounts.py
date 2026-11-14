"""Brand browser profiles: login doctor (read-only) and a manual-login helper.

The map lives in config/accounts.json. Logins live only inside the profile directories (outside the
repo); this module never types credentials, never reads cookies, never creates accounts.

  python -m studio_os.cli accounts show
  python -m studio_os.cli accounts doctor [--profile NAME]
  python -m studio_os.cli accounts login <profile> [--service youtube_studio ...]
  python -m studio_os.cli accounts keepalive   # daily timer: visit every service, alert on sign-outs
"""
from __future__ import annotations

import json
import subprocess
import shutil
import sys
import time
import warnings
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONFIG = Path(__file__).resolve().parents[1] / "config" / "accounts.json"


def load() -> dict:
    if not CONFIG.exists():
        raise SystemExit(f"missing {CONFIG}: copy config/accounts.example.json to config/accounts.json and edit it")
    return json.loads(CONFIG.read_text())


@contextmanager
def open_profile(name: str, headless: bool = False):
    from playwright.sync_api import sync_playwright

    prof = load()["profiles"][name]
    pw = sync_playwright().start()
    kw = dict(user_data_dir=str(Path(prof["dir"]).expanduser()), headless=headless, accept_downloads=True,
              args=["--disable-blink-features=AutomationControlled"], viewport={"width": 1440, "height": 900})
    channel = prof.get("channel")
    if channel and channel != "chromium":
        if channel == "chrome" and sys.platform.startswith("linux") and not (
            shutil.which("google-chrome") or shutil.which("google-chrome-stable")
        ):
            warnings.warn("Google Chrome is unavailable; using Playwright Chromium for this profile", stacklevel=2)
        else:
            kw["channel"] = channel
            kw["ignore_default_args"] = ["--enable-automation"]
    try:
        ctx = pw.chromium.launch_persistent_context(**kw)
    except Exception:
        pw.stop()
        raise
    try:
        yield ctx
    finally:
        try:
            ctx.close()
        except Exception:  # noqa: BLE001
            pass
        pw.stop()


# --------------------------------------------------------------- checks
def _check(page, kind: str) -> dict:
    url = page.url
    if "accounts.google.com" in url or "/loginpage" in url or "/login" in url.split("?")[0]:
        return {"ok": False, "state": "signed out", "url": url}
    if kind == "chatgpt":
        login = page.get_by_role("button", name="Log in")
        composer = page.locator("#prompt-textarea, [contenteditable=true]")
        ok = composer.count() > 0 and not any(login.nth(i).is_visible() for i in range(login.count()))
        return {"ok": ok, "state": "signed in" if ok else "signed out", "url": url}
    if kind == "flow":
        ok = "flow.google.com" in url and "/about" not in url and page.get_by_role("button", name="Account details").count() > 0
        acct = page.get_by_role("link", name="Google Account").first.get_attribute("aria-label") if ok and page.get_by_role("link", name="Google Account").count() else None
        return {"ok": ok, "state": "signed in" if ok else "signed out", "account": acct, "url": url}
    if kind == "meta":
        ok = "business.facebook.com/latest" in url
        return {"ok": ok, "state": "signed in" if ok else "signed out", "url": url}
    if kind == "x":
        ok = "x.com/home" in url
        return {"ok": ok, "state": "signed in" if ok else "signed out", "url": url}
    if kind == "youtube":
        body = page.locator("body").inner_text()[:4000].lower()
        if "create channel" in body or "create_channel" in url:
            return {"ok": False, "state": "signed in, NO CHANNEL yet", "url": url}
        ok = "studio.youtube.com" in url
        return {"ok": ok, "state": "signed in, channel ready" if "/channel/" in url else ("signed in" if ok else "unknown"),
                "url": url}
    return {"ok": None, "state": "no check", "url": url}


def doctor(profiles: list[str] | None = None, settle_ms: int = 9000) -> dict:
    cfg = load()
    out = {}
    for name in profiles or list(cfg["profiles"]):
        prof = cfg["profiles"][name]
        res = {"account": prof["account"], "services": {}}
        try:
            with open_profile(name, headless=True) as ctx:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                for svc, meta in prof["services"].items():
                    try:
                        page.goto(meta["url"], wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_timeout(settle_ms)
                        res["services"][svc] = _check(page, meta["check"])
                    except Exception as e:  # noqa: BLE001
                        res["services"][svc] = {"ok": False, "state": f"error: {str(e)[:120]}"}
        except Exception as e:  # noqa: BLE001
            res["error"] = f"could not open profile (in use by another run?): {str(e)[:160]}"
        out[name] = res
    return out


STATE = Path.home() / ".local" / "state" / "faceless-accounts"


def keepalive() -> dict:
    """Visit every service so the sites refresh their session cookies, save the result, and send a
    desktop alert for anything signed out. Profiles busy in another run are skipped, not alerted."""
    r = doctor()
    STATE.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    (STATE / "status.json").write_text(json.dumps({"checked": stamp, "profiles": r}, indent=1))
    out = [f"{p} / {s}" for p, res in r.items() for s, v in res.get("services", {}).items() if v.get("ok") is False]
    if out:
        try:
            subprocess.run(["notify-send", "-u", "critical", "Studio: signed out",
                            "\n".join(out) + "\n\nRun: accounts login <profile>"], check=False, timeout=10)
        except Exception:  # noqa: BLE001 - no desktop session
            pass
    return {"checked": stamp, "signed_out": out,
            "busy": [p for p, res in r.items() if res.get("error")]}


def login(name: str, services: list[str] | None = None, wait_s: int = 3600) -> dict:
    """Open the profile headed with one tab per service. The account owner signs in / creates channels by hand,
    then closes the window. Nothing is typed by the agent."""
    prof = load()["profiles"][name]
    want = services or list(prof["services"])
    with open_profile(name) as ctx:
        first = ctx.pages[0] if ctx.pages else ctx.new_page()
        for i, svc in enumerate(want):
            page = first if i == 0 else ctx.new_page()
            page.goto(prof["services"][svc]["url"], wait_until="domcontentloaded", timeout=60000)
        print(f"Profile '{name}' ({prof['account']}) is open with {len(want)} tab(s): {', '.join(want)}.\n"
              "Sign in where needed (and create the YouTube channel if it asks), then CLOSE THE WINDOW.", flush=True)
        deadline = time.time() + wait_s
        while time.time() < deadline and any(not p.is_closed() for p in ctx.pages):
            time.sleep(2)
    return {"profile": name, "opened": want}


def add_parser(sub):
    p = sub.add_parser("accounts", help="brand browser profiles: show, doctor, login")
    s = p.add_subparsers(dest="accounts_cmd", required=True)
    s.add_parser("show")
    d = s.add_parser("doctor")
    d.add_argument("--profile", action="append")
    lg = s.add_parser("login")
    lg.add_argument("profile")
    lg.add_argument("--service", action="append")
    s.add_parser("keepalive")
    return p


def handle(args) -> int:
    if args.accounts_cmd == "show":
        print(json.dumps(load(), indent=1))
    elif args.accounts_cmd == "doctor":
        r = doctor(args.profile)
        print(json.dumps(r, indent=1))
        return 0 if all(s.get("ok") for p in r.values() for s in p.get("services", {}).values()) else 2
    elif args.accounts_cmd == "login":
        print(json.dumps(login(args.profile, args.service), indent=1))
    elif args.accounts_cmd == "keepalive":
        r = keepalive()
        print(json.dumps(r, indent=1))
        return 2 if r["signed_out"] else 0
    return 0
