from pathlib import Path

from conftest import write
from faceless.gates import check_beats, check_keyframes, check_package


def state(fmt="short", voice_mode="tts"):
    return {"format": fmt, "voice_mode": voice_mode}


def beat(i, start, end, **extra):
    return {"beat_id": f"B{i:03d}", "keyframe_id": f"KF{i:03d}", "start_s": start, "end_s": end, "text": "x", "visual_objective": "show x", **extra}


def rules(result):
    return {f.rule_id for f in result.findings if f.severity == "critical"}


def test_beats_gate_catches_gap_and_shared_keyframe(tmp_path: Path):
    manifest = {"audio_duration_s": 9.0, "beats": [beat(1, 0, 3), {**beat(2, 3.5, 6), "keyframe_id": "KF001"}, beat(3, 6, 9)]}
    found = rules(check_beats(manifest, tmp_path, state()))
    assert {"FF-SYNC-001", "FF-SYNC-003"} <= found


def test_beats_gate_requires_direction(tmp_path: Path):
    manifest = {"audio_duration_s": 3.0, "beats": [{**beat(1, 0, 3), "visual_objective": ""}]}
    assert "FF-DIR-001" in rules(check_beats(manifest, tmp_path, state()))


def test_keyframe_recast_is_critical(tmp_path: Path):
    write(tmp_path / "06-beats/beat_manifest.json", {"audio_duration_s": 3, "beats": [beat(1, 0, 3)]})
    manifest = {"keyframes": [{"keyframe_id": "KF001", "beat_id": "B009", "path": "missing.png", "sha256": "a", "source": "x", "qa_status": "pass"}]}
    assert {"FF-KF-002", "FF-KF-004"} <= rules(check_keyframes(manifest, tmp_path, state()))


def test_package_gate_limits(tmp_path: Path):
    pkg = {"vidiq_used": False, "youtube": {"title": "x" * 101, "description": "d", "tags": ["t" * 501], "hashtags": ["#a"] * 16,
                                            "chapters": [{"time": "0:05", "title": "a"}]}}
    found = rules(check_package(pkg, tmp_path, state("longform")))
    assert {"FF-PKG-001", "FF-PKG-004", "FF-PKG-005", "FF-PKG-007", "FF-PKG-008"} <= found
