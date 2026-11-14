"""Generate beat clips in Google Flow (NORMAL mode, Omni 1.1 Flash, Frames) from a shot plan.

Every step was verified by hand on clip 1 of projects/chatgpt-dots-tech-reel (2026-09-30).
Guards before each paid click: Agent chip off, settings chip = Video/720p/9:16/x1, the frame
ingredients attached exactly as planned, the prompt landed whole, and the UI price equals the
expected price. Any guard failure stops the run. A timeout never resubmits.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path

from .config import FlowConfig
from .selectors import PRICE_720P_X1
from .session import flow_session

PROGRESS_JS = r"""() => [...document.querySelectorAll('body *')].filter(e => e.children.length === 0
                    && /^\d{1,3}%$/.test((e.textContent || '').trim())).length"""
VIDEO_SRC_JS = "() => { const v = document.querySelector('video'); return v ? (v.currentSrc || v.src) : null; }"


class GuardStop(RuntimeError):
    pass


def _prompt(beat: dict, has_end: bool) -> str:
    # Project-scoped, reviewed prompts must take precedence over the legacy
    # tech-reel template below. Other projects use this adapter too.
    if beat.get("prompt"):
        return beat["prompt"].strip()
    frames = ("Start frame: the first attached image. End frame: the second attached image; transform "
              "smoothly and continuously from the start frame into the end frame."
              if has_end else
              "Start frame: the attached image. Preserve its exact composition, colours, lighting and every "
              "object in it.")
    return (f"{frames} Single continuous shot.\nMotion: {beat['motion']}\n"
            f"Camera: {beat['camera']}, smooth and stabilised, 35mm lens feel.\n"
            "Style: premium glossy 3D tech-explainer render, same look as the start frame, clean surfaces "
            "without any text or logos. The glass orb character keeps its exact round shape and two oval eyes.\n"
            "Audio: soft ambient room tone only.")


class FlowGenerator:
    def __init__(self, project: Path, cfg: FlowConfig | None = None):
        self.project = Path(project)
        self.cfg = (cfg or FlowConfig()).ensure_dirs()
        self.plan = json.loads((self.project / "05-visuals/shot_plan.json").read_text())
        if self.plan.get("flow_project_url"):
            self.cfg.project_url = self.plan["flow_project_url"]
        self.clips = self.project / "06-video/clips"
        self.clips.mkdir(parents=True, exist_ok=True)
        self.ledger_path = self.clips / "flow_ledger.json"
        self.ledger = (json.loads(self.ledger_path.read_text()) if self.ledger_path.exists()
                       else {"project_url": self.cfg.project_url, "clips": []})

    # ------------------------------------------------------------ helpers
    def _save_ledger(self):
        self.ledger_path.write_text(json.dumps(self.ledger, indent=1))

    def _shot(self, page, name):
        page.screenshot(path=str(self.cfg.diagnostics_dir / f"gen_{name}.png"))

    def _stop(self, page, beat, why):
        self._shot(page, f"{beat}_STOP")
        raise GuardStop(f"{beat}: {why}")

    def _open(self, page):
        page.goto(self.cfg.project_url, wait_until="domcontentloaded")
        page.wait_for_timeout(9000)

    def credits(self, page) -> int | None:
        page.get_by_role("button", name="Account details").click()
        page.wait_for_timeout(2000)
        m = re.search(r"([\d,]+)\s+Google Flow credits", page.locator("body").inner_text())
        page.keyboard.press("Escape")
        page.wait_for_timeout(800)
        bd = page.locator(".cdk-overlay-backdrop")
        if bd.count():
            bd.first.click(force=True)
            page.wait_for_timeout(800)
        return int(m.group(1).replace(",", "")) if m else None

    def _attach(self, page, slot: str, image: Path, beat: str):
        # Flow's 2026-10 UI exposes image references through the prompt's
        # ingredient picker; older workspaces still expose Start/End slots.
        legacy = page.get_by_role("button", name=slot, exact=True).count() > 0
        if slot == "End" and not legacy:
            self._stop(page, beat, "End-frame binding is unavailable in the current Flow picker")
        before = page.get_by_role("button", name="Image ingredient" if legacy else "Ingredient", exact=True).count()
        if legacy:
            page.get_by_role("button", name=slot, exact=True).click()
        else:
            page.get_by_role("button", name="Add ingredients to the prompt box").click()
        page.wait_for_timeout(3500)
        opt = page.get_by_role("option").filter(has_text=image.name)
        if not opt.count():
            with page.expect_file_chooser() as fc:
                page.get_by_role("button", name="Upload media").click()
            fc.value.set_files(str(image))
            page.wait_for_timeout(3000)
            agree = page.get_by_role("button", name="I agree")      # approved by the account owner
            if agree.count():
                agree.click()
        for _ in range(60):
            opt = page.get_by_role("option").filter(has_text=image.name)
            if opt.count() and "Uploading" not in opt.first.inner_text():
                break
            page.wait_for_timeout(2000)
        else:
            self._stop(page, beat, f"{image.name} never finished uploading")
        opt.first.click()
        page.wait_for_timeout(2500)
        # The picker sometimes closes on selection (clip 1) and sometimes stays open with an
        # "Add to prompt" button (clip 2). Handle both, then prove the frame attached.
        add = page.get_by_role("button", name="Add to prompt")
        if add.count() and add.first.is_visible():
            add.first.click()
            page.wait_for_timeout(2000)
        if legacy and page.get_by_text("Select a frame image").count() and page.get_by_text("Select a frame image").first.is_visible():
            page.keyboard.press("Escape")
            page.wait_for_timeout(1500)
        if page.get_by_role("button", name="Image ingredient" if legacy else "Ingredient", exact=True).count() != before + 1:
            self._stop(page, beat, f"{slot} frame {image.name} did not attach")

    def _set_duration(self, page, seconds: int, beat: str) -> str:
        radio = page.get_by_role("radio", name=f"{seconds}s", exact=True)
        for _ in range(3):                                   # the popover sometimes toggles shut
            if radio.count() and radio.first.is_visible():
                break
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
            page.get_by_role("button", name="Settings trigger").click()
            page.wait_for_timeout(1500)
            video = page.get_by_role("radio", name="Video")
            if video.count() and video.first.is_visible() and video.first.get_attribute("aria-checked") != "true":
                video.first.click()
                page.wait_for_timeout(1000)
        if not (radio.count() and radio.first.is_visible()):
            self._stop(page, beat, f"duration option {seconds}s not available")
        radio.first.click()
        page.wait_for_timeout(1200)
        price_link = page.locator("a").filter(has_text=re.compile(r"^\s*\d+\s+credits\s*$"))
        if not price_link.count():
            self._stop(page, beat, "numeric generation price is not visible")
        price = price_link.first.inner_text().strip()
        page.keyboard.press("Escape")
        page.wait_for_timeout(800)
        return price

    def _ensure_video_settings(self, page, beat: str):
        """Restore the approved Flow workspace settings before attaching media."""
        page.get_by_role("button", name="Settings trigger").click()
        page.wait_for_timeout(700)
        for name in ("Video", "9:16", "720p", "x1"):
            radio = page.get_by_role("radio", name=name, exact=(name == "x1"))
            if not (radio.count() and radio.first.is_visible()):
                page.get_by_role("button", name="Settings trigger").click()
                page.wait_for_timeout(600)
            if not (radio.count() and radio.first.is_visible()):
                self._stop(page, beat, f"approved setting {name} not available")
            if radio.first.get_attribute("aria-checked") != "true":
                radio.first.click()
                page.wait_for_timeout(800)
        model = page.get_by_role("button", name="Select model family").inner_text()
        if "Omni 1.1 Flash" not in model:
            self._stop(page, beat, f"approved Omni 1.1 Flash model not selected: {model!r}")
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

    # ------------------------------------------------------------- one clip
    def one(self, page, beat: dict, known_srcs: set) -> dict:
        bid = beat["id"]
        sb = self.project / "05-visuals/storyboards"
        end_id = beat["transition"].split(":", 1)[1] if beat["transition"].startswith("first_last:") else None
        self._open(page)
        if page.get_by_role("button", name="Agent", exact=True).get_attribute("aria-pressed") != "false":
            self._stop(page, bid, "Agent mode is on (house rule: never use Agent mode)")
        self._ensure_video_settings(page, bid)
        if page.get_by_role("button", name="Clear prompt").count():
            page.get_by_role("button", name="Clear prompt").click()
            page.wait_for_timeout(800)
        while page.get_by_role("button", name="Image ingredient").count():
            page.get_by_role("button", name="Image ingredient").first.click()
            page.wait_for_timeout(1000)
        chip = page.get_by_role("button", name="Settings trigger").inner_text()
        if not all(k in chip for k in ("Video", "720p", "9_16", "x1")):
            self._stop(page, bid, f"settings chip unexpected: {chip!r}")

        self._attach(page, "Start", sb / f"{bid}.png", bid)
        if end_id:
            self._attach(page, "End", sb / f"{end_id}.png", bid)
        want = 2 if end_id else 1
        got = page.get_by_role("button", name="Image ingredient", exact=True).count() or page.get_by_role("button", name="Ingredient", exact=True).count()
        if got != want:
            self._stop(page, bid, f"{got} frame ingredients attached, expected {want}")

        prompt = _prompt(beat, bool(end_id))
        box = page.locator('[contenteditable="true"]:visible')
        if box.count() != 1:
            self._stop(page, bid, f"{box.count()} visible prompt editors")
        box.first.click()
        box.first.fill(prompt)
        page.wait_for_timeout(800)
        if len(box.first.inner_text().strip()) < len(prompt) * 0.9:
            self._stop(page, bid, "prompt did not land whole")

        expected = PRICE_720P_X1[beat["clip_s"]]
        price = self._set_duration(page, beat["clip_s"], bid)
        if price != f"{expected} credits":
            self._stop(page, bid, f"price {price!r}, expected {expected} credits")
        if (page.get_by_role("button", name="Image ingredient", exact=True).count() or page.get_by_role("button", name="Ingredient", exact=True).count()) != want:
            self._stop(page, bid, "frames detached while changing duration")
        self._shot(page, f"{bid}_ready")

        page.get_by_role("button", name="Start generation").click()      # the one paid click
        t0 = time.time()
        seen_progress = False
        while time.time() - t0 < 900:
            page.wait_for_timeout(6000)
            n = page.evaluate(PROGRESS_JS)
            seen_progress = seen_progress or n > 0
            if seen_progress and n == 0:
                break
            if not seen_progress and time.time() - t0 > 120:
                break                         # finished before we ever saw a % tile
        gen_s = round(time.time() - t0)

        # Flow now interleaves uploaded images with generated video in All media.
        # Filter to Videos before opening the newest rendered tile.
        self._open(page)
        src = None
        for _ in range(3):
            videos = page.get_by_text("Videos", exact=True)
            if videos.count():
                videos.first.click()
                page.wait_for_timeout(3000)
            thumb = page.locator('img[alt="Generated video thumbnail"]')
            if not thumb.count():
                self._stop(page, bid, "Videos view has no generated thumbnail")
            thumb.first.hover()
            page.wait_for_timeout(700)
            thumb.first.click()
            for _ in range(20):
                src = page.evaluate(VIDEO_SRC_JS)
                if src:
                    break
                page.wait_for_timeout(1000)
            if src and src not in known_srcs:
                break
            self._open(page)
            page.wait_for_timeout(20000)      # still finishing; look again
        if not src or src in known_srcs:
            self._shot(page, f"{bid}_nofile")
            return {"beat": bid, "status": "generated_not_downloaded", "gen_s": gen_s, "price": expected}
        body = page.request.get(src).body()
        out = self.clips / f"{bid}_v1.mp4"
        out.write_bytes(body)
        known_srcs.add(src)
        return {"beat": bid, "file": str(out.relative_to(self.project)), "src": src,
                "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body), "credits": expected,
                "clip_s": beat["clip_s"], "start_frame": f"05-visuals/storyboards/{bid}.png",
                "end_frame": f"05-visuals/storyboards/{end_id}.png" if end_id else None,
                "gen_s": gen_s, "status": "downloaded", "at": datetime.now().isoformat(timespec="seconds")}

    # ------------------------------------------------------------- run
    def run(self, beat_ids: list[str], credit_cap: int) -> dict:
        beats = {b["id"]: b for b in self.plan["beats"]}
        todo = [beats[b] for b in beat_ids]
        planned = sum(PRICE_720P_X1[b["clip_s"]] for b in todo)
        if planned > credit_cap:
            raise GuardStop(f"planned {planned} credits exceeds cap {credit_cap}")
        known = {c.get("src") for c in self.ledger["clips"] if c.get("src")}
        spent = 0
        with flow_session(self.cfg) as (_, page):
            self._open(page)
            start_credits = self.credits(page)
            # The ledger tracks known output URLs; uploaded images in All media
            # are not video sources and must not be treated as the latest clip.
            print(json.dumps({"start_credits": start_credits, "planned": planned, "beats": beat_ids}))
            for b in todo:
                if spent + PRICE_720P_X1[b["clip_s"]] > credit_cap:
                    raise GuardStop(f"credit cap {credit_cap} reached")
                rec = self.one(page, b, known)
                spent += rec.get("credits", rec.get("price", 0))
                self.ledger["clips"].append(rec)
                self._save_ledger()
                print(json.dumps({k: v for k, v in rec.items() if k != "src"}), flush=True)
            self._open(page)
            end_credits = self.credits(page)
        summary = {"start_credits": start_credits, "end_credits": end_credits, "planned": planned,
                   "charged": (start_credits - end_credits) if start_credits and end_credits else None}
        self.ledger.setdefault("runs", []).append(summary | {"beats": beat_ids,
                                                             "at": datetime.now().isoformat(timespec="seconds")})
        self._save_ledger()
        return summary


def harvest(project: Path, cfg: FlowConfig | None = None, max_tiles: int = 40) -> dict:
    """Free recovery: open every video tile in the Flow project, download any whose src is not in the
    ledger, bind it to a beat by comparing its first frame with the storyboards, and file the missing
    beats. Nothing is generated."""
    import subprocess
    import tempfile
    from PIL import Image, ImageChops, ImageStat

    gen = FlowGenerator(project, cfg)
    known = {c.get("src") for c in gen.ledger["clips"] if c.get("src")}
    have = {p.stem.split("_")[0] for p in gen.clips.glob("B??_v*.mp4")}
    sb = {p.stem: Image.open(p).convert("L").resize((180, 320))
          for p in sorted((gen.project / "05-visuals/storyboards").glob("B??.png"))}
    found = []
    def open_videos(page):
        gen._open(page)
        v = page.get_by_text("Videos", exact=True)      # sidebar filter: videos only, newest first
        if v.count():
            v.first.click()
            page.wait_for_timeout(4000)

    with flow_session(gen.cfg) as (_, page):
        open_videos(page)
        THUMB = 'img[alt="Generated video thumbnail"]'
        n_tiles = page.locator(THUMB).count()
        points = list(range(n_tiles))
        for i in points[:max_tiles]:
            open_videos(page)
            for _ in range(12):                              # the grid only renders tiles near the viewport
                if page.locator(THUMB).count() > i:
                    break
                page.mouse.move(800, 500)
                page.mouse.wheel(0, 700)
                page.wait_for_timeout(1500)
            if page.locator(THUMB).count() <= i:
                continue
            page.locator(THUMB).nth(i).scroll_into_view_if_needed()
            page.locator(THUMB).nth(i).hover(); page.wait_for_timeout(1000)
            page.locator(THUMB).nth(i).click()
            src = None
            for _ in range(12):
                src = page.evaluate(VIDEO_SRC_JS)
                if src:
                    break
                page.wait_for_timeout(1000)
            if not src or src in known:
                continue
            body = page.request.get(src).body()
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as t:
                t.write(body)
            png = t.name + ".png"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", t.name, "-frames:v", "1", png], check=True)
            fr = Image.open(png).convert("L").resize((180, 320))
            # bind only among beats still missing: B15's storyboard is B01's frame with the glow on,
            # so against the full set they are ambiguous; B01 is already filed.
            pool = {k: im for k, im in sb.items() if k not in have} or sb
            scores = sorted((ImageStat.Stat(ImageChops.difference(fr, im)).mean[0], k) for k, im in pool.items())
            scores.append((999.0, "-"))
            (best_d, best), (next_d, _) = scores[0], scores[1]
            rec = {"src": src, "best": best, "best_diff": round(best_d, 2), "next_diff": round(next_d, 2)}
            known.add(src)
            if best not in have and best_d < 8 and next_d - best_d > 3:
                out = gen.clips / f"{best}_v1.mp4"
                out.write_bytes(body)
                have.add(best)
                rec.update(filed=str(out.relative_to(gen.project)))
                beat = next(b for b in gen.plan["beats"] if b["id"] == best)
                gen.ledger["clips"].append({"beat": best, "file": rec["filed"], "src": src,
                                            "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
                                            "clip_s": beat["clip_s"], "status": "harvested",
                                            "bound_by": f"first-frame diff {best_d:.1f} vs next {next_d:.1f}",
                                            "at": datetime.now().isoformat(timespec="seconds")})
                gen._save_ledger()
            found.append(rec)
    return {"tiles": len(points), "new_videos": len(found), "found": found,
            "missing_after": sorted(set(sb) - have)}
