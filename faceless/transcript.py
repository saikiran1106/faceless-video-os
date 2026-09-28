"""Transcript stage + 'understand the narration' for uploaded audio."""
from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from .captions import align_script_words, normalize
from .config import load_profile
from .engine import ProductionEngine, StateError
from .io import atomic_write_json, load_json, sha256_file
from .providers import split_sentences
from .providers.transcribe import estimate_usd, select_transcriber, transcribe


def plan(engine: ProductionEngine, provider: str = "auto") -> dict[str, Any]:
    voice_path = engine.artifact_path("voice")
    if not voice_path.exists():
        raise StateError("No narration yet. Finish the voice stage first.")
    voice = load_json(voice_path)
    chosen = select_transcriber(provider)
    return {"provider": chosen, "audio": voice["master_path"], "duration_s": voice["duration_s"], "estimated_usd": round(estimate_usd(chosen, voice["duration_s"]), 4)}


def script_match(script_text: str, words: list[dict[str, Any]]) -> dict[str, Any]:
    a = [t for t in (normalize(x) for x in script_text.split()) if t]
    b = [t for t in (normalize(w["text"]) for w in words) if t]
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    missing, extra = [], []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("delete", "replace"):
            missing.extend(a[i1:i2])
        if tag in ("insert", "replace"):
            extra.extend(b[j1:j2])
    return {"ratio": round(matched / max(len(a), 1), 4), "missing": missing[:60], "extra": extra[:60]}


def run(engine: ProductionEngine, provider: str = "auto") -> dict[str, Any]:
    state = engine.state()
    info = plan(engine, provider)
    if info["estimated_usd"] > 0:
        engine.record_cost(info["estimated_usd"], info["provider"], f"asr:{engine.project_root.name}:{sha256_file(engine.project_root / info['audio'])[:16]}:{info['provider']}", "transcript")
    voice = load_json(engine.artifact_path("voice"))
    master = engine.project_root / voice["master_path"]
    result = transcribe(master, info["provider"], state.get("language", ""), work_dir=engine.project_root / "04-transcript")
    if not result["words"]:
        raise StateError("The transcriber returned no words. Is the audio silent or in an unexpected language?")
    doc = {
        "version": "1.0",
        **result,
        "audio_path": voice["master_path"],
        "audio_sha256": sha256_file(master),
        "duration_s": voice["duration_s"],
    }
    script_path = engine.artifact_path("script")
    if script_path.exists():
        script = load_json(script_path)
        if script.get("source") == "written":
            doc["script_match"] = script_match(script["narration"], result["words"])
    atomic_write_json(engine.artifact_path("transcript"), doc)
    return {k: v for k, v in doc.items() if k != "words"} | {"word_count": len(doc["words"])}


def script_from_transcript(engine: ProductionEngine, force: bool = False, script_file: Path | None = None) -> dict[str, Any]:
    """Draft 02-script/script.json from what was actually said.

    Sections are cut at the longest pauses so they follow the speaker's own
    structure. Hook/promise are left as TODO on purpose: the agent must read
    the narration and state them - the gate refuses the stage until it does.

    `script_file`: the creator's own written script for this recording. Its text
    (exact spelling of names, punctuation) becomes the narration and the captions;
    the recording still supplies every timing. Refused if it doesn't match the audio.
    """
    state = engine.state()
    path = engine.artifact_path("script")
    if path.exists() and not force:
        raise StateError(f"{path} already exists; pass --force to overwrite it")
    transcript = load_json(engine.artifact_path("transcript"))
    words = transcript["words"]
    profile = load_profile(state["format"])
    duration_s = transcript["duration_s"]
    wanted = 1 if state["format"] == "short" else max(3, min(12, round(duration_s / 75)))
    gaps = sorted(((words[i + 1]["start"] - words[i]["end"], i + 1) for i in range(len(words) - 1)), reverse=True)
    cut_points = sorted(index for _, index in gaps[: wanted - 1])
    bounds = [0, *cut_points, len(words)]
    sections = []
    for n, (lo, hi) in enumerate(zip(bounds, bounds[1:]), 1):
        text = " ".join(w["text"] for w in words[lo:hi])
        sections.append({"section_id": f"S{n:02d}", "title": "TODO section title", "text": text, "start_s": round(words[lo]["start"], 2)})
    narration = " ".join(w["text"] for w in words)
    match = None
    if script_file:
        text = " ".join(Path(script_file).expanduser().read_text(encoding="utf-8").split())
        match = script_match(text, words)
        if match["ratio"] < 0.7:
            raise StateError(
                f"Only {match['ratio']:.0%} of that script was heard in the recording. "
                "Is it the right script for this audio? (missing: " + " ".join(match["missing"][:12]) + ")"
            )
        narration = text
        timed = align_script_words(text, words)
        starts = [s["start_s"] for s in sections] + [float("inf")]
        for i, section in enumerate(sections):
            section["text"] = " ".join(w["text"] for w in timed if starts[i] - 0.01 <= w["start"] < starts[i + 1] - 0.01) or section["text"]
    first_sentence = (split_sentences(narration) or [narration])[0]
    script = {
        "version": "1.0",
        "language": transcript.get("language") or state.get("language", "en"),
        "title": state["title"],
        "source": "transcript",
        "narration": narration,
        "hook": {"text": first_sentence, "seconds": round(min(profile["hook_max_s"], duration_s), 2)},
        "promise": {"question": "TODO: the question the opening makes the viewer ask", "payoff": "TODO: the answer the ending delivers"},
        "sections": [{k: v for k, v in s.items() if k != "start_s"} for s in sections],
        "claims": [],
    }
    atomic_write_json(path, script)
    return {"path": str(path), **({"script_match": match} if match else {}), "sections": [{"section_id": s["section_id"], "start_s": s["start_s"], "words": len(s["text"].split())} for s in sections]}
