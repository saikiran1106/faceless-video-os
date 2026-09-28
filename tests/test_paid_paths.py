"""Provider paths exercised with fake HTTP, so no key or credit is ever used in tests."""
import base64
import io
import json
import shutil

import pytest
from PIL import Image

from conftest import write

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


class FakeResponse:
    def __init__(self, status=200, body=None, content=b""):
        self.status_code, self._body, self.content = status, body, content
        self.text = json.dumps(body) if body is not None else ""

    def json(self):
        return self._body


def tone_mp3(tmp_path, seconds=1.0):
    from faceless.media import require, run

    out = tmp_path / f"tone_{seconds}.mp3"
    run([require("ffmpeg"), "-y", "-f", "lavfi", "-i", f"sine=frequency=300:duration={seconds}", "-ac", "1", str(out)])
    return out.read_bytes()


def approved_tts_project(make_project):
    engine = make_project("tts", budget=5.0)
    write(engine.artifact_path("brief"), {"topic": "t", "title": "T", "format": "short", "language": "en", "target_duration_s": 30, "voice_mode": "tts", "promise": {"question": "q", "payoff": "p"}})
    engine.complete("brief")
    narration = " ".join(f"Sentence number {i} is here." for i in range(16))
    write(engine.artifact_path("script"), {"language": "en", "title": "T", "source": "written", "narration": narration, "hook": {"text": "Sentence number 0 is here."},
                                          "promise": {"question": "q", "payoff": "p"}, "sections": [{"section_id": "S1", "title": "all", "text": narration}]})
    engine.complete("script")
    engine.approve("cp1_story", "tester")
    return engine


def test_openai_tts_generate_chunks_caches_and_budgets(make_project, monkeypatch, tmp_path):
    from faceless import voice
    from faceless.providers import tts

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    audio = tone_mp3(tmp_path)
    calls = []
    monkeypatch.setattr(tts.requests, "post", lambda url, **kw: calls.append(kw["json"]["input"]) or FakeResponse(content=audio))
    monkeypatch.setattr(tts.OpenAITTS, "max_chars", 120)
    engine = approved_tts_project(make_project)

    manifest = voice.generate(engine, provider="openai")
    assert len(calls) == len(manifest["chunks"]) > 1
    assert (engine.project_root / manifest["master_path"]).exists()
    spent = engine.state()["budget"]["spent_usd"]
    assert spent > 0

    voice.generate(engine, provider="openai")          # unchanged text: nothing re-bought
    assert len(calls) == len(manifest["chunks"])
    assert engine.state()["budget"]["spent_usd"] == spent

    voice.generate(engine, provider="openai", only_chunk="C002")   # one forced retake
    assert len(calls) == len(manifest["chunks"]) + 1


def test_scribe_parsing_and_script_match(make_project, monkeypatch, tmp_path):
    from faceless import transcript, voice
    from faceless.providers import transcribe as asr, tts

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    monkeypatch.setattr(tts.requests, "post", lambda url, **kw: FakeResponse(content=tone_mp3(tmp_path, 2.0)))
    engine = approved_tts_project(make_project)
    voice.generate(engine, provider="openai")
    engine.complete("voice")

    script_words = json.loads(engine.artifact_path("script").read_text())["narration"].split()
    body = {"language_code": "en", "text": " ".join(script_words), "words": []}
    t = 0.0
    for w in script_words:
        body["words"] += [{"text": w, "start": t, "end": t + 0.2, "type": "word"}, {"text": " ", "start": t + 0.2, "end": t + 0.25, "type": "spacing"}]
        t += 0.25
    monkeypatch.setenv("ELEVENLABS_API_KEY", "xi-test-not-real")
    monkeypatch.setattr(asr.requests, "post", lambda url, **kw: FakeResponse(body=body))
    out = transcript.run(engine, "elevenlabs")
    assert out["word_count"] == len(script_words)
    doc = json.loads(engine.artifact_path("transcript").read_text())
    assert doc["script_match"]["ratio"] == 1.0


def test_openai_whisper_word_parsing(monkeypatch, tmp_path):
    from faceless.providers import transcribe as asr

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    src = tmp_path / "a.mp3"
    src.write_bytes(tone_mp3(tmp_path))
    monkeypatch.setattr(asr.requests, "post", lambda url, **kw: FakeResponse(body={"language": "english", "text": "Hi there.", "words": [{"word": "Hi", "start": 0.0, "end": 0.3}, {"word": "there.", "start": 0.3, "end": 0.7}]}))
    result = asr.transcribe(src, "openai", "en", tmp_path)
    assert [w["text"] for w in result["words"]] == ["Hi", "there."]


def test_image_api_records_and_rejects_wrong_aspect(make_project, monkeypatch, tmp_path):
    from faceless import imagejobs
    from faceless.providers import images

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    engine = make_project("upload", budget=5.0)
    write(engine.artifact_path("visual_bible"), {"aspect": "9:16", "style_contract": "s" * 50, "characters": [], "locations": []})
    write(engine.artifact_path("beats"), {"audio_duration_s": 4, "beats": [
        {"beat_id": "B001", "keyframe_id": "KF001", "start_s": 0, "end_s": 2, "text": "a", "visual_objective": "show a"},
        {"beat_id": "B002", "keyframe_id": "KF002", "start_s": 2, "end_s": 4, "text": "b", "visual_objective": "show b"}]})
    imagejobs.compile_jobs(engine)

    def png(size):
        buf = io.BytesIO()
        Image.new("RGB", size, (9, 9, 9)).save(buf, "PNG")
        return base64.b64encode(buf.getvalue()).decode()

    sizes = iter([(1024, 1536), (1536, 1024)])  # a 2:3 portrait is cropped to 9:16; a landscape is rejected
    monkeypatch.setattr(images.requests, "post", lambda url, **kw: FakeResponse(body={"data": [{"b64_json": png(next(sizes))}]}))
    result = imagejobs.generate_api(engine)
    assert result["generated"] == ["KF001"], result
    assert result["failed"][0]["keyframe_id"] == "KF002" and "9:16" in result["failed"][0]["error"]
    assert engine.state()["budget"]["spent_usd"] > 0
    receipt = json.loads((engine.project_root / "07-keyframes/receipts/KF001.json").read_text())
    assert receipt["cropped_from"] == [1024, 1536]
    assert abs(receipt["width"] / receipt["height"] - 9 / 16) < 0.01
