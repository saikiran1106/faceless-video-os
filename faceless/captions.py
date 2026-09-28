"""Word timings -> caption pages -> SRT.

When a script exists (AI-voice mode, or a creator who pasted their script), the
caption TEXT comes from the script - exact spelling, names and punctuation - and
only the TIMING comes from the transcript. ASR misspellings never reach the screen.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from typing import Any

PUNCT = re.compile(r"[^\w]+", re.UNICODE)
SENTENCE_END = re.compile(r"[.!?।॥。！？]['\"”’)]*$")


def normalize(token: str) -> str:
    token = unicodedata.normalize("NFC", token).lower()
    return PUNCT.sub("", token)


def align_script_words(script_text: str, words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Give every script word a start/end taken from the transcript.

    Matched runs copy timings 1:1. Replaced or inserted runs are spread evenly across
    the time span the transcript used for that stretch, so nothing is left untimed.
    """
    script_tokens = script_text.split()
    if not script_tokens or not words:
        return [dict(w) for w in words]
    a = [normalize(t) for t in script_tokens]
    b = [normalize(w["text"]) for w in words]
    out: list[dict[str, Any] | None] = [None] * len(script_tokens)
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                w = words[j1 + k]
                out[i1 + k] = {"text": script_tokens[i1 + k], "start": w["start"], "end": w["end"]}
        elif tag in ("replace", "insert") and i2 > i1:
            if j2 > j1:
                start, end = words[j1]["start"], words[j2 - 1]["end"]
            else:  # pure insertion: squeeze between neighbours
                start = words[j1 - 1]["end"] if j1 > 0 else 0.0
                end = words[j1]["start"] if j1 < len(words) else start + 0.3 * (i2 - i1)
            span = max(end - start, 0.05 * (i2 - i1))
            step = span / (i2 - i1)
            for k in range(i2 - i1):
                out[i1 + k] = {"text": script_tokens[i1 + k], "start": start + k * step, "end": start + (k + 1) * step}
    return [w for w in out if w is not None]


def build_pages(words: list[dict[str, Any]], max_words: int, max_chars: int, pause_break_s: float = 0.35) -> list[dict[str, Any]]:
    """Group words into on-screen caption pages.

    A page breaks at the word/char limit, at a sentence end, or at a natural pause.
    Each page stays up until the next page starts (no flicker between pages).
    """
    pages: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []

    def flush() -> None:
        if current:
            pages.append({"start": current[0]["start"], "end": current[-1]["end"], "words": list(current)})
            current.clear()

    for index, word in enumerate(words):
        text = " ".join(w["text"] for w in current + [word])
        if current and (len(current) >= max_words or len(text) > max_chars or word["start"] - current[-1]["end"] > pause_break_s):
            flush()
        current.append(word)
        nxt = words[index + 1] if index + 1 < len(words) else None
        if SENTENCE_END.search(word["text"]) or nxt is None:
            flush()
    for index in range(len(pages) - 1):
        gap = pages[index + 1]["start"] - pages[index]["end"]
        if 0 < gap < 0.6:
            pages[index]["end"] = pages[index + 1]["start"]
    return pages


def _ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(pages: list[dict[str, Any]]) -> str:
    blocks = []
    for index, page in enumerate(pages, 1):
        text = " ".join(w["text"] for w in page["words"])
        blocks.append(f"{index}\n{_ts(page['start'])} --> {_ts(page['end'])}\n{text}\n")
    return "\n".join(blocks)


def caption_words(transcript: dict[str, Any], script: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Script-spelled words when a script exists and it matches the audio well enough."""
    words = transcript["words"]
    if script and script.get("source") == "written":
        ratio = (transcript.get("script_match") or {}).get("ratio", 0)
        if ratio >= 0.6:
            return align_script_words(script["narration"], words)
    return [dict(w) for w in words]
