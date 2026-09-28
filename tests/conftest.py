import json
from pathlib import Path

import pytest

from faceless.engine import ProductionEngine


@pytest.fixture
def make_project(tmp_path: Path):
    def _make(voice_mode: str = "tts", fmt: str = "short", budget: float = 10.0) -> ProductionEngine:
        return ProductionEngine.initialize(tmp_path / "projects", "test-video", "Test Video", fmt, voice_mode, "manual", "en", budget)

    return _make


def write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def words_from(text: str, start: float = 0.0, per_word: float = 0.4, gap_after_sentence: float = 0.3):
    out, t = [], start
    for token in text.split():
        out.append({"text": token, "start": round(t, 3), "end": round(t + per_word * 0.9, 3)})
        t += per_word
        if token.endswith((".", "?", "!")):
            t += gap_after_sentence
    return out
