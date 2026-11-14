"""Centralised selector registry.

Every critical control is described by an ORDERED list of strategies. Resolution
prefers semantics over styling, so a Tailwind class change cannot break the run:

    1. ARIA role + accessible name
    2. stable accessible label / placeholder
    3. data-testid
    4. CSS (last resort only)

`resolve()` returns the first strategy that yields a visible element, together
with which strategy won, so drift is observable in receipts and diagnostics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

ROLE, LABEL, TESTID, CSS, TEXT = "role", "label", "testid", "css", "text"


@dataclass(frozen=True)
class Strategy:
    kind: str
    value: str
    name: Optional[str] = None   # accessible name for ROLE
    exact: bool = False

    def locator(self, scope: Any):
        if self.kind == ROLE:
            return scope.get_by_role(self.value, name=self.name, exact=self.exact) \
                if self.name else scope.get_by_role(self.value)
        if self.kind == LABEL:
            return scope.get_by_label(self.value, exact=self.exact)
        if self.kind == TESTID:
            return scope.get_by_test_id(self.value)
        if self.kind == TEXT:
            return scope.get_by_text(self.value, exact=self.exact)
        return scope.locator(self.value)


REGISTRY: dict[str, List[Strategy]] = {
    # --- composer -------------------------------------------------------
    # Observed 2026-09-18 on chatgpt.com: the app serves a composer with
    # id="mobile-composer-prompt" (a real <textarea>) alongside the classic
    # ProseMirror "#prompt-textarea". Both are listed; role/label first.
    "composer": [
        Strategy(ROLE, "textbox", name="Ask anything"),
        Strategy(ROLE, "textbox", name="Message ChatGPT"),
        Strategy(ROLE, "textbox", name="Chat with ChatGPT"),
        Strategy(CSS, "textarea#mobile-composer-prompt"),
        Strategy(CSS, "textarea[name='prompt']"),
        Strategy(CSS, "#prompt-textarea"),
        Strategy(CSS, "div[contenteditable='true']"),
    ],
    "send_button": [
        Strategy(TESTID, "send-button"),
        Strategy(ROLE, "button", name="Send prompt"),
        Strategy(ROLE, "button", name="Send message"),
        Strategy(CSS, "button[aria-label*='Send']"),
    ],
    "stop_button": [
        Strategy(TESTID, "stop-button"),
        Strategy(ROLE, "button", name="Stop streaming"),
        Strategy(ROLE, "button", name="Stop generating"),
    ],
    # --- attachments ----------------------------------------------------
    # File inputs are hidden by design, so `resolve()` cannot probe them for
    # visibility - `upload_references` looks them up directly instead.
    "file_input": [
        Strategy(CSS, "input[type='file'][multiple]:not([capture])"),
        Strategy(CSS, "input[type='file'][name='upload-media']"),
        Strategy(TESTID, "upload-media-input"),
        Strategy(CSS, "input#octane-mobile-composer-photos-input"),
        Strategy(CSS, "input#octane-mobile-composer-files-input"),
        Strategy(CSS, "input[type='file'][accept*='image']"),
        Strategy(CSS, "input[type='file']"),
    ],
    # Opens the attach menu when the file input is only mounted on demand.
    "add_files_button": [
        Strategy(ROLE, "button", name="Add files and more"),
        Strategy(ROLE, "button", name="Attach files"),
        Strategy(CSS, "button[aria-label*='Add files']"),
        Strategy(CSS, "button[aria-label*='Attach']"),
    ],
    "attachment_chip": [
        Strategy(CSS, "button[aria-label^='Remove file']"),
        Strategy(CSS, "button[aria-label^='Remove attachment']"),
        Strategy(CSS, "[data-testid='attachment-chip']"),
    ],
    # --- assistant turns / results -------------------------------------
    # Verified live 2026-09-18: turn containers are [data-turn="assistant"|"user"].
    # `data-message-author-role` is present ONLY on user turns, so the old
    # [data-message-author-role='assistant'] matched nothing - turn_count() was
    # permanently 0 and every wait ran to its timeout past a finished image.
    "assistant_turn": [
        Strategy(CSS, "[data-turn-key]"),
        Strategy(CSS, "[data-turn='assistant']"),
        Strategy(CSS, "[data-message-author-role='assistant']"),
        Strategy(CSS, "article[data-testid^='conversation-turn']"),
    ],
    # Observed live 2026-09-18: a finished image carries
    #   alt="Generated image: <title ChatGPT invented>"
    # and is served from /backend-api/estuary/content?id=... - NOT from
    # oaiusercontent, and NOT with a bare alt="Generated image". Matching the
    # alt exactly meant a completed image was never detected and every job ran
    # to its generation timeout.
    "generated_image": [
        Strategy(CSS, "img[alt^='Generated image']"),
        Strategy(CSS, "[data-testid='generated-image-preview'] img"),
        Strategy(CSS, "img[src*='oaiusercontent']"),
        Strategy(CSS, "img[src^='blob:']"),
    ],
    "download_button": [
        Strategy(ROLE, "button", name="Download this image"),
        Strategy(ROLE, "button", name="Download"),
        Strategy(CSS, "button[aria-label*='Download']"),
    ],
    # --- account / gating ------------------------------------------------
    # Observed on the signed-out page: "Log in" / "Sign up for free" buttons and
    # the "Log in to get answers..." banner. Any of these means signed out.
    "login_indicator": [
        Strategy(ROLE, "button", name="Log in"),
        Strategy(ROLE, "link", name="Log in"),
        Strategy(ROLE, "button", name="Sign up for free"),
        Strategy(TEXT, "Sign up for free"),
    ],
    "rate_limit_notice": [
        Strategy(TEXT, "You've hit your limit"),
        Strategy(TEXT, "rate limit"),
        Strategy(TEXT, "Please wait"),
    ],
}


# Which strategy last won for a key. The registry is an ORDERED fallback list,
# so on a UI where the first few entries do not exist every lookup pays their
# full timeout before reaching the one that works - measured at ~78s per
# prompt submission, which is over an hour across a 53-frame queue. Once a
# strategy wins we try it first, with a short timeout, and only fall back to
# the full sweep if the UI really has changed.
_WINNERS: dict[str, Strategy] = {}
FAST_TIMEOUT_MS = 2500


def reset_cache() -> None:
    _WINNERS.clear()


def _try(scope: Any, s: Strategy, timeout_ms: int):
    loc = s.locator(scope).first
    loc.wait_for(state="visible", timeout=timeout_ms)
    return loc


def resolve(scope: Any, key: str, timeout_ms: int = 5000) -> Tuple[Any, Strategy]:
    """Return (locator, winning_strategy) or raise SelectorDrift."""
    cached = _WINNERS.get(key)
    if cached is not None:
        try:
            return _try(scope, cached, min(timeout_ms, FAST_TIMEOUT_MS)), cached
        except Exception:                         # noqa: BLE001 - UI moved; re-sweep
            _WINNERS.pop(key, None)

    attempts: list[str] = []
    strategies = REGISTRY[key]
    for i, s in enumerate(strategies):
        # Give every strategy but the last a short budget: a control that
        # exists is found immediately, and one that does not should not hold
        # the queue for the full timeout.
        budget = timeout_ms if i == len(strategies) - 1 else min(timeout_ms, FAST_TIMEOUT_MS)
        try:
            loc = _try(scope, s, budget)
            _WINNERS[key] = s
            return loc, s
        except Exception:                         # noqa: BLE001 - try next strategy
            attempts.append(f"{s.kind}:{s.value}:{s.name or ''}")
            continue
    raise SelectorDrift(key, attempts)


class SelectorDrift(RuntimeError):
    def __init__(self, key: str, attempts: List[str]):
        self.key, self.attempts = key, attempts
        super().__init__(f"no strategy matched '{key}'; tried: {attempts}")


# Attachment chips carry the filename in their accessible name; these are the
# prefixes we strip to recover it.
CHIP_LABEL_PREFIXES = ("Remove file:", "Remove file", "Remove attachment:",
                       "Remove attachment", "Remove ")

# Every CSS form of the hidden file input, tried in order by upload_references.
FILE_INPUT_CSS = (
    # 2026-10-16: ChatGPT mounts a hidden single-file "Take a photo" input (capture=environment) before the
    # real uploader; picking it breaks multi-reference uploads. Prefer a multi-file input without capture.
    "input[type='file'][multiple]:not([capture])",
    "input[type='file'][name='upload-media']",
    "input#octane-mobile-composer-photos-input",
    "input#octane-mobile-composer-files-input",
    "input[type='file'][accept*='image']:not([capture])",
    "input[type='file']:not([capture])",
    "input[type='file'][accept*='image']",
    "input[type='file']",
)


# Primary match for a finished generation, and the host patterns a generated
# asset is served from. The host patterns alone are NOT sufficient: uploaded
# reference images come from the same host, so they must be excluded by name.
ASSISTANT_TURN_CSS = "[data-turn-key], [data-turn='assistant']"
ANY_TURN_CSS = "[data-turn-key], [data-turn]"
GENERATED_IMG_CSS = "img[alt^='Generated image'], [data-testid='generated-image-preview'] img"
GENERATED_IMG_HOST_CSS = ("img[src*='estuary/content'], img[src*='oaiusercontent'], img[src^='blob:']")
