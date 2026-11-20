"""Fast Flow clip generation: submit every beat back-to-back, harvest through Flow's media API.

Per beat the only UI work is: attach frame(s) from the project's uploads, fill the prompt, set the
duration, check the UI price, click once. We do NOT wait for the render before submitting the next
beat - Flow renders them concurrently. Completion, binding and download come from the Zzl0ze media
list (exact: each video records the uploaded start-frame filename) and the =m22 MP4 URL.
Guards: Agent mode off, settings chip, frame count, prompt landed, price == plan, total <= cap.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path

from studio_os.flow import api as FAPI
from studio_os.flow.config import FlowConfig
from studio_os.flow.generate import FlowGenerator, GuardStop, _prompt
from studio_os.flow.selectors import PRICE_720P_X1
from studio_os.flow.session import flow_session


def _log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def _submit_one(gen: FlowGenerator, page, beat: dict, dry_run: bool) -> dict:
    bid = beat["id"]
    sb = gen.project / "05-visuals/storyboards"
    end_id = beat["transition"].split(":", 1)[1] if beat["transition"].startswith("first_last:") else None
    if page.get_by_role("button", name="Agent", exact=True).get_attribute("aria-pressed") != "false":
        gen._stop(page, bid, "Agent mode is on")
    while page.get_by_role("button", name="Image ingredient").count():
        page.get_by_role("button", name="Image ingredient").first.click()
        page.wait_for_timeout(600)
    chip = page.get_by_role("button", name="Settings trigger").inner_text()
    aspect = os.environ.get("FACELESS_FLOW_ASPECT", "9_16")   # 16_9 for landscape films (set the composer to match first)
    if not all(k in chip for k in ("Video", "720p", aspect, "x1")):
        gen._stop(page, bid, f"settings chip unexpected: {chip!r}")
    gen._attach(page, "Start", sb / f"{bid}.png", bid)
    if end_id:
        gen._attach(page, "End", sb / f"{end_id}.png", bid)
    want = 2 if end_id else 1
    if page.get_by_role("button", name="Image ingredient").count() != want:
        gen._stop(page, bid, "frame count wrong")
    prompt = _prompt(beat, bool(end_id))
    box = page.locator('[contenteditable="true"]:visible')
    if box.count() != 1:
        gen._stop(page, bid, f"{box.count()} visible prompt editors")
    box.first.click()
    box.first.fill(prompt)
    page.wait_for_timeout(400)
    if len(box.first.inner_text().strip()) < len(prompt) * 0.9:
        gen._stop(page, bid, "prompt did not land whole")
    expected = PRICE_720P_X1[beat["clip_s"]]
    price = gen._set_duration(page, beat["clip_s"], bid)
    if price != f"{expected} credits":
        gen._stop(page, bid, f"price {price!r} != {expected} credits")
    if page.get_by_role("button", name="Image ingredient").count() != want:
        gen._stop(page, bid, "frames detached while changing duration")
    if dry_run:
        return {"beat": bid, "credits": expected, "dry_run": True}
    page.get_by_role("button", name="Start generation").click()
    # accepted = the composer resets (frames and prompt cleared)
    for _ in range(40):
        page.wait_for_timeout(500)
        if page.get_by_role("button", name="Image ingredient").count() == 0:
            break
    else:
        gen._stop(page, bid, "submission not accepted (frames still attached)")
    return {"beat": bid, "credits": expected, "submitted_at": time.time()}


def preupload(gen: FlowGenerator, page, files: list[Path], known_names: set) -> int:
    """Upload every frame Flow does not have yet in ONE file-chooser action."""
    missing = [f for f in files if f.name not in known_names]
    if not missing:
        return 0
    page.get_by_role("button", name="Start", exact=True).click()
    page.wait_for_timeout(3000)
    with page.expect_file_chooser() as fc:
        page.get_by_role("button", name="Upload media").click()
    fc.value.set_files([str(f) for f in missing])
    page.wait_for_timeout(2500)
    agree = page.get_by_role("button", name="I agree")          # approved by the account owner
    if agree.count():
        agree.click()
    for _ in range(120):
        page.wait_for_timeout(1500)
        if not page.get_by_role("option").filter(has_text="Uploading").count():
            break
    page.keyboard.press("Escape")
    page.wait_for_timeout(1200)
    return len(missing)


def run(project: Path, beats: list[str] | None, credit_cap: int, dry_run: bool = False,
        harvest_timeout_s: int = 1500) -> dict:
    gen = FlowGenerator(Path(project))
    plan_beats = {b["id"]: b for b in gen.plan["beats"]}
    ids = beats or list(plan_beats)
    todo = [plan_beats[b] for b in ids]
    planned = sum(PRICE_720P_X1[b["clip_s"]] for b in todo)
    if planned > credit_cap:
        raise GuardStop(f"planned {planned} credits > cap {credit_cap}")
    t_run = time.time()
    subs = []
    with flow_session(gen.cfg) as (_, page):
        st = FAPI.project_state(gen.cfg, page)             # also loads the project page
        start_credits = st["credits"]
        _log(f"credits {start_credits}; planned {planned} for {len(todo)} clips; dry_run={dry_run}")
        if start_credits is not None and start_credits < planned:
            raise GuardStop(f"only {start_credits} credits for a {planned}-credit plan")
        frames = sorted({gen.project / "05-visuals/storyboards" / f"{x}.png" for b in todo
                         for x in [b["id"]] + ([b["transition"].split(":", 1)[1]]
                                               if b["transition"].startswith("first_last:") else [])})
        n_up = preupload(gen, page, frames, {str(n) for n in st["names"].values()})
        _log(f"pre-uploaded {n_up} new frame(s)")
        spent = 0
        for b in todo:
            if spent + PRICE_720P_X1[b["clip_s"]] > credit_cap:
                raise GuardStop(f"credit cap {credit_cap} reached")
            rec = _submit_one(gen, page, b, dry_run)
            spent += rec["credits"]
            subs.append(rec)
            _log(f"{'checked' if dry_run else 'submitted'} {b['id']} ({rec['credits']} cr)")
        if dry_run:
            return {"dry_run": True, "checked": [s["beat"] for s in subs], "planned": planned,
                    "credits": start_credits, "seconds": round(time.time() - t_run)}

        # ---- harvest through the media API (no clicks)
        want = {s["beat"] for s in subs}
        got: dict = {}
        deadline = time.time() + harvest_timeout_s
        while want - set(got) and time.time() < deadline:
            page.wait_for_timeout(15000)
            st = FAPI.project_state(gen.cfg, page)
            for v in sorted(st["videos"], key=lambda v: v["created"] or 0):
                beat = Path(v["start"] or "").stem
                if beat in want and beat not in got and (v["created"] or 0) >= t_run - 30:
                    try:                                   # big clips can stall past the 30s default; retry next poll
                        r = page.request.get(v["url"] + FAPI.VIDEO_SUFFIX, timeout=180000)
                    except Exception as e:  # noqa: BLE001
                        _log(f"download {beat} failed, will retry: {str(e)[:80]}")
                        continue
                    if r.status == 200 and "video" in (r.headers.get("content-type") or ""):
                        out = gen.clips / f"{beat}_v1.mp4"
                        if out.exists():
                            out = gen.clips / f"{beat}_v{len(list(gen.clips.glob(beat + '_v*.mp4'))) + 1}.mp4"
                        out.write_bytes(r.body())
                        got[beat] = {"beat": beat, "file": str(out.relative_to(gen.project)),
                                     "media_id": v["media_id"], "model": v["model"], "start": v["start"],
                                     "end": v["end"], "sha256": hashlib.sha256(r.body()).hexdigest(),
                                     "status": "downloaded_api", "at": datetime.now().isoformat(timespec="seconds")}
                        _log(f"downloaded {beat} ({len(got)}/{len(want)})")
            _log(f"waiting on {sorted(want - set(got))}")
        end_credits = FAPI.project_state(gen.cfg, page)["credits"]
    gen.ledger["clips"].extend(got.values())
    summary = {"start_credits": start_credits, "end_credits": end_credits, "planned": planned,
               "charged": (start_credits - end_credits) if start_credits is not None and end_credits is not None else None,
               "downloaded": sorted(got), "missing": sorted(want - set(got)),
               "seconds": round(time.time() - t_run)}
    gen.ledger.setdefault("runs", []).append(summary | {"mode": "fast", "at": datetime.now().isoformat(timespec="seconds")})
    gen._save_ledger()
    return summary
