import pytest

from conftest import write
from faceless.engine import StateError
from faceless.stages import STAGE_ORDER


def brief(voice_mode="tts", fmt="short"):
    return {"topic": "t", "title": "T", "format": fmt, "language": "en", "target_duration_s": 50, "voice_mode": voice_mode,
            "promise": {"question": "q", "payoff": "p"}}


def test_stage_order_depends_on_voice_mode(make_project):
    order = make_project("tts").state()["stage_order"]
    assert order == list(STAGE_ORDER["tts"])
    assert order.index("script") < order.index("voice")


def test_upload_mode_transcribes_before_script(tmp_path):
    from faceless.engine import ProductionEngine

    engine = ProductionEngine.initialize(tmp_path, "u", "U", "short", "upload", "manual")
    order = engine.state()["stage_order"]
    assert order.index("transcript") < order.index("script")


def test_complete_advances_and_hash_binds(make_project):
    engine = make_project()
    write(engine.artifact_path("brief"), brief())
    state = engine.complete("brief")
    assert state["stages"]["brief"]["status"] == "completed"
    assert state["current_stage"] == "script"


def test_failed_gate_keeps_stage_current(make_project):
    engine = make_project()
    write(engine.artifact_path("brief"), {**brief(), "voice_mode": "upload"})
    state = engine.complete("brief")
    assert state["stages"]["brief"]["status"] == "failed"
    assert state["current_stage"] == "brief"


def test_cannot_complete_out_of_order(make_project):
    engine = make_project()
    with pytest.raises(StateError):
        engine.complete("voice")


def test_human_gate_and_edit_after_gate_blocks_approval(make_project):
    engine = make_project()
    write(engine.artifact_path("brief"), brief())
    engine.complete("brief")
    narration = " ".join(["word"] * 140)
    script = {"language": "en", "title": "T", "source": "written", "narration": narration, "hook": {"text": "word word"},
              "promise": {"question": "q", "payoff": "p"}, "sections": [{"section_id": "S1", "title": "one", "text": narration}]}
    write(engine.artifact_path("script"), script)
    state = engine.complete("script")
    assert state["stages"]["script"]["status"] == "awaiting_human"
    write(engine.artifact_path("script"), {**script, "title": "Changed"})
    with pytest.raises(StateError):
        engine.approve("cp1_story", "tester")
    write(engine.artifact_path("script"), script)
    state = engine.approve("cp1_story", "tester")
    assert state["current_stage"] == "voice"


def test_budget_blocks_and_costs_are_idempotent(make_project):
    engine = make_project(budget=1.0)
    engine.record_cost(0.6, "x", "op-1", "voice")
    engine.record_cost(0.6, "x", "op-1", "voice")  # same operation: not charged twice
    assert engine.state()["budget"]["spent_usd"] == pytest.approx(0.6)
    with pytest.raises(StateError):
        engine.record_cost(0.6, "x", "op-2", "voice")


def test_reopen_invalidates_later_stages(make_project):
    engine = make_project()
    write(engine.artifact_path("brief"), brief())
    engine.complete("brief")
    engine.reopen("brief", "new angle")
    state = engine.state()
    assert state["current_stage"] == "brief"
    assert state["stages"]["brief"]["status"] == "pending"
