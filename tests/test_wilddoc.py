"""Wild-doc pipeline: script parsing, script<->audio alignment, shot-list grammar, plan building (offline, no keys)."""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from faceless.wilddoc import WildDocError
from faceless.wilddoc import align as A
from faceless.wilddoc import shotlist as SL
from faceless.wilddoc.project import Project, norm, write_json

SCRIPT = """## The challenge
Imagine you were sent back in time. No phone, no fire, no weapon.
## The cold
At six in the evening the temperature starts to fall.
"""


def _heard(text: str, t0: float = 0.2, step: float = 0.4):
    out, t = [], t0
    for w in text.split():
        out.append({"text": w, "start": round(t, 3), "end": round(t + step * 0.8, 3)})
        t += step
    return out


def test_parse_script_chapters_and_sentence_split():
    s = A.parse_script(SCRIPT)
    assert [c["name"] for c in s["chapters"]] == ["the-challenge", "the-cold"]
    assert [ln["text"] for ln in s["lines"]][:2] == ["Imagine you were sent back in time.", "No phone, no fire, no weapon."]
    assert [ln["i"] for ln in s["lines"]] == [1, 2, 3]
    assert len(A.parse_script(SCRIPT, split_sentences=False)["lines"]) == 2


def test_norm_strips_punctuation_and_danda():
    assert norm("फौजिल।") == norm("फौजिल")
    assert norm("Phone,") == "phone"


def test_alignment_handles_misheard_dropped_and_extra_words():
    s = A.parse_script(SCRIPT)
    # the voice adds "okay", mishears "weapon" and drops the last line entirely
    heard = _heard("Imagine you were sent back in time okay No phone no fire no wepon")
    tl = A.build_timeline(s, {"words": heard}, duration=10.0)
    assert tl["stats"]["extra_spoken"] == ["okay"]
    lines = {ln["i"]: ln for ln in tl["lines"]}
    assert lines[1]["spoken"] and lines[2]["spoken"]
    assert not lines[3]["spoken"], "a dropped line keeps its slot but is not spoken"
    w = [x for x in tl["words"] if x["text"] == "weapon."][0]
    assert w["spoken"] and w["heard"] == "wepon"
    starts = [x["start"] for x in tl["words"]]
    assert starts == sorted(starts)
    assert [c["name"] for c in tl["chapters"]] == ["the-challenge"]  # chapter 2 has no spoken line
    assert tl["chapters"][0]["start"] == 0.0


def test_shotlist_grammar_and_errors():
    sl = SL.parse('L1: S:wolf_run@2 +t=whip +fx=snow ; fire=P:P01:crash +t=punch\n'
                  'O L1 fire kw 1.2 {"text":"FIRE"}\nX L1 fire fire_whoosh -10\n# comment\n')
    assert sl["rows"][1][1] == "fire=P:P01:crash +t=punch"
    assert sl["overlays"][0]["props"] == {"text": "FIRE"} and sl["story"][0]["gain"] == -10
    o = SL.parse_spec("S:wolf_run@2 +t=whip +fx=snow")
    assert o == {"kind": "stock", "name": "wolf_run", "off": 2.0, "trans": "whip", "fx": "snow"}
    assert SL.parse_spec("M:timeline#2")["key"] == "timeline#2"
    with pytest.raises(WildDocError):
        SL.parse("L1: S:x +t=teleport\n")
    with pytest.raises(WildDocError):
        SL.parse("Line one: nothing\n")


def _project(tmp_path):
    root = tmp_path / "p"
    for d in ("00-source", "01-audio", "02-direction", "06-assets", "08-compose/public/plates", "08-compose/public/depth", "09-package"):
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / "00-source/script.txt").write_text(SCRIPT)
    write_json(root / "project.json", {"slug": "p", "audio": "00-source/voice.wav"})
    write_json(root / "style.json", {"chapters": {"the-challenge": {"look": "night", "title": "Challenge"}}})
    s = A.parse_script(SCRIPT)
    heard = _heard("Imagine you were sent back in time No phone no fire no weapon At six in the evening the temperature starts to fall")
    write_json(root / "01-audio/timeline.json", A.build_timeline(s, {"words": heard}, duration=9.0))
    return Project(root)


def test_draft_then_plan_with_placeholders_and_jump_cuts(tmp_path):
    p = _project(tmp_path)
    text, plates = SL.draft(p.timeline(), p.style())
    assert set(plates) == {"L001", "L002", "L003"}
    p.shotlist_path.write_text(text)
    with pytest.raises(WildDocError, match="missing"):
        from faceless.wilddoc import plan as PL
        PL.build(p)
    from faceless.wilddoc import plan as PL

    rep = PL.build(p, allow_missing=True)
    plan = json.loads(p.plan_path.read_text())
    assert rep["missing"]["plates"] == ["L001", "L002", "L003"]
    assert plan["shots"][0]["from"] == 0
    assert all(s["dur"] / plan["fps"] <= 3.3 + 1e-6 for s in plan["shots"] if s["kind"] != "mg" or s.get("props", {}).get("kicker") == "MISSING PLATE")
    assert plan["chapters"][0]["title"] == "Challenge"
    assert plan["shots"][0]["look"] == "night"


def test_plan_places_cuts_and_overlays_on_words(tmp_path):
    p = _project(tmp_path)
    from PIL import Image

    for pid in ("A", "B"):
        Image.new("RGB", (64, 36)).save(p.p("public", "plates", f"{pid}.jpg"))
        Image.new("L", (64, 36)).save(p.p("public", "depth", f"{pid}_depth.png"))
    p.shotlist_path.write_text('L1: P:A ; time.=P:B:pull +t=glitch\nL2: P:B\nL3: P:A\nO L2 fire, kw 1.0 {"text":"NO FIRE"}\n')
    from faceless.wilddoc import plan as PL

    PL.build(p)
    plan = json.loads(p.plan_path.read_text())
    t_time = next(w for w in p.timeline()["words"] if w["text"] == "time.")["start"]
    cut = next(s for s in plan["shots"] if s.get("id") == "B" and s["line"] == 1)
    assert cut["from"] == round((t_time - 0.04) * 24) and cut["trans"] == "glitch"
    t_fire = next(w for w in p.timeline()["words"] if w["text"] == "fire,")["start"]
    assert plan["overlays"][0]["from"] == round((t_fire - 0.05) * 24)
    with pytest.raises(WildDocError, match="anchor 'tiger'"):
        p.shotlist_path.write_text("L1: P:A ; tiger=P:B\n")
        PL.build(p)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg needed")
def test_procedural_kit_writes_every_sound(tmp_path, monkeypatch):
    from faceless.wilddoc import sound

    monkeypatch.setattr(sound, "KIT_DIR", tmp_path / "kit")
    r = sound.make_kit("procedural")
    assert len(list((tmp_path / "kit").glob("*.wav"))) == len(sound.KIT) == len(r["made"])
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(tmp_path / "kit" / "riser.wav")],
                       capture_output=True, text=True).stdout
    assert abs(float(d) - sound.KIT["riser"][1]) < 0.05
