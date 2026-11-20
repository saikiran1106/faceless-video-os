"""`faceless login ...` - one command to connect the media generators. The human signs in; nothing types credentials.

  faceless login images                 asks: ChatGPT in the browser, or the Codex CLI
  faceless login images --via browser   opens chatgpt.com in a persistent profile; if it is already signed in, done
  faceless login images --via codex     installs the Codex CLI if missing, runs `codex login` if not signed in
  faceless login flow --accounts 3      opens 3 browser windows (flow-1..flow-3), one Google account each
  faceless login status [--live]        what is connected

Config: ~/.faceless/media.json (no secrets: logins live only inside the profile folders / Codex's own auth store).
Profiles: ~/.faceless/browser-profiles/<name> (0700, outside every repo). Also mirrored into
automation/config/accounts.json so `python -m studio_os.cli accounts doctor` sees them.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HOME = Path(os.environ.get("FACELESS_HOME", str(Path.home() / ".faceless"))).expanduser()
CONFIG = HOME / "media.json"
PROFILES = HOME / "browser-profiles"
REPO = Path(__file__).resolve().parents[1]
ACCOUNTS = REPO / "automation" / "config" / "accounts.json"

SERVICES = {
    "chatgpt": {"url": "https://chatgpt.com/", "channel": "chromium", "check": "chatgpt", "label": "ChatGPT"},
    "flow": {"url": "https://flow.google.com/", "channel": "chrome", "check": "flow", "label": "Google Flow"},
}
PROJECT_RE = re.compile(r"/project/[0-9a-zA-Z-]{8,}")


def _say(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def load() -> dict:
    if CONFIG.exists():
        return json.loads(CONFIG.read_text())
    return {"images": {}, "flow": {"profiles": []}}


def save(cfg: dict) -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=1))
    _mirror_accounts(cfg)


def _mirror_accounts(cfg: dict) -> None:
    """Keep automation/config/accounts.json in step (git-ignored; the studio_os doctor reads it)."""
    data = json.loads(ACCOUNTS.read_text()) if ACCOUNTS.exists() else {"profiles": {}}
    for p in cfg.get("images", {}).get("profiles", []):
        data["profiles"][p["name"]] = {"account": p.get("account", "(signed in by faceless login)"), "dir": p["dir"], "channel": "chromium",
                                       "used_for": ["image generation (ChatGPT)"],
                                       "services": {"chatgpt": {"url": SERVICES["chatgpt"]["url"], "check": "chatgpt"}}}
    for p in cfg.get("flow", {}).get("profiles", []):
        data["profiles"][p["name"]] = {"account": p.get("account", "(signed in by faceless login)"), "dir": p["dir"], "channel": "chrome",
                                       "used_for": ["video generation (Google Flow)"],
                                       "services": {"google_flow": {"url": SERVICES["flow"]["url"], "check": "flow"}}}
    ACCOUNTS.parent.mkdir(parents=True, exist_ok=True)
    ACCOUNTS.write_text(json.dumps(data, indent=1))


def _profile_dir(name: str) -> Path:
    d = PROFILES / name
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, stat.S_IRWXU)
    except OSError:
        pass
    return d


# ---------------------------------------------------------------- sign-in checks (read-only)
def _signed_in(page, kind: str) -> tuple[bool, dict]:
    url = page.url
    if "accounts.google.com" in url or "/auth/" in url or "/login" in url.split("?")[0]:
        return False, {}
    try:
        if kind == "chatgpt":
            login = page.get_by_role("button", name="Log in")
            composer = page.locator("#prompt-textarea, [contenteditable=true]")
            ok = composer.count() > 0 and not any(login.nth(i).is_visible() for i in range(login.count()))
            return ok, {}
        if kind == "flow":
            ok = "flow.google.com" in url and "/about" not in url and page.get_by_role("button", name="Account details").count() > 0
            acct = None
            if ok:
                link = page.get_by_role("link", name="Google Account")
                acct = link.first.get_attribute("aria-label") if link.count() else None
            return ok, {"account_label": acct} if acct else {}
    except Exception:  # noqa: BLE001 - page navigating
        return False, {}
    return False, {}


def _launch(pw, service: str, prof_dir: Path):
    svc = SERVICES[service]
    kw = dict(user_data_dir=str(prof_dir), headless=False, accept_downloads=True, viewport={"width": 1280, "height": 860},
              args=["--disable-blink-features=AutomationControlled"])
    if svc["channel"] == "chrome" and os.environ.get("FACELESS_CHROME_PATH"):
        kw.update(executable_path=os.environ["FACELESS_CHROME_PATH"], ignore_default_args=["--enable-automation"])
    elif svc["channel"] == "chrome" and (shutil.which("google-chrome") or shutil.which("google-chrome-stable") or sys.platform in ("darwin", "win32")):
        kw.update(channel="chrome", ignore_default_args=["--enable-automation"])  # Google sign-in rejects bundled Chromium
    # Same launch flags as the generators (studio_os adapters): a different --password-store would make the saved
    # cookies unreadable to them and the profile would look signed out.
    return pw.chromium.launch_persistent_context(**kw)


def login_browser(service: str, accounts: int = 1, wait_s: int = 1800, keep_open: bool = False, names: list[str] | None = None) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("Playwright is not installed. Run: pip install 'faceless-video-os[browser]' && python -m playwright install chromium") from exc
    if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        raise SystemExit("No display for a browser window. On a remote shell set DISPLAY (and XAUTHORITY) to your desktop session first.")
    svc = SERVICES[service]
    names = names or [f"{service}-{k}" for k in range(1, accounts + 1)]
    results: dict[str, dict] = {}
    with sync_playwright() as pw:
        live = {}
        for n in names:
            d = _profile_dir(n)
            try:
                ctx = _launch(pw, service, d)
            except Exception as e:  # noqa: BLE001
                results[n] = {"name": n, "dir": str(d), "signed_in": False, "error": f"could not open (profile in use?): {str(e)[:160]}"}
                continue
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                page.goto(svc["url"], wait_until="domcontentloaded", timeout=90000)
            except Exception:  # noqa: BLE001
                pass
            live[n] = {"ctx": ctx, "dir": d, "signed": False, "since": None, "extra": {}}
        _say(f"\n{len(live)} {svc['label']} window(s) open: {', '.join(live)}."
             f"\n  Sign in in each window (one account per window). Already signed in? It is detected and closed for you."
             + ("\n  Flow: after signing in, open (or create) the Flow project to use in that window - its URL is saved."
                "\n  Close the window when you are done." if service == "flow" else "") + "\n")
        deadline = time.time() + wait_s
        time.sleep(6)
        while live and time.time() < deadline:
            for n in list(live):
                st = live[n]
                ctx = st["ctx"]
                pages = [p for p in ctx.pages if not p.is_closed()]
                if not pages:  # human closed the window
                    results[n] = {"name": n, "dir": str(st["dir"]), "signed_in": st["signed"], **st["extra"]}
                    _say(f"  {n}: window closed - {'signed in' if st['signed'] else 'NOT signed in'}")
                    live.pop(n)
                    continue
                for p in pages:
                    if service == "flow" and PROJECT_RE.search(p.url or ""):
                        st["extra"]["project_url"] = p.url.split("?")[0]
                    ok, extra = _signed_in(p, svc["check"])
                    if ok:
                        if not st["signed"]:
                            _say(f"  {n}: signed in" + (f" ({extra['account_label']})" if extra.get("account_label") else ""))
                        st["signed"] = True
                        st["since"] = st["since"] or time.time()
                        st["extra"].update(extra)
                        break
                done = st["signed"] and (service != "flow" or "project_url" in st["extra"] or time.time() - st["since"] > 600)
                if done and not keep_open:
                    results[n] = {"name": n, "dir": str(st["dir"]), "signed_in": True, **st["extra"]}
                    if service == "flow" and "project_url" not in st["extra"]:
                        results[n]["note"] = "no Flow project opened; set it later with `faceless login flow --project-url NAME URL`"
                    try:
                        ctx.close()
                    except Exception:  # noqa: BLE001
                        pass
                    _say(f"  {n}: ready" + (f" - project {st['extra'].get('project_url')}" if st["extra"].get("project_url") else ""))
                    live.pop(n)
            time.sleep(3)
        for n, st in live.items():
            results[n] = {"name": n, "dir": str(st["dir"]), "signed_in": st["signed"], **st["extra"], "note": "timed out waiting"}
            try:
                st["ctx"].close()
            except Exception:  # noqa: BLE001
                pass
    stamp = datetime.now().isoformat(timespec="seconds")
    cfg = load()
    if service == "chatgpt":
        img = cfg.setdefault("images", {})
        img["via"] = "browser"
        keep = [p for p in img.get("profiles", []) if p["name"] not in results]
        img["profiles"] = keep + [dict(r, checked=stamp) for r in results.values()]
    else:
        fl = cfg.setdefault("flow", {"profiles": []})
        old = {p["name"]: p for p in fl.get("profiles", [])}
        for n, r in results.items():
            merged = dict(old.get(n, {}), **r, checked=stamp)
            old[n] = merged
        fl["profiles"] = [old[k] for k in sorted(old)]
    save(cfg)
    ok = [r["name"] for r in results.values() if r.get("signed_in")]
    return {"service": service, "signed_in": ok, "not_signed_in": [n for n in results if n not in ok], "profiles": list(results.values()),
            "config": str(CONFIG)}


# ---------------------------------------------------------------- Codex CLI
def _codex_bin() -> str | None:
    return shutil.which("codex") or next((str(p) for p in (Path.home() / ".local/bin/codex", Path.home() / ".npm-global/bin/codex") if p.exists()), None)


def codex_status() -> dict:
    exe = _codex_bin()
    if not exe:
        return {"installed": False, "signed_in": False}
    ver = subprocess.run([exe, "--version"], capture_output=True, text=True).stdout.strip()
    st = subprocess.run([exe, "login", "status"], capture_output=True, text=True)
    text = (st.stdout + st.stderr).strip()
    feats = subprocess.run([exe, "features", "list"], capture_output=True, text=True).stdout
    img = next((ln for ln in feats.splitlines() if ln.split() and ln.split()[0] == "image_generation"), "")
    return {"installed": True, "bin": exe, "version": ver, "signed_in": st.returncode == 0 and "not logged in" not in text.lower(),
            "login_status": text[:200], "image_generation": img.split()[-1] == "true" if img else None}


def login_codex() -> dict:
    st = codex_status()
    if not st["installed"]:
        if not shutil.which("npm"):
            raise SystemExit("Codex CLI is not installed and npm is missing. Install Node.js 18+ (./install.sh does it), then re-run.")
        _say("Installing the Codex CLI (npm install -g @openai/codex) ...")
        r = subprocess.run(["npm", "install", "-g", "@openai/codex"])
        if r.returncode != 0:
            _say("Global install needs permissions; installing into ~/.local instead ...")
            subprocess.run(["npm", "install", "-g", "--prefix", str(Path.home() / ".local"), "@openai/codex"], check=True)
            _say("Add ~/.local/bin to your PATH if `codex` is not found in new shells.")
        st = codex_status()
        if not st["installed"]:
            raise SystemExit("Codex CLI install did not produce a `codex` command.")
    if not st["signed_in"]:
        _say("Opening the Codex sign-in (use your ChatGPT account) ...")
        cmd = [st["bin"], "login"] + ([] if sys.stdin.isatty() else ["--device-auth"])
        subprocess.run(cmd)
        st = codex_status()
    if st.get("image_generation") is False:
        _say("Note: Codex reports image_generation disabled; enable it with `codex features enable image_generation` if available.")
    cfg = load()
    cfg.setdefault("images", {})["via"] = "codex"
    cfg["images"]["codex"] = {"bin": st.get("bin"), "version": st.get("version"), "checked": datetime.now().isoformat(timespec="seconds")}
    save(cfg)
    return {"service": "codex", **st, "config": str(CONFIG)}


def set_project_url(name: str, url: str) -> dict:
    cfg = load()
    for p in cfg.setdefault("flow", {"profiles": []})["profiles"]:
        if p["name"] == name:
            p["project_url"] = url
            save(cfg)
            return {"flow_profile": name, "project_url": url}
    raise SystemExit(f"No Flow profile named {name!r}. Known: {[p['name'] for p in cfg['flow']['profiles']]}")


def status(live: bool = False) -> dict:
    cfg = load()
    out = {"config": str(CONFIG), "images": {"via": cfg.get("images", {}).get("via")}, "flow": []}
    out["images"]["codex"] = codex_status()
    out["images"]["browser_profiles"] = [{"name": p["name"], "signed_in_at_setup": p.get("signed_in"), "dir_exists": Path(p["dir"]).exists()}
                                         for p in cfg.get("images", {}).get("profiles", [])]
    for p in cfg.get("flow", {}).get("profiles", []):
        out["flow"].append({"name": p["name"], "signed_in_at_setup": p.get("signed_in"), "project_url": p.get("project_url"), "dir_exists": Path(p["dir"]).exists()})
    if live:
        out["live_check"] = _live_check(cfg)
    if not out["images"]["via"]:
        out["next"] = "faceless login images"
    elif not out["flow"]:
        out["next"] = "faceless login flow --accounts 1   (only if you want Google Flow video clips)"
    return out


def _live_check(cfg: dict) -> dict:
    """Headless read-only check. 'signed out' can be a false negative under load: confirm in a headed window."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"error": "playwright not installed"}
    res = {}
    with sync_playwright() as pw:
        for kind, profs in (("chatgpt", cfg.get("images", {}).get("profiles", [])), ("flow", cfg.get("flow", {}).get("profiles", []))):
            for p in profs:
                try:
                    ctx = _launch(pw, kind, Path(p["dir"]))
                    page = ctx.pages[0] if ctx.pages else ctx.new_page()
                    page.goto(SERVICES[kind]["url"], wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(8000)
                    res[p["name"]] = _signed_in(page, kind)[0]
                    ctx.close()
                except Exception as e:  # noqa: BLE001
                    res[p["name"]] = f"error: {str(e)[:100]}"
    return res


def choose_images_backend() -> str:
    if not sys.stdin.isatty():
        st = codex_status()
        return "codex" if st["installed"] and st["signed_in"] else "browser"
    _say("How should images be generated?\n  1) ChatGPT in the browser (sign in once in a window)\n  2) Codex CLI (installs if needed, signs in with ChatGPT)")
    ans = input("Choose 1 or 2 [1]: ").strip()
    return "codex" if ans == "2" else "browser"


def add_parser(sub) -> None:
    p = sub.add_parser("login", help="connect image/video generators: ChatGPT browser, Codex CLI, Google Flow accounts")
    ls = p.add_subparsers(dest="login_cmd", required=True)
    i = ls.add_parser("images", help="ChatGPT in the browser or the Codex CLI")
    i.add_argument("--via", choices=["browser", "codex"], help="skip the question")
    i.add_argument("--accounts", type=int, default=1, help="browser: how many ChatGPT accounts (one window each)")
    i.add_argument("--wait", type=int, default=1800, help="seconds to wait for sign-in")
    i.add_argument("--keep-open", action="store_true")
    f = ls.add_parser("flow", help="Google Flow: one browser window per account")
    f.add_argument("--accounts", type=int, help="how many Google accounts (asked if omitted)")
    f.add_argument("--only", nargs="*", help="re-open just these profiles, e.g. flow-2")
    f.add_argument("--wait", type=int, default=1800)
    f.add_argument("--keep-open", action="store_true")
    f.add_argument("--project-url", nargs=2, metavar=("PROFILE", "URL"), help="set the Flow project URL of a profile, no window")
    s = ls.add_parser("status", help="what is connected")
    s.add_argument("--live", action="store_true", help="open each profile headless and check (read-only)")


def handle(args) -> int:
    if args.login_cmd == "status":
        print(json.dumps(status(args.live), indent=1))
        return 0
    if args.login_cmd == "images":
        via = args.via or choose_images_backend()
        r = login_codex() if via == "codex" else login_browser("chatgpt", args.accounts, args.wait, args.keep_open)
        print(json.dumps(r, indent=1))
        return 0 if (r.get("signed_in") is True or (isinstance(r.get("signed_in"), list) and r["signed_in"])) else 2
    if args.login_cmd == "flow":
        if args.project_url:
            print(json.dumps(set_project_url(*args.project_url), indent=1))
            return 0
        n = args.accounts
        if n is None and not args.only:
            n = int(input("How many Google accounts do you want to use for Flow? [1]: ").strip() or 1) if sys.stdin.isatty() else 1
        r = login_browser("flow", n or 1, args.wait, args.keep_open, names=args.only)
        print(json.dumps(r, indent=1))
        return 0 if r["signed_in"] else 2
    return 1
