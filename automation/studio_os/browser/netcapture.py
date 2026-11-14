"""Capture generated images straight off the network.

Why this exists
---------------
Reading results out of the DOM was the single biggest source of breakage in
this adapter. Three separate live failures came from it:

  * `[data-message-author-role='assistant']` matched nothing (that attribute is
    only on USER turns), so the turn count was permanently 0;
  * a finished image is labelled ``alt="Generated image: <title>"``, not
    ``alt="Generated image"``;
  * the result is served from ``/backend-api/estuary/content``, not from
    ``oaiusercontent``.

Each of those cost a full generation timeout to discover. The bytes, meanwhile,
were arriving over the network the whole time.

So we stop asking the DOM what happened and observe the responses the page
already receives. This is passive observation of traffic the browser fetched on
its own - no request is forged, replayed or re-authenticated, and no token is
read. It is both faster (bytes in hand the moment they render, no second fetch)
and immune to markup changes.

Uploaded references come back over the same endpoint, so they are excluded by
content hash: we know exactly what we sent.
"""
from __future__ import annotations

import hashlib
import time
from typing import Dict, List, Optional, Set

# The hosts ChatGPT serves conversation file content from.
IMAGE_URL_MARKERS = ("backend-api/estuary/content", "oaiusercontent", "/backend-api/files/")


class CapturedImage:
    __slots__ = ("url", "sha256", "data", "at", "content_type")

    def __init__(self, url: str, data: bytes, content_type: str):
        self.url = url
        self.data = data
        self.content_type = content_type
        self.sha256 = hashlib.sha256(data).hexdigest()
        self.at = time.time()

    def __repr__(self) -> str:                    # pragma: no cover - debug aid
        return f"<CapturedImage {len(self.data)}B sha={self.sha256[:10]}>"


class ImageCapture:
    """Collects image responses in arrival order, ignoring our own uploads."""

    MIN_BYTES = 40_000          # a generated 9:16 frame is far larger than an icon

    def __init__(self, page, ignore_hashes: Optional[Set[str]] = None):
        self.page = page
        self.ignore = set(ignore_hashes or ())
        self.items: List[CapturedImage] = []
        self._seen: Set[str] = set()
        self._errors: List[str] = []
        page.on("response", self._on_response)

    # ---------------------------------------------------------- collection --
    def ignore_files(self, paths) -> None:
        """Mark local files as uploads so their echo is never taken as a result."""
        for p in paths:
            try:
                self.ignore.add(hashlib.sha256(open(p, "rb").read()).hexdigest())
            except OSError:
                continue

    def _on_response(self, response) -> None:
        try:
            url = response.url
            if not any(m in url for m in IMAGE_URL_MARKERS):
                return
            ctype = (response.headers or {}).get("content-type", "")
            if not ctype.startswith("image/"):
                return
            body = response.body()
            if not body or len(body) < self.MIN_BYTES:
                return
            sha = hashlib.sha256(body).hexdigest()
            if sha in self.ignore or sha in self._seen:
                return                            # our own upload, or a re-render
            self._seen.add(sha)
            self.items.append(CapturedImage(url, body, ctype))
        except Exception as e:                    # noqa: BLE001 - never break the page
            self._errors.append(str(e)[:120])

    def drain(self, settle_ms: int = 2500, rounds: int = 3) -> int:
        """Treat everything captured so far as pre-existing, not a result.

        The ChatGPT Project page carries images from other episodes and other
        conversations. Those load as ordinary image responses, and without this
        the first batch "completes" instantly by collecting somebody else's
        artwork. Verified live: a 5-frame batch finished in 15s holding five
        unrelated images.
        """
        for _ in range(rounds):
            before = len(self.items)
            self.page.wait_for_timeout(settle_ms)
            if len(self.items) == before:
                break
        moved = len(self.items)
        for i in self.items:
            self.ignore.add(i.sha256)
        self.items.clear()
        return moved

    # ------------------------------------------------------------- waiting --
    def count_since(self, since: float) -> int:
        return sum(1 for i in self.items if i.at >= since)

    def since(self, ts: float) -> List[CapturedImage]:
        return [i for i in self.items if i.at >= ts]

    def wait_for(self, want: int, since: float, timeout_s: int,
                 settle_s: float = 45.0, poll_ms: int = 700,
                 min_elapsed_s: float = 0.0) -> List[CapturedImage]:
        """Wait for `want` new images to arrive after `since`.

        Returns as soon as `want` have arrived, or after the stream goes quiet
        for `settle_s` (which is how a short batch - ChatGPT returning fewer
        images than asked - surfaces instead of hanging to the full timeout).
        """
        started = time.time()
        deadline = started + timeout_s
        last_count, last_change = self.count_since(since), started
        while time.time() < deadline:
            n = self.count_since(since)
            if n != last_count:
                last_count, last_change = n, time.time()
            elapsed = time.time() - started
            if n >= want and elapsed >= min_elapsed_s:
                # let a trailing image land before we call it done
                self.page.wait_for_timeout(1500)
                return self.since(since)
            # Only call it a short batch once the stream has been quiet for a
            # while AND enough time has passed that a generation could have
            # finished - otherwise an early upload echo ends the wait.
            if n > 0 and elapsed >= min_elapsed_s and (time.time() - last_change) > settle_s:
                return self.since(since)
            self.page.wait_for_timeout(poll_ms)
        return self.since(since)

    # -------------------------------------------------------------- health --
    def stats(self) -> Dict:
        return {"captured": len(self.items), "ignored_hashes": len(self.ignore),
                "errors": self._errors[-3:]}
