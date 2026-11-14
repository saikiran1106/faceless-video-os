"""`studio_os browser ...` subcommands."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .config import ADAPTER_VERSION, BrowserConfig
from . import jobstore as JS
from .runner import QueueRunner


def _print(o):
    print(json.dumps(o, ensure_ascii=False, indent=1))


def add_parser(sub):
    p = sub.add_parser("browser", help="ChatGPT image-generation browser adapter")
    bs = p.add_subparsers(dest="browser_cmd", required=True)

    s = bs.add_parser("setup", help="open a headed window for one-time manual sign-in")
    s.add_argument("--profile")
    s.add_argument("--wait", type=int, default=1800,
                   help="seconds to hold the window open for manual sign-in (default 1800)")

    d = bs.add_parser("doctor", help="verify the adapter without consuming a generation")
    d.add_argument("--profile")
    d.add_argument("--headed", action="store_true")

    g = bs.add_parser("generate", help="run an image-job queue")
    g.add_argument("--project", required=True)
    g.add_argument("--queue", required=True)
    g.add_argument("--limit", type=int)
    g.add_argument("--headed", action="store_true")
    g.add_argument("--profile")
    g.add_argument("--batch", type=int, default=0,
                   help="generate N images per message (0 = one per message). "
                        "Batching pays the per-message overhead once per batch "
                        "instead of once per frame.")
    g.add_argument("--only", nargs="*", default=None,
                   help="restrict the run to these beat_ids or keyframe_ids")
    g.add_argument("--aspect", default=None, metavar="W:H",
                   help="expected output aspect, e.g. 16:9 for long-form. "
                        "Default 9:16 (the Shorts/reels contract) when omitted.")
    g.add_argument("--new-conversation", action="store_true",
                   help="start a fresh chat in the ChatGPT Project instead of "
                        "reusing this project's stored conversation")

    r = bs.add_parser("resume", help="recover in-flight jobs and continue")
    r.add_argument("--project", required=True)
    r.add_argument("--queue", required=True)
    r.add_argument("--headed", action="store_true")
    r.add_argument("--profile")
    r.add_argument("--aspect", default=None, metavar="W:H",
                   help="expected output aspect, e.g. 16:9. Default 9:16 when omitted.")
    r.add_argument("--new-conversation", action="store_true",
                   help="start a fresh chat in the ChatGPT Project instead of "
                        "reusing this project's stored conversation")

    st = bs.add_parser("status", help="show durable queue state")
    st.add_argument("--project", required=True)
    return p


def _cfg(args) -> BrowserConfig:
    c = BrowserConfig()
    if getattr(args, "profile", None):
        c.profile_dir = Path(args.profile).expanduser()
    if getattr(args, "headed", False):
        c.headless = False
    return c.ensure_dirs()


def _aspect(args):
    """`--aspect W:H` -> float, or None to keep QueueRunner.DEFAULT_RATIO (9:16)."""
    raw = getattr(args, "aspect", None)
    if not raw:
        return None
    try:
        w, h = raw.replace("x", ":").split(":")
        val = float(w) / float(h)
    except (ValueError, ZeroDivisionError):
        raise SystemExit(f"--aspect must look like 16:9 or 9:16, got {raw!r}")
    if not 0.2 <= val <= 5.0:
        raise SystemExit(f"--aspect {raw!r} is out of range")
    return val


def handle(args) -> int:
    cmd = args.browser_cmd

    if cmd == "status":
        proj = Path(args.project)
        store = JS.JobStore(proj / ".faceless" / "browser_jobs.json")
        _print({"project": str(proj), "adapter_version": ADAPTER_VERSION,
                "conversation_url": store.doc.get("conversation_url"),
                "total_jobs": len(store.doc["jobs"]),
                "by_state": store.by_state(),
                "pending": len(store.pending())})
        return 0

    cfg = _cfg(args)

    if cmd == "setup":
        cfg.headless = False
        from .imagegen import ChatGPTImageAdapter
        print(json.dumps({"action": "setup", "profile_dir": str(cfg.profile_dir),
                          "instructions": "Sign in to ChatGPT in the window that opened. "
                                          "Complete any CAPTCHA/MFA yourself. "
                                          "Close the window when the chat composer is visible."},
                         indent=1))
        with ChatGPTImageAdapter(cfg) as ad:
            try:
                ad.goto_chatgpt()
            except Exception as e:                               # noqa: BLE001
                # Not fatal: the window is open and the human can navigate.
                print(json.dumps({"status": "navigation_warning",
                                  "detail": str(e)[:160]}), flush=True)

            def report(state, url):
                print(json.dumps({"status": state, "url": url}), flush=True)

            ok = ad.wait_for_sign_in(int(getattr(args, "wait", 1800) or 1800),
                                     on_state=report)
            _print({"signed_in": ok, "profile_dir": str(cfg.profile_dir),
                    "url": (ad.page.url if ok else None),
                    "note": ("profile persisted; future runs reuse it" if ok
                             else "timed out waiting for manual sign-in")})
            return 0 if ok else 2

    if cmd == "doctor":
        from .imagegen import ChatGPTImageAdapter
        out = {"adapter_version": ADAPTER_VERSION, "config": cfg.describe()}
        try:
            import playwright                                    # noqa: F401
            from playwright.sync_api import sync_playwright
            out["playwright_installed"] = True
        except Exception as e:                                   # noqa: BLE001
            out["playwright_installed"] = False
            out["error"] = str(e)[:200]
            _print(out)
            return 2
        out["profile_exists"] = cfg.profile_dir.exists()
        try:
            out["profile_mode"] = oct(cfg.profile_dir.stat().st_mode & 0o777)
        except OSError:
            out["profile_mode"] = None
        out["profile_outside_repo"] = not cfg.profile_inside_repo(Path.cwd())
        out["downloads_writable"] = os.access(cfg.downloads_dir, os.W_OK)
        try:
            with ChatGPTImageAdapter(cfg) as ad:
                out.update(ad.health())
        except Exception as e:                                   # noqa: BLE001
            out["chromium_error"] = str(e)[:300]
        out["passed"] = bool(out.get("playwright_installed") and out.get("reachable")
                             and out.get("signed_in") and out.get("composer_strategy")
                             and out.get("file_input_strategy") and out.get("downloads_writable"))
        _print(out)
        return 0 if out["passed"] else 2

    if cmd in ("generate", "resume"):
        runner = QueueRunner(Path(args.project), Path(args.queue), cfg,
                             expect_ratio=_aspect(args))
        added = runner.seed()
        if getattr(args, "new_conversation", False):
            # Drop the stored chat so open_conversation lands on the ChatGPT
            # Project page and the first submission creates a fresh
            # conversation. Any job that was mid-flight in the OLD chat is
            # rewound to queued: its turn marker refers to a conversation we
            # are no longer in, so recovering from it would read the wrong turn.
            rewound = runner.reset_for_new_conversation()
            _print({"new_conversation": True, "rewound_jobs": rewound})
        batch = int(getattr(args, "batch", 0) or 0)
        if batch > 1:
            res = runner.run_batched(size=batch, limit=getattr(args, "limit", None),
                                     only=getattr(args, "only", None))
        else:
            res = runner.run(limit=getattr(args, "limit", None), resume=(cmd == "resume"),
                             only=getattr(args, "only", None))
        _print({"command": cmd, "seeded": added, **res,
                "by_state": runner.store.by_state(),
                "conversation_url": runner.store.doc.get("conversation_url")})
        return 0 if not res.get("blocked") else 3

    return 1
