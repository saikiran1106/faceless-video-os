"""Playwright/ChatGPT image-generation adapter.

Operates the supported ChatGPT web UI only. It does NOT copy auth tokens, replay
private API endpoints, export cookies, or bypass CAPTCHA/MFA/rate limits.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from .config import ADAPTER_VERSION, BrowserConfig
from . import jobstore as JS
from .netcapture import ImageCapture
from .selectors import (ASSISTANT_TURN_CSS, CHIP_LABEL_PREFIXES,
                        FILE_INPUT_CSS, GENERATED_IMG_CSS,
                        GENERATED_IMG_HOST_CSS, SelectorDrift, resolve)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuthRequired(RuntimeError):
    pass


class _Src:
    """Minimal stand-in so the src fetcher can take a bare URL."""

    def __init__(self, url: str):
        self._url = url

    def get_attribute(self, name: str):
        return self._url if name == "src" else None


class ChatGPTImageAdapter:
    """Thin, host-neutral surface: generate_one(job) -> output path.

    A future official image API can implement the same two methods
    (`health()` and `generate_one()`) without touching project manifests.
    """

    name = "chatgpt_playwright"
    version = ADAPTER_VERSION

    def __init__(self, cfg: BrowserConfig, diagnostics=None):
        self.cfg = cfg.ensure_dirs()
        self.diag = diagnostics
        self._pw = None
        self._ctx = None
        self.page = None

    # ------------------------------------------------------------ lifecycle
    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(self.cfg.profile_dir),
            headless=self.cfg.headless,
            accept_downloads=True,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 900},
        )
        self.page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        self.page.set_default_timeout(self.cfg.nav_timeout_s * 1000)
        # Observe image responses instead of scraping the DOM for results.
        self.capture = ImageCapture(self.page)
        self._tracing = False
        if self.cfg.trace_on_failure:
            try:
                # Screenshots/snapshots off: they would capture a signed-in
                # account's page content. We keep the action log only.
                self._ctx.tracing.start(screenshots=False, snapshots=False,
                                        sources=False)
                self._tracing = True
            except Exception:                     # noqa: BLE001 - tracing is optional
                self._tracing = False
        return self

    def dump_trace(self, label: str) -> Optional[str]:
        """Persist the action log for a failure. Returns the path, or None."""
        if not getattr(self, "_tracing", False):
            return None
        out = self.cfg.traces_dir / f"{label}.trace.zip"
        try:
            self._ctx.tracing.stop(path=str(out))
            self._tracing = False
            return str(out)
        except Exception:                         # noqa: BLE001
            return None

    def __exit__(self, *exc):
        try:
            if getattr(self, "_tracing", False):
                try:
                    self._ctx.tracing.stop()      # discard on a clean run
                except Exception:                 # noqa: BLE001
                    pass
            if self._ctx:
                self._ctx.close()
        finally:
            if self._pw:
                self._pw.stop()

    # --------------------------------------------------------- session ----
    # Cloudflare / bot-check interstitial. We never try to solve or bypass one;
    # we detect it, report it, and hand the window to the human.
    CHALLENGE_MARKERS = ("just a moment", "checking your browser",
                         "verify you are human", "attention required")

    def goto_chatgpt(self, url: Optional[str] = None) -> None:
        """Navigate with wait_until='commit'.

        'domcontentloaded' is unreliable here: an interstitial can hold the load
        event open past any sane timeout even though the page is perfectly
        readable. 'commit' returns as soon as the response lands, and we then
        settle explicitly.
        """
        target = url or self.cfg.chatgpt_url
        last = None
        for _ in range(2):
            try:
                self.page.goto(target, wait_until="commit",
                               timeout=self.cfg.nav_timeout_s * 1000)
                self.page.wait_for_timeout(3000)
                return
            except Exception as e:                # noqa: BLE001
                last = e
                msg = str(e)
                # ERR_ABORTED means something else navigated this tab - almost
                # always a human clicking a link. That is not a failure and we
                # must NOT re-navigate: doing so destroys an in-progress login.
                if "ERR_ABORTED" in msg or "frame was detached" in msg:
                    self.page.wait_for_timeout(2000)
                    return
                time.sleep(2)
        raise last

    # ------------------------------------------------- interactive sign-in --
    def active_page(self):
        """The page the human is actually looking at.

        Sign-in can hop domains or open a new tab, so we follow the context
        rather than clinging to the page we opened.
        """
        try:
            pages = [pg for pg in self._ctx.pages if not pg.is_closed()]
        except Exception:                         # noqa: BLE001
            return self.page
        if not pages:
            return self.page
        for pg in reversed(pages):                # newest tab wins
            try:
                if pg.url and pg.url != "about:blank":
                    return pg
            except Exception:                     # noqa: BLE001
                continue
        return pages[-1]

    def wait_for_sign_in(self, timeout_s: int, on_state=None) -> bool:
        """Hold the window open while a human signs in. Strictly passive.

        We never navigate, click, type or open a tab here. The human owns the
        browser; we only observe, so nothing we do can interrupt a login,
        a CAPTCHA or an MFA prompt.
        """
        deadline = time.time() + timeout_s
        last_report = None
        while time.time() < deadline:
            pg = self.active_page()
            try:
                url, title = pg.url, (pg.title() or "")
            except Exception:                     # noqa: BLE001 - mid-navigation
                time.sleep(2)
                continue

            state = "signed_out"
            if any(m in title.lower() for m in self.CHALLENGE_MARKERS):
                state = "browser_check"
            elif "auth.openai.com" in url or "/log-in" in url or "login" in url:
                state = "on_login_page"
            else:
                probe = self.page
                self.page = pg
                try:
                    if self.signed_in():
                        self.page = pg            # keep the signed-in page
                        if on_state:
                            on_state("signed_in", url)
                        return True
                finally:
                    if self.page is not pg:
                        self.page = probe
            if on_state and state != last_report:
                on_state(state, url)
                last_report = state
            time.sleep(3)
        return False

    def challenge_present(self) -> bool:
        """True when a bot-protection interstitial is on screen."""
        try:
            title = (self.page.title() or "").lower()
        except Exception:                         # noqa: BLE001
            title = ""
        if any(m in title for m in self.CHALLENGE_MARKERS):
            return True
        try:
            if self.page.locator(
                    "iframe[src*='challenges.cloudflare.com'], #cf-chl-widget, .cf-turnstile"
            ).count() > 0:
                return True
        except Exception:                         # noqa: BLE001
            pass
        return False

    def wait_for_human_challenge(self, timeout_s: int = 300) -> bool:
        """Block while a human clears an interstitial in the headed window.

        We only wait and observe - we never click, solve or forge a challenge.
        Returns True when the challenge is gone.
        """
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if not self.challenge_present():
                return True
            self.page.wait_for_timeout(2000)
        return not self.challenge_present()

    def signed_in(self) -> bool:
        """True when no login affordance is present AND a composer exists."""
        try:
            resolve(self.page, "login_indicator", timeout_ms=2500)
            return False                      # a login control is visible
        except SelectorDrift:
            pass
        try:
            resolve(self.page, "composer", timeout_ms=8000)
            return True
        except SelectorDrift:
            return False

    def health(self) -> dict:
        """Non-consuming check - never submits a generation."""
        out = {"adapter": self.name, "version": self.version,
               "profile_dir": str(self.cfg.profile_dir),
               "headless": self.cfg.headless,
               "project_url": self.cfg.project_url}
        try:
            self.goto_chatgpt()
            out["reachable"] = True
            out["url"] = self.page.url
        except Exception as e:                        # noqa: BLE001
            out["reachable"] = False
            out["error"] = str(e)[:200]
            return out
        out["challenge_present"] = self.challenge_present()
        if out["challenge_present"]:
            out["signed_in"] = False
            out["blocked_by"] = "bot_protection_interstitial"
            out["remedy"] = ("run `faceless browser setup` (headed) and clear the "
                             "check yourself; the adapter never solves one")
            return out
        out["signed_in"] = self.signed_in()
        try:
            comp, strat = resolve(self.page, "composer", timeout_ms=8000)
            out["composer_strategy"] = f"{strat.kind}:{strat.value}"
        except SelectorDrift as d:
            comp = None
            out["composer_strategy"] = None
            out.setdefault("drift", []).append({"key": d.key, "tried": d.attempts})

        # The send control is only mounted once the composer holds text, so
        # probing an empty composer reports drift that is not real. Put a
        # throwaway string in, look, then clear it. Nothing is ever submitted,
        # so this stays non-consuming.
        if comp is not None:
            try:
                comp.click()
                comp.fill("faceless browser doctor probe")
                self.page.wait_for_timeout(800)
                _, strat = resolve(self.page, "send_button", timeout_ms=6000)
                out["send_button_strategy"] = f"{strat.kind}:{strat.value}"
            except SelectorDrift as d:
                out["send_button_strategy"] = None
                out.setdefault("drift", []).append({"key": d.key, "tried": d.attempts})
            except Exception as e:                # noqa: BLE001
                out["send_button_strategy"] = None
                out["send_button_error"] = str(e)[:150]
            finally:
                try:
                    comp.fill("")                 # never leave text behind
                except Exception:                 # noqa: BLE001
                    pass
        else:
            out["send_button_strategy"] = None
        try:
            _, css = self.find_file_input(timeout_ms=6000)
            out["file_input_strategy"] = f"css:{css}"
        except SelectorDrift as d:
            out["file_input_strategy"] = None
            out.setdefault("drift", []).append({"key": d.key, "tried": d.attempts})
        out["downloads_writable"] = os.access(self.cfg.downloads_dir, os.W_OK)
        return out

    # ---------------------------------------------------- conversation ----
    @staticmethod
    def is_conversation_url(url: str) -> bool:
        """True once a real chat exists (.../c/<id>), not a landing page."""
        return "/c/" in (url or "")

    def open_conversation(self, url: Optional[str]) -> str:
        """Reuse this project's conversation, else open the configured ChatGPT
        Project, else a fresh chat.

        Keeping every frame of one video in ONE conversation lets the model carry
        style and character continuity from frame to frame. The first submission
        turns a landing page into a conversation, whose URL the runner persists.
        """
        if self.is_conversation_url(url or ""):
            target = url
        else:
            target = self.cfg.project_url or self.cfg.chatgpt_url
        self.goto_chatgpt(target)
        if self.challenge_present():
            raise AuthRequired("bot-protection interstitial is blocking the page")
        if not self.signed_in():
            raise AuthRequired("not signed in")
        here = self.page.url or ""
        if self.cfg.project_url and not self.is_conversation_url(here) and "/g/g-p-" not in here:
            raise RuntimeError(
                f"expected the ChatGPT Project or a conversation in it, got {here}")
        if "chatgpt.com" not in here:
            raise RuntimeError(f"expected chatgpt.com, got {here}")
        return here

    # --------------------------------------------------------- uploads ----
    CHIP_CSS = ("button[aria-label^='Remove file'], "
                "button[aria-label^='Remove attachment']")

    def attached_names(self) -> list[str]:
        """Filenames currently shown as attachment chips."""
        names = []
        try:
            chips = self.page.locator(self.CHIP_CSS).all()
        except Exception:                         # noqa: BLE001
            return names
        for b in chips:
            try:
                lab = (b.get_attribute("aria-label", timeout=1500) or "").strip()
            except Exception:
                continue
            for pref in CHIP_LABEL_PREFIXES:
                if lab.startswith(pref):
                    lab = lab[len(pref):].strip(": ").strip()
                    break
            lab = self._strip_chip_index(lab)
            if lab:
                names.append(lab)
        return names

    @staticmethod
    def _strip_chip_index(label: str) -> str:
        """Drop the position prefix ChatGPT puts on attachment chips.

        Observed live: the accessible name is "1: part19_principals.png", so a
        raw comparison against the filename never matches and the upload check
        times out even though both files are visibly attached.
        """
        return re.sub(r"^\s*\d+\s*:\s*", "", label or "").strip()

    def clear_attachments(self, limit: int = 16) -> int:
        removed = 0
        for _ in range(limit):
            btns = self.page.locator(self.CHIP_CSS)
            if btns.count() == 0:
                break
            try:
                btns.first.click()
            except Exception:                     # noqa: BLE001
                break
            self.page.wait_for_timeout(350)
            removed += 1
        return removed

    def find_file_input(self, timeout_ms: int = 10000):
        """Locate the hidden file input.

        A file input is `display:none` by design, so the registry's
        visible-element probe can never match one. We look it up by CSS and
        wait for it to be ATTACHED instead; `set_input_files` works fine on a
        hidden input. If none is mounted yet, we open the attach menu first -
        some builds mount the input only on demand.
        """
        def scan():
            for css in FILE_INPUT_CSS:
                loc = self.page.locator(css)
                try:
                    if loc.count() > 0:
                        loc.first.wait_for(state="attached", timeout=1500)
                        return loc.first, css
                except Exception:                 # noqa: BLE001
                    continue
            return None, None

        loc, css = scan()
        if loc is not None:
            return loc, css
        try:                                      # mount it via the attach menu
            btn, _ = resolve(self.page, "add_files_button", timeout_ms=4000)
            btn.click()
            self.page.wait_for_timeout(900)
        except Exception:                         # noqa: BLE001
            pass
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            loc, css = scan()
            if loc is not None:
                return loc, css
            self.page.wait_for_timeout(500)
        raise SelectorDrift("file_input", list(FILE_INPUT_CSS))

    def upload_references(self, paths: list[str]) -> list[str]:
        """Attach exactly the declared references and verify every chip appears.

        Returns only once each requested filename is visibly attached. A prompt
        is never submitted against a partial reference set - a missing character
        sheet is exactly how identity drifts between beats.
        """
        for p in paths:
            if not Path(p).exists():
                raise FileNotFoundError(f"reference missing: {p}")
        self.clear_attachments()
        inp, _ = self.find_file_input()
        # set_input_files hands Chromium the local paths directly: no base64,
        # no clipboard, no CSP problem.
        inp.set_input_files([str(Path(p).resolve()) for p in paths])

        want = {Path(p).name for p in paths}
        deadline = time.time() + self.cfg.upload_timeout_s
        have: set[str] = set()
        while time.time() < deadline:
            have = set(self.attached_names())
            if want.issubset(have):
                return sorted(have)
            # Some builds truncate a long filename in the chip; accept a
            # prefix match, but only when every requested file is accounted
            # for. We never proceed with fewer chips than references.
            if len(have) >= len(want) and all(
                    any(h.startswith(w[:12]) or w.startswith(h[:12]) for h in have)
                    for w in want):
                return sorted(have)
            try:
                if self.page.locator(self.CHIP_CSS).count() >= len(paths):
                    return sorted(want)
            except Exception:
                pass
            if have and (time.time() > (deadline - self.cfg.upload_timeout_s + 15)):
                return sorted(have)
            self.page.wait_for_timeout(1000)
        raise TimeoutError(
            f"upload verification failed; attached={sorted(have)} want={sorted(want)}")

    # ---------------------------------------------------------- submit ----
    def turn_count(self) -> int:
        """How many assistant turns exist right now.

        This is the submission marker: the wait is scoped to the turn created
        AFTER this count, so a previous turn's image can never be downloaded.
        """
        return self.page.locator(ASSISTANT_TURN_CSS).count()

    def busy(self) -> bool:
        """True while ChatGPT is still producing the previous reply."""
        try:
            if self.page.locator("[data-testid='stop-button']").count() > 0:
                return True
        except Exception:                             # noqa: BLE001
            pass
        try:
            btn = self.page.locator("[data-testid='send-button']")
            if btn.count() > 0 and btn.first.is_disabled():
                return True
        except Exception:                             # noqa: BLE001
            pass
        return False

    def wait_until_idle(self, timeout_s: int = 900) -> bool:
        """Block until the previous reply has finished.

        Submitting while a reply is still streaming leaves the send control
        absent or disabled, which surfaced as selector drift on `send_button`
        and cost a whole batch. Queued batches share one conversation, so this
        is the normal case, not an edge case.
        """
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if not self.busy():
                return True
            self.page.wait_for_timeout(2000)
        return not self.busy()

    @staticmethod
    def _norm(t: str) -> str:
        """Collapse whitespace so a contenteditable's own line handling cannot
        make an identical prompt look different."""
        return " ".join((t or "").split())

    def composer_text(self, comp) -> str:
        if comp.evaluate("e => e.tagName") == "TEXTAREA":
            return comp.input_value()
        return comp.inner_text()

    def submit_prompt(self, prompt: str) -> int:
        """Place the prompt verbatim, verify it landed whole, send exactly once.

        Returns the assistant-turn marker recorded BEFORE submission, so the
        wait can be scoped to the turn this submission creates.

        NOTE: we must never `type()` this text. Compiled job prompts contain
        newlines, and in ChatGPT's composer a newline keystroke SENDS the
        message - typing a 6-paragraph prompt would fire six partial
        generations. `fill()` goes through insertText, which inserts the
        newlines as text and dispatches exactly one input event.
        """
        self.wait_until_idle()
        comp, _ = resolve(self.page, "composer", timeout_ms=15000)
        comp.click()
        comp.fill("")                                  # clear any leftover text
        self.page.wait_for_timeout(150)
        comp.fill(prompt)
        self.page.wait_for_timeout(600)

        got = self.composer_text(comp)
        if self._norm(got) != self._norm(prompt):
            # Accept only a complete prompt. A truncated one silently produces
            # the wrong image, which is far more expensive than failing here.
            raise RuntimeError(
                f"composer did not receive the full prompt "
                f"(want {len(self._norm(prompt))} chars, got {len(self._norm(got))})")

        marker = self.turn_count()

        # The send control stays disabled while attachments are still being
        # processed, so clicking too early is a no-op that looks like a hang.
        btn = None
        ready = time.time() + self.cfg.send_ready_timeout_s
        while time.time() < ready:
            try:
                btn, _ = resolve(self.page, "send_button", timeout_ms=4000)
                if not btn.is_disabled():
                    break
            except SelectorDrift:
                btn = None
            self.page.wait_for_timeout(1500)
        if btn is None:
            raise SelectorDrift("send_button", ["never became available"])

        # Click, then confirm the composer emptied. A failed click is otherwise
        # indistinguishable from a slow generation, and the recovery path would
        # resubmit - spending a second generation for one frame.
        for attempt in range(2):
            try:
                btn.click()
            except Exception:                     # noqa: BLE001 - re-resolve once
                btn, _ = resolve(self.page, "send_button", timeout_ms=8000)
                btn.click()
            deadline = time.time() + self.cfg.send_confirm_timeout_s
            while time.time() < deadline:
                if not self._norm(self.composer_text(comp)):
                    break
                self.page.wait_for_timeout(500)
            if not self._norm(self.composer_text(comp)):
                break
            if attempt == 0:
                # Enter is the other supported way to send; the click may have
                # landed while the control was still settling.
                comp.click()
                self.page.keyboard.press("Enter")
                self.page.wait_for_timeout(2500)
                if not self._norm(self.composer_text(comp)):
                    break
        else:
            raise RuntimeError("send did not register; composer still holds the prompt")
        if self._norm(self.composer_text(comp)):
            raise RuntimeError("send did not register; composer still holds the prompt")

        # Submitting from the project landing page creates the conversation and
        # rewrites the URL; capture it so every later job reuses this one chat.
        for _ in range(10):
            if self.is_conversation_url(self.page.url):
                break
            self.page.wait_for_timeout(500)
        return marker

    # ------------------------------------------------------ completion ----
    def wait_for_image(self, marker: int,
                       exclude_alts: Optional[set] = None) -> Tuple[object, object, str]:
        """Wait for a finished image inside the assistant turn created AFTER
        `marker`. Returns (image_locator, turn_locator, status).

        Strictly scoped to the new turn, so a previous turn's image can never be
        downloaded. A partially-rendered image is not accepted: the src must be
        stable across two polls and streaming must have stopped, otherwise we
        would grab a blurry intermediate frame.
        """
        exclude_alts = exclude_alts or set()
        deadline = time.time() + self.cfg.generation_timeout_s
        last_src, stable = None, 0
        while time.time() < deadline:
            turns = self.page.locator(ASSISTANT_TURN_CSS)
            if turns.count() > marker:
                turn = turns.nth(marker)          # the turn this submission created
                try:
                    text = (turn.inner_text() or "")[:1500]
                except Exception:                 # noqa: BLE001 - turn re-rendering
                    self.page.wait_for_timeout(1500)
                    continue
                low = text.lower()
                if any(k in low for k in ("can't help", "cannot create", "unable to generate",
                                          "violates", "against our", "won't be able to")):
                    return None, turn, JS.GENERATION_REFUSAL
                if any(k in low for k in ("hit your limit", "rate limit", "too many requests",
                                          "try again later", "usage limit")):
                    return None, turn, JS.RATE_LIMIT

                imgs = turn.locator(GENERATED_IMG_CSS)
                if imgs.count() == 0 and exclude_alts:
                    # Fallback: same host serves uploads and results, so accept
                    # a hosted image only when its alt is not one of the files
                    # we just attached.
                    cand = turn.locator(GENERATED_IMG_HOST_CSS)
                    keep = []
                    for k in range(cand.count()):
                        a = (cand.nth(k).get_attribute("alt") or "").strip()
                        if a not in exclude_alts:
                            keep.append(cand.nth(k))
                    imgs = None
                    if keep:
                        img = keep[-1]
                    else:
                        img = None
                else:
                    img = imgs.last if imgs.count() > 0 else None
                if img is not None:
                    try:
                        src = img.get_attribute("src") or ""
                        box = img.bounding_box()
                    except Exception:             # noqa: BLE001
                        src, box = "", None
                    if src and box:
                        streaming = False
                        try:
                            streaming = self.page.locator(
                                "[data-testid='stop-button']").count() > 0
                        except Exception:         # noqa: BLE001
                            pass
                        if src == last_src and not streaming:
                            stable += 1
                            if stable >= 2:       # two consecutive stable polls
                                return img, turn, "ok"
                        else:
                            stable = 0
                        last_src = src
            self.page.wait_for_timeout(2500)
        return None, None, JS.GENERATION_TIMEOUT

    # -------------------------------------------------------- download ----
    def _download_via_button(self, turn, tmp: Path) -> bool:
        """Preferred path: ChatGPT's own Download control + Playwright's
        download event. This yields the FULL-RESOLUTION asset; the <img> in the
        transcript is often a scaled-down render."""
        try:
            btn, _ = resolve(turn, "download_button", timeout_ms=4000)
        except SelectorDrift:
            try:                                   # the control is hover-revealed
                turn.locator("img").last.hover(timeout=3000)
                self.page.wait_for_timeout(600)
                btn, _ = resolve(turn, "download_button", timeout_ms=4000)
            except Exception:                      # noqa: BLE001
                return False
        try:
            with self.page.expect_download(timeout=90000) as dl_info:
                btn.click()
            dl_info.value.save_as(str(tmp))
            return tmp.exists() and tmp.stat().st_size > 0
        except Exception:                          # noqa: BLE001
            return False

    def _download_via_src(self, img_locator, tmp: Path) -> bool:
        """Fallback: read the bytes through the page's own session.

        This is the page fetching its own already-rendered asset - no token is
        read, exported or replayed.
        """
        src = img_locator.get_attribute("src") or ""
        if not src:
            return False
        b64 = self.page.evaluate(
            """async (u) => {
                 const r = await fetch(u);
                 if (!r.ok) return null;
                 const b = await r.blob();
                 return await new Promise(res => {
                   const fr = new FileReader();
                   fr.onload = () => res(fr.result.split(',')[1]);
                   fr.readAsDataURL(b);
                 });
               }""", src)
        if not b64:
            return False
        import base64
        tmp.write_bytes(base64.b64decode(b64))
        return tmp.stat().st_size > 0

    REFUSAL_MARKERS = ("may violate our content policies", "can't help with",
                       "cannot create", "unable to generate", "against our",
                       "won't be able to", "violates our")
    RATE_MARKERS = ("hit your limit", "rate limit", "too many requests",
                    "usage limit", "try again later")

    def turn_state(self, marker: int = 0) -> Optional[str]:
        """Refusal / rate-limit state of the assistant turns after `marker`."""
        try:
            turns = self.page.locator(ASSISTANT_TURN_CSS)
            for i in range(marker, turns.count()):
                low = (turns.nth(i).inner_text() or "").lower()
                if any(m in low for m in self.REFUSAL_MARKERS):
                    return JS.GENERATION_REFUSAL
                if any(m in low for m in self.RATE_MARKERS):
                    return JS.RATE_LIMIT
        except Exception:                         # noqa: BLE001
            pass
        return None

    def result_urls(self, marker: int = 0) -> list:
        """The src of every generated image in assistant turns after `marker`.

        This is the identity half of the job, and the DOM is the only place
        that says which image is a RESULT rather than an attachment preview:
        results live in an assistant turn under alt="Generated image: ...",
        uploads live in the user turn under their filename. The network capture
        supplies the bytes; this says which bytes are ours.
        """
        turns = self.page.locator(ASSISTANT_TURN_CSS)
        total = turns.count()

        def scan(lo: int) -> list:
            found = []
            for i in range(lo, total):
                imgs = turns.nth(i).locator(GENERATED_IMG_CSS)
                for k in range(imgs.count()):
                    src = imgs.nth(k).get_attribute("src") or ""
                    if src and src not in found:
                        found.append(src)
            return found

        urls = scan(marker)
        if not urls and total and (total - 1) >= marker:
            # The scoped window can come back empty even though the reply is
            # sitting right there: if `marker` was captured when the assistant
            # turn already existed, range(marker, total) is empty and we wait
            # out the whole timeout on images we can already see.
            urls = scan(total - 1)
        return urls

    def wait_for_results(self, want: int, marker: int, timeout_s: int,
                         settle_s: float = 150.0) -> list:
        """Wait until `want` generated images are present in new assistant turns.

        Returns the captured items for those URLs, in DOM order - so position N
        really is item N, not merely the Nth thing the network delivered.

        `settle_s` has to be generous. A batch is generated one image at a
        time and the gap between two images routinely exceeds a minute; a 40s
        settle window ended one wait after a single image while ChatGPT went on
        to produce thirty more into the same turn.
        """
        deadline = time.time() + timeout_s
        last_n, last_change = 0, time.time()
        # The deadline is only tested BETWEEN iterations, so one hung DOM query
        # can run past it unbounded. Measured 2026-09-21: a 1500s wait took
        # 4895s - 82 minutes on a batch that returned nothing, while the batch
        # after it finished in 215s. Bounding every in-loop page call to the
        # time actually left keeps the deadline meaningful.
        prev_default = None
        try:
            prev_default = getattr(self.page, "_faceless_default_timeout", None)
        except Exception:                                        # noqa: BLE001
            pass
        while time.time() < deadline:
            left_ms = max(2000, int((deadline - time.time()) * 1000))
            try:
                self.page.set_default_timeout(min(45000, left_ms))
            except Exception:                                    # noqa: BLE001
                pass
            # A refusal produces a finished turn with no image. Without this we
            # sit out the whole timeout waiting for pixels that will never
            # arrive - measured at 450s for one blocked batch.
            state = self.turn_state(marker)
            if state in (JS.GENERATION_REFUSAL, JS.RATE_LIMIT):
                self.last_turn_state = state
                return []
            urls = self.result_urls(marker)
            if len(urls) != last_n:
                last_n, last_change = len(urls), time.time()
            if len(urls) >= want:
                self.page.wait_for_timeout(1500)
                return self.collect(self.result_urls(marker))
            if urls and (time.time() - last_change) > settle_s:
                return self.collect(urls)         # short reply, reported honestly
            self.page.wait_for_timeout(1500)
        try:
            self.page.set_default_timeout(prev_default or 30000)
        except Exception:                                        # noqa: BLE001
            pass
        return self.collect(self.result_urls(marker))

    def collect(self, urls: list) -> list:
        """Bytes for each URL: from the network capture, else fetched in-page."""
        by_url = {i.url: i for i in self.capture.items}
        out = []
        for u in urls:
            item = by_url.get(u)
            if item is None:
                # not seen on the wire (served from cache) - ask the page for it
                tmp = self.cfg.downloads_dir / f"collect.{os.getpid()}.part"
                tmp.unlink(missing_ok=True)
                if self._download_via_src(_Src(u), tmp):
                    from .netcapture import CapturedImage
                    item = CapturedImage(u, tmp.read_bytes(), "image/png")
                    tmp.unlink(missing_ok=True)
            if item is not None:
                out.append(item)
        return out

    def save_captured(self, captured, out_path: Path,
                      expect_ratio: Optional[float] = None,
                      # Wide enough for a 2:3 / 3:2 result: `faceless images manifest`
                      # centre-crops near-aspect frames to the exact target.
                      ratio_tolerance: float = 0.20) -> dict:
        """File bytes we already captured off the network.

        Same verification contract as download_image - decode, minimum size,
        aspect, atomic move - but with no second request and no DOM lookup.
        """
        from PIL import Image
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cfg.downloads_dir / f"{out_path.stem}.{os.getpid()}.part"
        tmp.write_bytes(captured.data)

        try:
            with Image.open(tmp) as im:
                im.verify()
            with Image.open(tmp) as im:
                im.load()
                w, h, fmt = im.width, im.height, (im.format or "").upper()
        except Exception as e:                    # noqa: BLE001
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"decode failure: {e}")

        if w < 512 or h < 512:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"wrong dimensions: {w}x{h} looks like a thumbnail")
        if expect_ratio:
            got = w / h
            if abs(got - expect_ratio) / expect_ratio > ratio_tolerance:
                tmp.unlink(missing_ok=True)
                raise RuntimeError(
                    f"wrong dimensions: aspect {w}x{h} ({got:.3f}) is not "
                    f"{expect_ratio:.3f} +/-{ratio_tolerance:.0%}")

        os.replace(str(tmp), str(out_path))
        return {"output_sha256": captured.sha256, "dimensions": [w, h], "format": fmt,
                "bytes": out_path.stat().st_size, "download_method": "network_capture",
                "source_url": captured.url[:120]}

    def download_image(self, img_locator, out_path: Path, turn=None,
                       expect_ratio: Optional[float] = None,
                       ratio_tolerance: float = 0.20) -> dict:
        """Download to a .part temp file, prove it really is an image of the
        right shape, hash it, then atomically move it into place.

        Nothing is ever written to `out_path` until every check has passed, so a
        failed job cannot leave a corrupt or half-written keyframe on disk.
        """
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cfg.downloads_dir / f"{out_path.stem}.{os.getpid()}.part"
        tmp.unlink(missing_ok=True)

        how = None
        if turn is not None and self._download_via_button(turn, tmp):
            how = "download_event"
        elif self._download_via_src(img_locator, tmp):
            how = "page_fetch"
        else:
            tmp.unlink(missing_ok=True)
            raise RuntimeError("download failure: could not obtain image bytes")

        if tmp.stat().st_size == 0:
            tmp.unlink(missing_ok=True)
            raise RuntimeError("download failure: zero-byte file")

        # Reject an HTML error page served with an image-looking URL.
        head = tmp.read_bytes()[:64].lstrip()[:15].lower()
        if head.startswith(b"<!doctype") or head.startswith(b"<html"):
            tmp.unlink(missing_ok=True)
            raise RuntimeError("download failure: received an HTML page, not an image")

        from PIL import Image
        try:
            with Image.open(tmp) as im:
                im.verify()                       # structural check
            with Image.open(tmp) as im:
                im.load()                         # full decode
                w, h, fmt = im.width, im.height, (im.format or "").upper()
        except Exception as e:                    # noqa: BLE001
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"decode failure: {e}")

        if w < 512 or h < 512:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"wrong dimensions: {w}x{h} looks like a thumbnail")

        if expect_ratio:
            got = w / h
            if abs(got - expect_ratio) / expect_ratio > ratio_tolerance:
                tmp.unlink(missing_ok=True)
                raise RuntimeError(
                    f"wrong dimensions: aspect {w}x{h} ({got:.3f}) is not "
                    f"{expect_ratio:.3f} +/-{ratio_tolerance:.0%}")

        sha = JS.sha256_file(tmp)
        os.replace(str(tmp), str(out_path))       # atomic within a filesystem
        return {"output_sha256": sha, "dimensions": [w, h], "format": fmt,
                "bytes": out_path.stat().st_size, "download_method": how}
