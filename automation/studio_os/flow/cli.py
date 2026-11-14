"""`studio_os flow ...` subcommands: setup (one-time manual sign-in) and doctor (read-only UI survey)."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import FlowConfig
from .session import flow_session, signed_in


# Read-only survey of the controls on the page, used to write selectors from the live UI.
SURVEY_JS = r"""
() => {
  const out = [];
  const els = document.querySelectorAll('button, [role=button], [role=menuitem], [role=option], [role=tab], [role=combobox], input, textarea, [contenteditable=true], select, a[href]');
  for (const el of els) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    out.push({tag: el.tagName.toLowerCase(), role: el.getAttribute('role'), aria: el.getAttribute('aria-label'),
              text: (el.innerText || el.value || '').trim().slice(0, 80), placeholder: el.getAttribute('placeholder'),
              type: el.getAttribute('type'), testid: el.getAttribute('data-testid'), id: el.id || null,
              x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)});
  }
  return out;
}
"""


def add_parser(sub):
    p = sub.add_parser("flow", help="Google Flow (Omni Flash) browser adapter")
    fs = p.add_subparsers(dest="flow_cmd", required=True)
    s = fs.add_parser("setup", help="open a headed window for one-time manual Google sign-in")
    s.add_argument("--wait", type=int, default=1800)
    g = fs.add_parser("generate", help="generate beat clips from 05-visuals/shot_plan.json (PAID)")
    g.add_argument("--project", required=True)
    g.add_argument("--beats", nargs="+", required=True)
    g.add_argument("--credit-cap", type=int, required=True, help="hard stop; owner-approved credit budget")
    h = fs.add_parser("harvest", help="download generated clips missing from the ledger (free)")
    h.add_argument("--project", required=True)
    d = fs.add_parser("doctor", help="open the project and survey the UI without generating anything")
    d.add_argument("--settle", type=int, default=8)
    n = fs.add_parser("new-project", help="create a named Flow project through the signed-in UI")
    n.add_argument("--name", required=True)
    n.add_argument("--output", required=True, help="JSON receipt path")
    i = fs.add_parser("inspect-composer", help="read-only survey of the live composer and settings")
    i.add_argument("--output", required=True, help="JSON survey path")
    v = fs.add_parser("inspect-voices", help="read-only survey of Ingredients and voice controls")
    v.add_argument("--output", required=True, help="JSON survey path")
    proof = fs.add_parser("dialogue-demo", help="guarded single-clip non-English Ingredients/voice proof")
    proof.add_argument("--project-url", required=True)
    proof.add_argument("--image", required=True)
    proof.add_argument("--prompt-file", required=True)
    proof.add_argument("--voice", required=True)
    proof.add_argument("--expected-line", default="ఆ తలుపు తెరిచే వరకూ దీన్ని ఆరనివ్వను.")
    proof.add_argument("--seconds", type=int, default=6)
    proof.add_argument("--credit-cap", type=int, required=True)
    proof.add_argument("--output", required=True)
    proof.add_argument("--dry-run", action="store_true")
    recovery = fs.add_parser("dialogue-harvest", help="recover a submitted dialogue proof without generating")
    recovery.add_argument("--output", required=True, help="existing submitted receipt path")
    return p


def _print(o):
    print(json.dumps(o, ensure_ascii=False, indent=1))


def handle(args) -> int:
    if args.flow_cmd == "dialogue-harvest":
        from .dialogue_demo import harvest_submitted
        _print(harvest_submitted(output=Path(args.output)))
        return 0
    if args.flow_cmd == "dialogue-demo":
        from .dialogue_demo import run
        _print(run(project_url=args.project_url, image=Path(args.image),
                   prompt_file=Path(args.prompt_file), voice=args.voice, expected_line=args.expected_line,
                   seconds=args.seconds, credit_cap=args.credit_cap,
                   output=Path(args.output), dry_run=args.dry_run))
        return 0
    cfg = FlowConfig().ensure_dirs()
    if args.flow_cmd == "setup":
        with flow_session(cfg) as (_, page):
            page.goto(cfg.project_url, wait_until="domcontentloaded")
            print("Sign in to the Google account that owns the Flow project, open the project so you "
                  "see its workspace, then CLOSE THE WINDOW. The session is saved when you close it.")
            try:
                page.wait_for_event("close", timeout=args.wait * 1000)
            except Exception:  # noqa: BLE001 - timeout: fall through and report
                pass
            _print({"window_closed": page.is_closed(), "profile": str(cfg.profile_dir),
                    "next": "python -m studio_os.cli flow doctor"})
            return 0
    if args.flow_cmd == "generate":
        from .generate import FlowGenerator
        _print(FlowGenerator(Path(args.project), cfg).run(args.beats, args.credit_cap))
        return 0
    if args.flow_cmd == "harvest":
        from .generate import harvest
        _print(harvest(Path(args.project), cfg))
        return 0
    if args.flow_cmd == "doctor":
        with flow_session(cfg) as (_, page):
            page.goto(cfg.project_url, wait_until="domcontentloaded")
            time.sleep(max(args.settle, 8))      # outlast Flow's delayed sign-in redirect
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            shot = cfg.diagnostics_dir / f"doctor_{stamp}.png"
            page.screenshot(path=str(shot), full_page=False)
            controls = page.evaluate(SURVEY_JS) if signed_in(page) else []
            report = {"signed_in": signed_in(page), "url": page.url, "title": page.title(),
                      "screenshot": str(shot), "controls": controls, "config": cfg.describe()}
            out = cfg.diagnostics_dir / f"doctor_{stamp}.json"
            out.write_text(json.dumps(report, ensure_ascii=False, indent=1))
            _print({k: v for k, v in report.items() if k != "controls"} | {"controls_found": len(controls), "report": str(out)})
            return 0 if report["signed_in"] else 2
    if args.flow_cmd == "new-project":
        with flow_session(cfg) as (_, page):
            page.goto("https://flow.google.com/", wait_until="domcontentloaded")
            page.get_by_text("New project", exact=True).wait_for(timeout=cfg.nav_timeout_s * 1000)
            page.get_by_text("New project", exact=True).click()
            page.wait_for_url("https://flow.google.com/project/*", timeout=cfg.nav_timeout_s * 1000)
            title = page.get_by_role("textbox", name="Editable text")
            title.fill(args.name)
            title.press("Enter")
            page.wait_for_timeout(1200)
            receipt = {"name": args.name, "url": page.url, "title": page.title(),
                       "profile": str(cfg.profile_dir), "created_via": "Flow UI"}
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
            _print(receipt)
            return 0
    if args.flow_cmd == "inspect-composer":
        with flow_session(cfg) as (_, page):
            page.goto(cfg.project_url, wait_until="domcontentloaded")
            page.wait_for_timeout(8000)
            page.get_by_role("button", name="Account details").click()
            page.wait_for_timeout(1000)
            account_text = page.locator("body").inner_text()
            page.keyboard.press("Escape")
            backdrop = page.locator(".cdk-overlay-backdrop")
            if backdrop.count():
                backdrop.first.click(force=True)
                page.wait_for_timeout(500)
            page.get_by_role("button", name="Settings trigger").click()
            page.wait_for_timeout(1000)
            settings = page.evaluate(SURVEY_JS)
            shot = cfg.diagnostics_dir / f"composer_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.png"
            page.screenshot(path=str(shot))
            credit_match = re.search(r"([\d,]+)\s+Google Flow credits", account_text)
            report = {"url": page.url, "settings": settings,
                      "credits": int(credit_match.group(1).replace(",", "")) if credit_match else None,
                      "screenshot": str(shot)}
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            _print({"url": report["url"], "credits": report["credits"],
                    "screenshot": str(shot), "report": str(out), "controls": len(settings)})
            return 0
    if args.flow_cmd == "inspect-voices":
        with flow_session(cfg) as (_, page):
            page.goto(cfg.project_url, wait_until="domcontentloaded")
            page.wait_for_timeout(8000)
            page.get_by_role("button", name="Settings trigger").click()
            for label in ("Video", "Ingredients", "16:9", "720p", "6s", "x1"):
                option = page.get_by_role("radio", name=label, exact=True)
                if option.get_attribute("aria-checked") != "true":
                    option.click()
                    page.wait_for_timeout(400)
            model = page.get_by_role("button", name="Select model family").inner_text()
            price = page.locator("a").filter(has_text=re.compile(r"^\s*\d+\s+credits\s*$"))
            price_text = price.first.inner_text().strip() if price.count() else None
            page.keyboard.press("Escape")
            backdrop = page.locator(".cdk-overlay-backdrop")
            if backdrop.count():
                backdrop.first.click(force=True)
            page.get_by_role("button", name="Add ingredients to the prompt box").click()
            page.wait_for_timeout(800)
            page.get_by_role("tab", name=re.compile("Voices")).click()
            page.wait_for_timeout(1200)
            controls = page.evaluate(SURVEY_JS)
            shot = cfg.diagnostics_dir / f"voices_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.png"
            page.screenshot(path=str(shot))
            report = {"url": page.url, "model": model, "price": price_text,
                      "settings_chip": page.get_by_role("button", name="Settings trigger").inner_text(),
                      "controls": controls, "screenshot": str(shot)}
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            _print({k: v for k, v in report.items() if k != "controls"} | {"controls_found": len(controls)})
            return 0
    return 1
