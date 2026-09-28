"""Text-to-speech adapters: ElevenLabs and OpenAI.

Both expose `max_chars`, `estimate_usd(chars)` and `synthesize(text, dest) -> Path`.
Pricing defaults are conservative and overridable by env var, because plans differ.
"""
from __future__ import annotations

from pathlib import Path

import requests

from ..config import env, has_key
from . import ProviderError


class ElevenLabsTTS:
    name = "elevenlabs"
    max_chars = 2500  # well under the API cap; shorter chunks drift less

    def __init__(self, voice_id: str, model: str = "eleven_multilingual_v2", stability: float = 0.5, similarity: float = 0.75, style: float = 0.0):
        if not has_key("ELEVENLABS_API_KEY"):
            raise ProviderError("ELEVENLABS_API_KEY is not set")
        if not voice_id:
            raise ProviderError("No ElevenLabs voice_id. Set voice.elevenlabs_voice_id in channel.json or pass --voice-id.")
        self.voice_id, self.model = voice_id, model
        self.settings = {"stability": stability, "similarity_boost": similarity, "style": style, "use_speaker_boost": True}

    @staticmethod
    def estimate_usd(chars: int) -> float:
        return chars / 1000 * float(env("FACELESS_ELEVENLABS_USD_PER_1K_CHARS", "0.30"))

    def synthesize(self, text: str, dest: Path, previous_text: str = "", next_text: str = "") -> Path:
        body: dict = {"text": text, "model_id": self.model, "voice_settings": self.settings}
        # Context stitching keeps prosody continuous across chunks (not supported by v3 models).
        if not self.model.startswith("eleven_v3"):
            if previous_text:
                body["previous_text"] = previous_text[-500:]
            if next_text:
                body["next_text"] = next_text[:500]
        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}",
            params={"output_format": "mp3_44100_128"},
            headers={"xi-api-key": env("ELEVENLABS_API_KEY"), "Content-Type": "application/json"},
            json=body,
            timeout=300,
        )
        if response.status_code != 200:
            raise ProviderError(f"ElevenLabs TTS {response.status_code}: {response.text[:300]}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.content)
        return dest


class OpenAITTS:
    name = "openai"
    max_chars = 3800  # API input cap is 4096 characters

    def __init__(self, voice: str = "onyx", model: str = "gpt-4o-mini-tts", instructions: str = ""):
        if not has_key("OPENAI_API_KEY"):
            raise ProviderError("OPENAI_API_KEY is not set")
        self.voice, self.model, self.instructions = voice, model, instructions

    @staticmethod
    def estimate_usd(chars: int) -> float:
        return chars / 1000 * float(env("FACELESS_OPENAI_TTS_USD_PER_1K_CHARS", "0.015"))

    def synthesize(self, text: str, dest: Path, previous_text: str = "", next_text: str = "") -> Path:
        body = {"model": self.model, "voice": self.voice, "input": text, "response_format": "mp3"}
        if self.instructions and not self.model.startswith("tts-1"):
            body["instructions"] = self.instructions
        response = requests.post(
            f"{env('OPENAI_BASE_URL', 'https://api.openai.com/v1')}/audio/speech",
            headers={"Authorization": f"Bearer {env('OPENAI_API_KEY')}"},
            json=body,
            timeout=300,
        )
        if response.status_code != 200:
            raise ProviderError(f"OpenAI TTS {response.status_code}: {response.text[:300]}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.content)
        return dest


def select_tts(channel: dict, provider: str = "auto", voice_id: str = "", model: str = ""):
    voice = channel.get("voice", {})
    choice = provider if provider != "auto" else voice.get("provider", "auto")
    if choice == "auto":
        if has_key("ELEVENLABS_API_KEY") and (voice_id or voice.get("elevenlabs_voice_id")):
            choice = "elevenlabs"
        elif has_key("OPENAI_API_KEY"):
            choice = "openai"
        else:
            raise ProviderError(
                "No TTS provider is configured. Add ELEVENLABS_API_KEY (+ a voice id) or OPENAI_API_KEY to .env, "
                "or switch this project to your own recording with `faceless voice ingest`."
            )
    if choice == "elevenlabs":
        return ElevenLabsTTS(voice_id or voice.get("elevenlabs_voice_id", ""), model or voice.get("elevenlabs_model", "eleven_multilingual_v2"))
    if choice == "openai":
        return OpenAITTS(voice_id or voice.get("openai_voice", "onyx"), model or voice.get("openai_model", "gpt-4o-mini-tts"), voice.get("style_instructions", ""))
    raise ProviderError(f"Unknown TTS provider {choice!r}")
