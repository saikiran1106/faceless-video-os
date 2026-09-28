"""Provider adapters. Each one is a small class with the same shape as its siblings,
so adding a new vendor means adding one class and one line in the registry.

Selection order (when a stage's provider is "auto") is defined in `select_*`
and documented in docs/05-providers.md.
"""
from __future__ import annotations

import re

from ..config import has_key

SENTENCE_END = re.compile(r"(?<=[.!?।॥。！？])\s+|\n+")


class ProviderError(RuntimeError):
    pass


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE_END.split(text) if part and part.strip()]


def chunk_text(text: str, max_chars: int) -> list[str]:
    """Pack whole sentences into chunks under `max_chars`. Never splits a sentence
    unless the sentence alone is longer than the limit (then it splits on commas/spaces)."""
    chunks: list[str] = []
    current = ""
    for sentence in split_sentences(text):
        pieces = [sentence] if len(sentence) <= max_chars else _hard_split(sentence, max_chars)
        for piece in pieces:
            candidate = f"{current} {piece}".strip()
            if current and len(candidate) > max_chars:
                chunks.append(current)
                current = piece
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks


def _hard_split(sentence: str, max_chars: int) -> list[str]:
    out, current = [], ""
    for token in re.split(r"(?<=[,;:،])\s+|\s+", sentence):
        candidate = f"{current} {token}".strip()
        if current and len(candidate) > max_chars:
            out.append(current)
            current = token
        else:
            current = candidate
    if current:
        out.append(current)
    return out


def available_providers() -> dict[str, list[str]]:
    """What this machine can use right now, per capability, in preference order."""
    from .transcribe import local_whisper_available

    tts, asr, image = [], [], []
    if has_key("ELEVENLABS_API_KEY"):
        tts.append("elevenlabs")
        asr.append("elevenlabs")
    if has_key("OPENAI_API_KEY"):
        tts.append("openai")
        asr.append("openai")
        image.append("openai")
    if local_whisper_available():
        asr.append("local")
    return {"tts": tts, "transcribe": asr, "image_api": image}
