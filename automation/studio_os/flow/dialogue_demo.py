"""Guarded, single-clip Google Flow Ingredients dialogue proof.

Only the final Start generation click spends credits. Dry-run uploads the visual
reference, attaches one voice, validates live settings/price, and saves a receipt.
A timeout after submission never resubmits: rerun in inspect/harvest mode instead.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from urllib.parse import urlparse
from datetime import datetime, timezone
from pathlib import Path

from .config import FlowConfig
from .session import flow_session
from . import api as flow_api


class DemoGuardStop(RuntimeError):
    pass


def _download_video(page, url: str) -> tuple[bytes | None, list[dict]]:
    attempts = []
    for candidate in (url + flow_api.VIDEO_SUFFIX, url, url + "=m18"):
        response = page.request.get(candidate, timeout=180000)
        body = response.body()
        mime = response.headers.get("content-type") or ""
        attempts.append({"status": response.status, "mime": mime, "bytes": len(body),
                         "host": urlparse(candidate).hostname,
                         "path_tail": urlparse(candidate).path[-45:]})
        if response.status == 200 and ("video" in mime or body[4:8] == b"ftyp"):
            return body, attempts
    return None, attempts


def _snapshot(page, out_dir: Path, label: str) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{label}_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.png"
    page.screenshot(path=str(path))
    return str(path)


def _dismiss_overlay(page):
    page.keyboard.press("Escape")
    backdrop = page.locator(".cdk-overlay-backdrop")
    if backdrop.count():
        backdrop.first.click(force=True)
    page.wait_for_timeout(400)


def _credits(page) -> int | None:
    page.get_by_role("button", name="Account details").click()
    page.wait_for_timeout(700)
    text = page.locator("body").inner_text()
    m = re.search(r"([\d,]+)\s+Google Flow credits", text)
    _dismiss_overlay(page)
    return int(m.group(1).replace(",", "")) if m else None


def _settings(page, seconds: int) -> int:
    page.get_by_role("button", name="Settings trigger").click()
    for label in ("Video", "Ingredients", "16:9", "720p", f"{seconds}s", "x1"):
        opt = page.get_by_role("radio", name=label, exact=True)
        if opt.count() != 1:
            raise DemoGuardStop(f"setting {label} unavailable")
        if opt.get_attribute("aria-checked") != "true":
            opt.click()
            page.wait_for_timeout(350)
    model = page.get_by_role("button", name="Select model family").inner_text()
    if "Omni 1.1 Flash" not in model:
        raise DemoGuardStop(f"wrong model: {model!r}")
    link = page.locator("a").filter(has_text=re.compile(r"^\s*\d+\s+credits\s*$"))
    if link.count() != 1:
        raise DemoGuardStop("numeric price missing")
    price = int(re.search(r"\d+", link.inner_text()).group())
    _dismiss_overlay(page)
    chip = page.get_by_role("button", name="Settings trigger").inner_text()
    if not all(s in chip for s in ("Video", "720p", f"{seconds}s", "crop_16_9", "x1")):
        raise DemoGuardStop(f"settings chip mismatch: {chip!r}")
    return price


def _add_image(page, image: Path):
    page.get_by_role("button", name="Add ingredients to the prompt box").click()
    page.wait_for_timeout(500)
    opt = page.get_by_role("option").filter(has_text=image.name)
    if not opt.count():
        with page.expect_file_chooser() as chooser:
            page.get_by_role("button", name="Upload media").click()
        chooser.value.set_files(str(image))
        page.wait_for_timeout(1800)
        agree = page.get_by_role("button", name="I agree")
        if agree.count():
            agree.click()
    for _ in range(60):
        opt = page.get_by_role("option").filter(has_text=image.name)
        if opt.count() and "Uploading" not in opt.first.inner_text():
            break
        page.wait_for_timeout(1000)
    else:
        raise DemoGuardStop(f"image upload unavailable: {image.name}")
    opt.first.click()
    page.wait_for_timeout(800)
    add = page.get_by_role("button", name="Add to prompt")
    if add.count() and add.first.is_visible():
        add.first.click()
    page.wait_for_timeout(650)
    if page.get_by_role("button", name="Add ingredients to the prompt box").count():
        # Some picker versions stay open after addition.
        _dismiss_overlay(page)


def _add_voice(page, voice: str):
    page.get_by_role("button", name="Add ingredients to the prompt box").click()
    page.get_by_role("tab", name=re.compile("Voices")).click()
    page.wait_for_timeout(600)
    chosen = page.get_by_text(voice, exact=True)
    if not chosen.count():
        raise DemoGuardStop(f"voice {voice!r} not present")
    chosen.first.click()
    page.wait_for_timeout(500)
    page.get_by_role("button", name="Add to prompt").click()
    page.wait_for_timeout(650)
    _dismiss_overlay(page)


def run(*, project_url: str, image: Path, prompt_file: Path, voice: str, expected_line: str, seconds: int,
        credit_cap: int, output: Path, dry_run: bool = True) -> dict:
    if seconds not in (4, 6, 8, 10):
        raise DemoGuardStop("unsupported clip duration")
    if not image.is_file():
        raise DemoGuardStop(f"image missing: {image}")
    prompt = prompt_file.read_text(encoding="utf-8").strip()
    if not prompt or expected_line not in prompt:
        raise DemoGuardStop("approved proof line is absent from prompt")
    cfg = FlowConfig().ensure_dirs()
    cfg.project_url = project_url
    out_dir = output.parent
    with flow_session(cfg) as (_, page):
        page.goto(project_url, wait_until="domcontentloaded")
        page.wait_for_timeout(8000)
        if page.get_by_role("button", name="Agent", exact=True).get_attribute("aria-pressed") != "false":
            raise DemoGuardStop("Agent mode enabled")
        before = _credits(page)
        price = _settings(page, seconds)
        if price > credit_cap or before is None or before < price:
            raise DemoGuardStop(f"balance/price/cap: balance={before}, price={price}, cap={credit_cap}")
        box = page.locator('[contenteditable="true"]:visible')
        if box.count() != 1:
            raise DemoGuardStop(f"prompt editors: {box.count()}")
        box.first.fill(prompt)
        _add_image(page, image)
        _add_voice(page, voice)
        landed = box.first.inner_text()
        if expected_line not in landed:
            raise DemoGuardStop("exact proof line did not remain in prompt")
        screenshot = _snapshot(page, out_dir, "flow_dialogue_ready")
        receipt = {"project_url": project_url, "image": str(image), "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                   "prompt_file": str(prompt_file), "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                   "voice": voice, "expected_line": expected_line,
                   "model": "Omni 1.1 Flash", "mode": "Ingredients", "aspect": "16:9",
                   "resolution": "720p", "seconds": seconds, "balance_before": before, "ui_price": price,
                   "credit_cap": credit_cap, "ready_screenshot": screenshot, "status": "dry_run_ready"}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        if dry_run:
            return receipt
        if page.get_by_role("button", name="Start generation").count() != 1:
            raise DemoGuardStop("Start generation button missing")
        failures = []
        def on_response(response):
            if response.status >= 400 and "flow.google.com" in response.url:
                failures.append({"status": response.status, "path": response.url.split("?")[0][-120:]})
        page.on("response", on_response)
        page.get_by_role("button", name="Start generation").click()
        receipt["status"] = "generation_click_attempted"
        receipt["submitted_at"] = datetime.now(timezone.utc).isoformat()
        output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        page.wait_for_timeout(8000)
        receipt["after_click_screenshot"] = _snapshot(page, out_dir, "flow_dialogue_after_click")
        receipt["after_click_text_tail"] = page.locator("body").inner_text()[-1200:]
        receipt["response_failures"] = failures
        output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        # Keep the originating Flow page open while it runs; navigation during
        # early progress may cancel a client-side pending generation card.
        receipt["progress_samples"] = []
        deadline = time.time() + 600
        while time.time() < deadline:
            page.wait_for_timeout(15000)
            body = page.locator("body").inner_text()
            progress = re.findall(r"\b\d+%", body)
            receipt["progress_samples"].append({"at": datetime.now(timezone.utc).isoformat(),
                                                 "progress": progress[-3:], "tail": body[-350:]})
            output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
            if len(receipt["progress_samples"]) % 4 == 0:
                receipt["progress_screenshot"] = _snapshot(page, out_dir, "flow_dialogue_progress")
            if not progress and len(receipt["progress_samples"]) > 2:
                break
        state = flow_api.project_state(cfg, page)
        receipt["balance_after"] = state["credits"]
        receipt["matching_records"] = [{"media_id": v["media_id"], "has_url": bool(v.get("url"))}
                                       for v in state["videos"] if expected_line in (v.get("prompt") or "")]
        for v in reversed(state["videos"]):
            if expected_line not in (v.get("prompt") or "") or not v.get("url"):
                continue
            video_body, attempts = _download_video(page, v["url"])
            receipt["download_attempts"] = attempts
            if video_body is not None:
                clip = output.with_suffix(".mp4")
                clip.write_bytes(video_body)
                receipt.update({"status": "downloaded", "clip": str(clip),
                                "clip_sha256": hashlib.sha256(video_body).hexdigest(),
                                "media_id": v["media_id"],
                                "charged_credits": before - state["credits"] if state["credits"] is not None else None})
                output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
                return receipt
        receipt["status"] = "submitted_not_harvested"
        output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        return receipt


def harvest_submitted(*, output: Path) -> dict:
    """Recover one previously submitted proof without touching generation controls."""
    receipt = json.loads(output.read_text(encoding="utf-8"))
    expected_line = receipt.get("expected_line", "ఆ తలుపు తెరిచే వరకూ దీన్ని ఆరనివ్వను.")
    if receipt.get("status") not in ("submitted", "submitted_not_harvested", "generation_click_attempted", "downloaded"):
        raise DemoGuardStop(f"receipt is not pending: {receipt.get('status')}")
    cfg = FlowConfig().ensure_dirs()
    cfg.project_url = receipt["project_url"]
    with flow_session(cfg) as (_, page):
        state = flow_api.project_state(cfg, page)
        receipt["project_state_summary"] = {"video_count": len(state["videos"]),
                                             "names_count": len(state["names"]),
                                             "prompts": [(v.get("prompt") or "")[:200] for v in state["videos"][-5:]],
                                             "page_url": page.url,
                                             "page_text_tail": page.locator("body").inner_text()[-1500:]}
        receipt["inspection_screenshot"] = _snapshot(page, output.parent, "flow_dialogue_inspect")
        matches = [v for v in state["videos"] if expected_line in (v.get("prompt") or "")]
        receipt["matching_records"] = [{"media_id": v["media_id"], "has_url": bool(v.get("url")),
                                         "model": v.get("model")} for v in matches]
        balance_after = state["credits"] if state["credits"] is not None else _credits(page)
        receipt["balance_after"] = balance_after
        receipt["charged_credits"] = (receipt["balance_before"] - balance_after
                                      if balance_after is not None else None)
        for v in reversed(matches):
            if not v.get("url"):
                continue
            video_body, attempts = _download_video(page, v["url"])
            receipt["download_attempts"] = attempts
            if video_body is None:
                continue
            clip = output.with_suffix(".mp4")
            if not clip.exists() or len(video_body) > clip.stat().st_size:
                clip.write_bytes(video_body)
            saved_body = clip.read_bytes()
            receipt.update({"status": "downloaded", "clip": str(clip),
                            "clip_sha256": hashlib.sha256(saved_body).hexdigest(),
                            "media_id": v["media_id"]})
            break
        output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        return receipt
