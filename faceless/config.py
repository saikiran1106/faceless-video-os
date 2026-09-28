"""Locating the repo, loading `.env`, the channel config and format profiles."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parent
SCHEMA_ROOT = PACKAGE_ROOT / "schemas"
PROFILE_ROOT = PACKAGE_ROOT / "profiles"


def repo_root(start: Path | None = None) -> Path:
    """The nearest directory above `start` that holds a `channel.json` or the composer.

    Falls back to the package's parent, which is the repo when run from a clone.
    """
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "channel.json").exists() or (candidate / "composer" / "package.json").exists():
            return candidate
    return PACKAGE_ROOT.parent


def load_dotenv(path: Path | None = None) -> None:
    """Minimal .env loader: KEY=VALUE lines, no overriding of real env vars."""
    env_path = path or repo_root() / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def env(name: str, default: str = "") -> str:
    value = os.environ.get(name, default)
    return value.strip() if isinstance(value, str) else default


def has_key(name: str) -> bool:
    """True when an API key looks real, not a placeholder copied from .env.example."""
    value = env(name)
    return bool(value) and not value.lower().startswith(("your_", "xxx", "changeme", "<"))


@lru_cache(maxsize=8)
def load_profile(content_format: str) -> dict[str, Any]:
    path = PROFILE_ROOT / f"{content_format}.json"
    if not path.exists():
        raise ValueError(f"No profile for format {content_format!r} at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


DEFAULT_CHANNEL: dict[str, Any] = {
    "channel_name": "My Channel",
    "language": "en",
    "niche": "",
    "voice": {"provider": "auto", "elevenlabs_voice_id": "", "elevenlabs_model": "eleven_multilingual_v2", "openai_voice": "onyx", "openai_model": "gpt-4o-mini-tts", "style_instructions": ""},
    "style": {"caption_font": "Noto Sans", "font_file": "", "caption_color": "#FFFFFF", "highlight_color": "#FFD400", "accent_color": "#E53935", "caption_case": "as_spoken"},
    "cta": {"hook_seconds": 3.0, "subscribe_text": "Subscribe for more", "comment_text": "Comment your answer below", "end_card_seconds": 3.0},
    "music": {"default_track": "", "volume": 0.12},
    "packaging": {"default_hashtags": [], "default_tags": []},
}


def load_channel(root: Path | None = None) -> dict[str, Any]:
    """channel.json merged over defaults, so a partial file still works."""
    path = (root or repo_root()) / "channel.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return _deep_merge(DEFAULT_CHANNEL, data)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
