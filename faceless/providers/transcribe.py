"""Word-timestamped transcription: ElevenLabs Scribe -> OpenAI Whisper -> local faster-whisper.

Every adapter returns the same shape:
    {"provider", "model", "language", "text", "words": [{"text", "start", "end"}]}
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import requests

from ..config import env, has_key
from ..media import compress_for_upload, duration
from . import ProviderError


def local_whisper_available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def estimate_usd(provider: str, seconds: float) -> float:
    per_min = {"elevenlabs": float(env("FACELESS_SCRIBE_USD_PER_MIN", "0.0067")), "openai": float(env("FACELESS_WHISPER_USD_PER_MIN", "0.006")), "local": 0.0}
    return per_min.get(provider, 0.0) * seconds / 60


def select_transcriber(provider: str = "auto") -> str:
    if provider != "auto":
        return provider
    if has_key("ELEVENLABS_API_KEY"):
        return "elevenlabs"
    if has_key("OPENAI_API_KEY"):
        return "openai"
    if local_whisper_available():
        return "local"
    raise ProviderError(
        "No transcription provider. Add ELEVENLABS_API_KEY or OPENAI_API_KEY to .env, "
        "or install the free local model: pip install 'faceless-forge[local-asr]'"
    )


def transcribe(audio: Path, provider: str, language: str = "", work_dir: Path | None = None) -> dict[str, Any]:
    if provider == "elevenlabs":
        return _elevenlabs(audio, language)
    if provider == "openai":
        return _openai(audio, language, work_dir or audio.parent)
    if provider == "local":
        return _local(audio, language)
    raise ProviderError(f"Unknown transcription provider {provider!r}")


def _elevenlabs(audio: Path, language: str) -> dict[str, Any]:
    model = env("FACELESS_SCRIBE_MODEL", "scribe_v2")
    data = {"model_id": model, "timestamps_granularity": "word", "tag_audio_events": "false"}
    if language:
        data["language_code"] = language
    with audio.open("rb") as handle:
        response = requests.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": env("ELEVENLABS_API_KEY")},
            data=data,
            files={"file": (audio.name, handle)},
            timeout=1800,
        )
    if response.status_code != 200:
        raise ProviderError(f"ElevenLabs Scribe {response.status_code}: {response.text[:300]}")
    body = response.json()
    words = [
        {"text": w["text"].strip(), "start": float(w["start"]), "end": float(w["end"])}
        for w in body.get("words", [])
        if w.get("type", "word") == "word" and w.get("text", "").strip()
    ]
    return {"provider": "elevenlabs", "model": model, "language": body.get("language_code", language), "text": body.get("text", "").strip(), "words": words}


def _openai(audio: Path, language: str, work_dir: Path) -> dict[str, Any]:
    # whisper-1 is the OpenAI model that returns word-level timestamps.
    model = env("FACELESS_OPENAI_ASR_MODEL", "whisper-1")
    upload = audio
    if audio.stat().st_size > 24 * 1024 * 1024 or audio.suffix.lower() == ".wav":
        upload = compress_for_upload(audio, work_dir / f"{audio.stem}.asr.mp3")
    if upload.stat().st_size > 25 * 1024 * 1024:
        raise ProviderError(f"Audio is still over OpenAI's 25 MB cap after compression ({duration(audio)/60:.0f} min). Use ElevenLabs or local.")
    data: list[tuple[str, str]] = [("model", model), ("response_format", "verbose_json"), ("timestamp_granularities[]", "word"), ("timestamp_granularities[]", "segment")]
    if language:
        data.append(("language", language))
    with upload.open("rb") as handle:
        response = requests.post(
            f"{env('OPENAI_BASE_URL', 'https://api.openai.com/v1')}/audio/transcriptions",
            headers={"Authorization": f"Bearer {env('OPENAI_API_KEY')}"},
            data=data,
            files={"file": (upload.name, handle)},
            timeout=1800,
        )
    if response.status_code != 200:
        raise ProviderError(f"OpenAI transcription {response.status_code}: {response.text[:300]}")
    body = response.json()
    words = [{"text": w["word"].strip(), "start": float(w["start"]), "end": float(w["end"])} for w in body.get("words", []) if w.get("word", "").strip()]
    return {"provider": "openai", "model": model, "language": body.get("language", language), "text": body.get("text", "").strip(), "words": words}


def _local(audio: Path, language: str) -> dict[str, Any]:
    from faster_whisper import WhisperModel  # optional dependency

    model_name = env("FACELESS_LOCAL_WHISPER_MODEL", "small")
    model = WhisperModel(model_name, device=env("FACELESS_LOCAL_WHISPER_DEVICE", "auto"), compute_type="int8")
    segments, info = model.transcribe(str(audio), language=language or None, word_timestamps=True, vad_filter=True)
    words, texts = [], []
    for segment in segments:
        texts.append(segment.text.strip())
        for w in segment.words or []:
            if w.word.strip():
                words.append({"text": w.word.strip(), "start": float(w.start), "end": float(w.end)})
    return {"provider": "local", "model": f"faster-whisper/{model_name}", "language": info.language, "text": " ".join(texts), "words": words}
