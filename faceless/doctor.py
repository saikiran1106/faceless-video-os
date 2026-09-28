"""`faceless doctor`: what can this machine do right now, and what is one step away?"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .config import has_key, load_channel, repo_root
from .contracts import load_schema
from .providers import available_providers
from .stages import STAGE_SCHEMAS

SKILLS = ("faceless-produce", "faceless-script", "faceless-voice", "faceless-transcribe", "faceless-visuals", "faceless-compose", "faceless-package", "faceless-review", "faceless-resume")


def _version(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.strip().splitlines()[0]
    except Exception:  # noqa: BLE001
        return ""


def run_doctor(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    checks: list[dict[str, str]] = []

    def add(name: str, ok: bool, detail: str, fix: str = "", severity: str = "critical") -> None:
        checks.append({"check": name, "status": "ok" if ok else severity, "detail": detail, **({"fix": fix} if not ok and fix else {})})

    add("ffmpeg", bool(shutil.which("ffmpeg") and shutil.which("ffprobe")), _version(["ffmpeg", "-version"]) or "missing", "macOS: brew install ffmpeg | Ubuntu: sudo apt install ffmpeg | Windows: winget install ffmpeg")
    node = _version(["node", "--version"])
    add("node", bool(node), node or "missing", "Install Node.js 18+ from nodejs.org (needed for Remotion rendering)", "warning")
    composer = root / "composer"
    add("composer_deps", (composer / "node_modules").exists(), str(composer / "node_modules"), f"cd {composer} && npm install", "warning")
    add("channel_config", (root / "channel.json").exists(), str(root / "channel.json"), "faceless setup  (copies channel.example.json)", "warning")
    for schema in STAGE_SCHEMAS.values():
        try:
            load_schema(schema)
        except Exception as exc:  # noqa: BLE001
            add(f"schema:{schema}", False, str(exc))
    for skill in SKILLS:
        canonical = root / "skills" / skill / "SKILL.md"
        add(f"skill:{skill}", canonical.exists(), str(canonical), "Restore skills/ from the repo")
        for mirror in (".claude/skills", ".agents/skills"):
            copy = root / mirror / skill / "SKILL.md"
            if canonical.exists() and (not copy.exists() or copy.read_bytes() != canonical.read_bytes()):
                add(f"mirror:{mirror}/{skill}", False, "out of sync with skills/", "faceless skills sync", "warning")

    providers = available_providers()
    playwright = importlib.util.find_spec("playwright") is not None
    channel = load_channel(root)
    voice_id = channel["voice"].get("elevenlabs_voice_id")
    capabilities = {
        "voice_ai": providers["tts"] or ["none - use your own recording (voice mode: upload)"],
        "voice_upload": ["always available"],
        "transcription": providers["transcribe"] or ["none"],
        "keyframes": [
            "codex (built-in image tool, when running inside Codex)",
            *(["claude-code (ChatGPT via Playwright browser)"] if playwright else []),
            *(["api (OpenAI Images)"] if "openai" in providers["image_api"] else []),
            "manual (copy prompts to any image tool)",
        ],
        "render": [*(["remotion"] if node and (composer / "node_modules").exists() else []), "ffmpeg (fallback, no captions)"],
        "packaging": ["vidIQ MCP (if connected in your agent)", "built-in rules"],
    }
    if not providers["transcribe"]:
        add("transcription", False, "no transcription provider", "Add ELEVENLABS_API_KEY or OPENAI_API_KEY to .env, or pip install 'faceless-video-os[local-asr]' (free, local)", "warning")
    if has_key("ELEVENLABS_API_KEY") and not voice_id:
        add("elevenlabs_voice", False, "ELEVENLABS_API_KEY set but no voice.elevenlabs_voice_id in channel.json", "Pick a voice at elevenlabs.io/app/voice-library and paste its id", "warning")
    upgrades = []
    if not has_key("ELEVENLABS_API_KEY"):
        upgrades.append("ELEVENLABS_API_KEY -> premium/cloned AI voice + Scribe transcription (best for non-English)")
    if not has_key("OPENAI_API_KEY"):
        upgrades.append("OPENAI_API_KEY -> OpenAI TTS voice, Whisper transcription, and direct image API")
    if not playwright:
        upgrades.append("pip install 'faceless-video-os[browser]' && playwright install chromium -> ChatGPT image generation from Claude Code")
    if not providers["transcribe"] or "local" not in providers["transcribe"]:
        upgrades.append("pip install 'faceless-video-os[local-asr]' -> free offline transcription (faster-whisper)")
    passed = not any(c["status"] == "critical" for c in checks)
    return {"passed": passed, "capabilities": capabilities, "checks": [c for c in checks if c["status"] != "ok"], "ok": [c["check"] for c in checks if c["status"] == "ok"], "one_step_upgrades": upgrades}
