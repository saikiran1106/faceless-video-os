"""Free, real proof captures for tech reels: GitHub repo pages (dark mode) + metadata.

  python -m studio_os.cli fast capture --project P --repo owner/name [--repo ...] [--url https://...]

Writes <project>/03-references/screens/<slug>/:
  header.png       repo header + description + star/fork counts (what viewers recognise)
  readme_top.png   first screen of the README
  readme_full.png  the whole README (tall; TechReel pans it)
  meta.json        stars, forks, license, description, pushed_at, captured_at (GitHub API)
Public pages only, anonymous browser context, no login, nothing posted.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

VIEW_W, VIEW_H = 900, 1600          # narrow viewport: GitHub stacks into a phone-friendly column; scale 2 = crisp


def _gh_meta(repo: str) -> dict:
    try:
        out = subprocess.run(["gh", "api", f"repos/{repo}"], capture_output=True, text=True, timeout=30)
        d = json.loads(out.stdout)
        return {"full_name": d.get("full_name"), "stars": d.get("stargazers_count"), "forks": d.get("forks_count"),
                "license": (d.get("license") or {}).get("spdx_id"), "language": d.get("language"),
                "description": d.get("description"), "pushed_at": d.get("pushed_at")}
    except Exception as e:  # noqa: BLE001
        return {"full_name": repo, "error": str(e)[:120]}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def capture_repo(project: Path, repo: str) -> dict:
    from playwright.sync_api import sync_playwright

    out = Path(project) / "03-references" / "screens" / _slug(repo)
    out.mkdir(parents=True, exist_ok=True)
    meta = _gh_meta(repo)
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": VIEW_W, "height": VIEW_H}, device_scale_factor=2, color_scheme="dark")
        page = ctx.new_page()
        page.goto(f"https://github.com/{repo}", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        for sel in ("[data-testid='cookie-consent-banner'] button", "button:has-text('Reject')"):
            try:
                if page.locator(sel).count():
                    page.locator(sel).first.click(timeout=2000)
            except Exception:  # noqa: BLE001
                pass
        shots = {}
        header = page.locator("#repository-container-header").first
        if header.count():
            header.screenshot(path=str(out / "header.png"))
            shots["header"] = "header.png"
        readme = page.locator("article.markdown-body").first
        if readme.count():
            readme.screenshot(path=str(out / "readme_full.png"))
            shots["readme_full"] = "readme_full.png"
            readme.scroll_into_view_if_needed()
            page.wait_for_timeout(800)
            box = readme.bounding_box()
            page.screenshot(path=str(out / "readme_top.png"),
                            clip={"x": box["x"], "y": box["y"], "width": box["width"], "height": min(box["height"], VIEW_H - 40)})
            shots["readme_top"] = "readme_top.png"
        b.close()
    rec = {**meta, "url": f"https://github.com/{repo}", "shots": shots, "captured_at": datetime.now().isoformat(timespec="seconds")}
    (out / "meta.json").write_text(json.dumps(rec, indent=1))
    return rec


def capture_url(project: Path, url: str, name: str | None = None) -> dict:
    from playwright.sync_api import sync_playwright

    out = Path(project) / "03-references" / "screens" / _slug(name or url)
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        page = b.new_context(viewport={"width": VIEW_W, "height": VIEW_H}, device_scale_factor=2, color_scheme="dark").new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        page.screenshot(path=str(out / "page_top.png"))
        page.screenshot(path=str(out / "page_full.png"), full_page=True)
        b.close()
    rec = {"url": url, "shots": {"page_top": "page_top.png", "page_full": "page_full.png"},
           "captured_at": datetime.now().isoformat(timespec="seconds")}
    (out / "meta.json").write_text(json.dumps(rec, indent=1))
    return rec
