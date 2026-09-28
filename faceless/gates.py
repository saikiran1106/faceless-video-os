"""Deterministic quality gates, one per stage.

A gate never judges taste; it catches the mechanical defects that ruin a video
(unsynced beats, a transcript of the wrong audio, a keyframe reused on two beats,
a title YouTube will truncate). Critical findings block the stage. Warnings are
reported for the reviewer but do not block.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from .config import load_profile
from .io import load_json, sha256_file

TODO = re.compile(r"\bTODO\b")


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str  # "critical" | "warning"
    message: str
    location: str = ""
    fix: str = ""


@dataclass(frozen=True)
class GateResult:
    passed: bool
    findings: tuple[Finding, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "findings": [asdict(f) for f in self.findings]}


def _result(findings: Iterable[Finding]) -> GateResult:
    items = tuple(findings)
    return GateResult(not any(f.severity == "critical" for f in items), items)


def _crit(rule: str, msg: str, loc: str = "", fix: str = "") -> Finding:
    return Finding(rule, "critical", msg, loc, fix)


def _warn(rule: str, msg: str, loc: str = "", fix: str = "") -> Finding:
    return Finding(rule, "warning", msg, loc, fix)


def _todos(payload: Any, path: str = "") -> list[str]:
    if isinstance(payload, str):
        return [path] if TODO.search(payload) else []
    if isinstance(payload, dict):
        return [hit for key, value in payload.items() for hit in _todos(value, f"{path}.{key}" if path else key)]
    if isinstance(payload, list):
        return [hit for i, value in enumerate(payload) for hit in _todos(value, f"{path}[{i}]")]
    return []


def _load(project: Path, stage_path: str) -> dict[str, Any] | None:
    path = project / stage_path
    return load_json(path) if path.exists() else None


# --------------------------------------------------------------------- stages
def check_brief(brief: dict, project: Path, state: dict) -> GateResult:
    findings = []
    profile = load_profile(state["format"])
    if brief["voice_mode"] != state["voice_mode"]:
        findings.append(_crit("FF-BRIEF-001", f"Brief says voice_mode={brief['voice_mode']} but the project is {state['voice_mode']}", "voice_mode"))
    if brief["format"] != state["format"]:
        findings.append(_crit("FF-BRIEF-002", f"Brief says format={brief['format']} but the project is {state['format']}", "format"))
    lo, hi = profile["duration_s"]["min"], profile["duration_s"]["max"]
    if not lo <= brief["target_duration_s"] <= hi:
        findings.append(_warn("FF-BRIEF-003", f"Target {brief['target_duration_s']}s is outside the {state['format']} range {lo}-{hi}s", "target_duration_s"))
    if not (brief.get("promise") or {}).get("question"):
        findings.append(_warn("FF-BRIEF-004", "No promise question: what does the viewer want answered?", "promise.question", "One question the opening asks and the ending answers."))
    for hit in _todos(brief):
        findings.append(_crit("FF-TODO", "Placeholder TODO left in the brief", hit))
    return _result(findings)


def check_script(script: dict, project: Path, state: dict) -> GateResult:
    findings = []
    profile = load_profile(state["format"])
    brief = _load(project, "01-brief/brief.json") or {}
    for hit in _todos(script):
        findings.append(_crit("FF-TODO", "Placeholder TODO left in the script", hit, "Fill it in from the narration."))
    words = len(script["narration"].split())
    wpm_table = profile["words_per_minute"]
    wpm = wpm_table.get(script["language"], wpm_table["default"])
    if script["source"] == "written":
        target = brief.get("target_duration_s") or profile["duration_s"]["target"]
        expected = target / 60 * wpm
        if not 0.75 * expected <= words <= 1.25 * expected:
            findings.append(_crit("FF-SCRIPT-001", f"{words} words is off-target: {target:.0f}s at ~{wpm} wpm is ~{expected:.0f} words (±25%)", "narration", "Tighten or expand without changing the promise."))
        if re.search(r"\s[-–—]\s", script["narration"]):
            findings.append(_warn("FF-SCRIPT-002", "Spaced dashes often make TTS pause oddly or read them aloud", "narration", "Use a comma or full stop."))
    hook_words = len(script["hook"]["text"].split())
    hook_seconds = hook_words / wpm * 60
    if hook_seconds > profile["hook_max_s"] * 1.5:
        findings.append(_warn("FF-SCRIPT-003", f"Hook runs ~{hook_seconds:.1f}s; aim for <= {profile['hook_max_s']}s", "hook.text", "Open on the most surprising line."))
    section_words = sum(len(s["text"].split()) for s in script["sections"])
    if abs(section_words - words) > max(5, 0.05 * words):
        findings.append(_warn("FF-SCRIPT-004", f"Sections hold {section_words} words but the narration has {words}", "sections", "Sections should partition the narration exactly (used for chapters)."))
    ids = [s["section_id"] for s in script["sections"]]
    if len(ids) != len(set(ids)):
        findings.append(_crit("FF-SCRIPT-005", "Duplicate section_id", "sections"))
    if state["format"] == "longform" and len(script["sections"]) < 3:
        findings.append(_warn("FF-SCRIPT-006", "Long-form with fewer than 3 sections gets no useful chapters", "sections"))
    if any(not c.get("source_refs") for c in script.get("claims", [])):
        findings.append(_warn("FF-SCRIPT-007", "Some factual claims have no source_refs", "claims", "Cite a source or soften the claim."))
    return _result(findings)


def check_voice(manifest: dict, project: Path, state: dict) -> GateResult:
    findings = []
    profile = load_profile(state["format"])
    if manifest["mode"] != state["voice_mode"]:
        findings.append(_crit("FF-VOICE-001", f"Manifest mode {manifest['mode']} != project voice_mode {state['voice_mode']}", "mode"))
    master = project / manifest["master_path"]
    if not master.exists():
        findings.append(_crit("FF-VOICE-002", f"Narration master is missing: {manifest['master_path']}", "master_path"))
        return _result(findings)
    if manifest.get("master_sha256") and sha256_file(master) != manifest["master_sha256"]:
        findings.append(_crit("FF-VOICE-003", "Narration master changed after the manifest was written", "master_sha256", "Re-run voice generate/ingest."))
    duration = manifest["duration_s"]
    if state["format"] == "short" and duration > 180:
        findings.append(_crit("FF-VOICE-004", f"{duration:.0f}s is longer than a Short can be (180s)", "duration_s"))
    elif duration > profile["duration_s"]["max"] * 1.1 or duration < profile["duration_s"]["min"] * 0.8:
        findings.append(_warn("FF-VOICE-005", f"{duration:.0f}s is outside the {state['format']} profile range", "duration_s"))
    for i, chunk in enumerate(manifest.get("chunks", [])):
        chars, secs = chunk.get("chars") or len(chunk.get("text", "")), chunk.get("duration_s", 0)
        if secs and chars / secs > 25:
            findings.append(_crit("FF-VOICE-006", f"Chunk {chunk['chunk_id']} speaks {chars/secs:.0f} chars/s; the provider probably truncated it", f"chunks[{i}]", "Regenerate this chunk only."))
        if not (project / chunk["path"]).exists():
            findings.append(_warn("FF-VOICE-007", f"Chunk file missing: {chunk['path']}", f"chunks[{i}]"))
    return _result(findings)


def check_transcript(transcript: dict, project: Path, state: dict) -> GateResult:
    findings = []
    voice = _load(project, "03-voice/voice_manifest.json")
    if not voice:
        findings.append(_crit("FF-ASR-001", "No voice manifest; transcribe after the voice stage", "audio_path"))
        return _result(findings)
    master = project / voice["master_path"]
    if master.exists() and sha256_file(master) != transcript["audio_sha256"]:
        findings.append(_crit("FF-ASR-002", "This transcript is of a different audio file than the current narration master", "audio_sha256", "Re-run `faceless transcribe`."))
    words = transcript["words"]
    prev = -1.0
    for i, w in enumerate(words):
        if w["end"] < w["start"] or w["start"] < prev - 0.05:
            findings.append(_crit("FF-ASR-003", f"Word timings go backwards at word {i} ({w['text']})", f"words[{i}]"))
            break
        prev = w["start"]
    if words and words[-1]["end"] > transcript["duration_s"] + 0.5:
        findings.append(_crit("FF-ASR-004", "Last word ends after the audio does", "words"))
    match = transcript.get("script_match")
    if state["voice_mode"] == "tts" and match is None:
        findings.append(_crit("FF-ASR-005", "AI-voice mode needs a script-vs-audio comparison", "script_match", "Re-run `faceless transcribe` after the script exists."))
    if match:
        if match["ratio"] < 0.85:
            findings.append(_crit("FF-ASR-006", f"Only {match['ratio']:.0%} of the script was heard in the audio; the voice dropped or garbled lines", "script_match", "Listen, then regenerate only the failing chunk."))
        elif match["ratio"] < 0.93:
            findings.append(_warn("FF-ASR-007", f"{match['ratio']:.0%} script match; check the missing words by ear", "script_match.missing"))
    return _result(findings)


def check_visual_bible(bible: dict, project: Path, state: dict) -> GateResult:
    findings = []
    profile = load_profile(state["format"])
    if bible["aspect"] != profile["aspect"]:
        findings.append(_crit("FF-VIS-001", f"Visual bible aspect {bible['aspect']} but {state['format']} renders {profile['aspect']}", "aspect"))
    for group, key in (("characters", "character_id"), ("locations", "location_id")):
        ids = [item[key] for item in bible[group]]
        for dup, count in Counter(ids).items():
            if count > 1:
                findings.append(_crit("FF-VIS-002", f"Duplicate {key} {dup}", group))
        for i, item in enumerate(bible[group]):
            for ref in item.get("reference_paths", []):
                if not (project / ref).exists() and not Path(ref).exists():
                    findings.append(_crit("FF-VIS-003", f"Reference image not found: {ref}", f"{group}[{i}]"))
            if len(item["prompt_contract"]) < 40:
                findings.append(_warn("FF-VIS-004", f"{item[key]} prompt_contract is thin; identity will drift between frames", f"{group}[{i}]", "Describe face, build, age, hair, wardrobe, colours, props."))
    if len(bible["style_contract"]) < 40:
        findings.append(_warn("FF-VIS-005", "style_contract is thin; frames will not look like one video", "style_contract"))
    for hit in _todos(bible):
        findings.append(_crit("FF-TODO", "Placeholder TODO left in the visual bible", hit))
    return _result(findings)


def check_beats(manifest: dict, project: Path, state: dict) -> GateResult:
    findings = []
    profile = load_profile(state["format"])
    pacing = profile["beats"]
    beats = sorted(manifest["beats"], key=lambda b: b["start_s"])
    for field in ("beat_id", "keyframe_id"):
        for dup, count in Counter(b[field] for b in beats).items():
            if count > 1:
                findings.append(_crit("FF-SYNC-001", f"Duplicate {field} {dup}: one keyframe per beat, never shared", "beats"))
    bible = _load(project, "05-visual-bible/visual_bible.json") or {"characters": [], "locations": []}
    characters = {c["character_id"] for c in bible["characters"]}
    locations = {loc["location_id"] for loc in bible["locations"]}
    previous_end = 0.0
    for i, b in enumerate(beats):
        loc = f"beats[{i}] {b['beat_id']}"
        if b["end_s"] <= b["start_s"]:
            findings.append(_crit("FF-SYNC-002", "Beat ends before it starts", loc))
        if i and b["start_s"] - previous_end > 0.08:
            findings.append(_crit("FF-SYNC-003", f"{b['start_s'] - previous_end:.2f}s gap before this beat", loc, "Beats must cover the audio continuously."))
        if b["start_s"] < previous_end - 0.08:
            findings.append(_crit("FF-SYNC-004", f"Overlaps the previous beat by {previous_end - b['start_s']:.2f}s", loc))
        span = b["end_s"] - b["start_s"]
        if span > pacing["max_hold_s"] and not b.get("long_hold_reason"):
            findings.append(_crit("FF-SYNC-005", f"{span:.1f}s hold on one image (max {pacing['max_hold_s']}s)", loc, "Split the beat or give a long_hold_reason."))
        if not b.get("visual_objective", "").strip():
            findings.append(_crit("FF-DIR-001", "Beat has no visual_objective (what must the viewer SEE?)", loc, "Direct every beat before generating keyframes."))
        for cid in b.get("character_ids", []):
            if cid not in characters:
                findings.append(_crit("FF-DIR-002", f"Unknown character_id {cid}", loc, "Add it to the visual bible or fix the id."))
        if b.get("location_id") and b["location_id"] not in locations:
            findings.append(_crit("FF-DIR-003", f"Unknown location_id {b['location_id']}", loc))
        previous_end = max(previous_end, b["end_s"])
    if beats and beats[0]["start_s"] > 0.08:
        findings.append(_crit("FF-SYNC-006", "First beat does not start at 0s", "beats[0]"))
    if beats and abs(previous_end - manifest["audio_duration_s"]) > 0.15:
        findings.append(_crit("FF-SYNC-007", f"Beats end at {previous_end:.2f}s but audio ends at {manifest['audio_duration_s']:.2f}s", "audio_duration_s"))
    scales = [b.get("shot_scale") for b in beats if b.get("shot_scale")]
    if scales:
        top, count = Counter(scales).most_common(1)[0]
        if len(scales) >= 6 and count / len(scales) > 0.6:
            findings.append(_warn("FF-DIR-004", f"{count/len(scales):.0%} of beats are '{top}' shots; it will read as static", "shot_scale", "Vary the framing ladder: wide / medium / close / insert."))
    run = 1
    for prev, cur in zip(beats, beats[1:]):
        run = run + 1 if (prev.get("camera") or {}).get("kind") == (cur.get("camera") or {}).get("kind") else 1
        if run == 4:
            findings.append(_warn("FF-DIR-005", f"Same camera move 4+ times in a row near {cur['beat_id']}", cur["beat_id"], "Alternate push/pull/pan/drift."))
    return _result(findings)


def check_keyframes(manifest: dict, project: Path, state: dict) -> GateResult:
    findings = []
    beats_doc = _load(project, "06-beats/beat_manifest.json")
    profile = load_profile(state["format"])
    want_ratio = profile["width"] / profile["height"]
    by_kf = {k["keyframe_id"]: k for k in manifest["keyframes"]}
    if beats_doc:
        for b in beats_doc["beats"]:
            kf = by_kf.get(b["keyframe_id"])
            if not kf:
                findings.append(_crit("FF-KF-001", f"No keyframe for beat {b['beat_id']} ({b['keyframe_id']})", b["beat_id"]))
            elif kf["beat_id"] != b["beat_id"]:
                findings.append(_crit("FF-KF-002", f"{kf['keyframe_id']} was declared for {b['beat_id']} but is bound to {kf['beat_id']}", b["beat_id"], "Never recast a keyframe onto another beat; regenerate."))
    for dup, count in Counter(k["sha256"] for k in manifest["keyframes"]).items():
        if count > 1:
            findings.append(_crit("FF-KF-003", f"The same image file is used for {count} keyframes", dup[:12], "Each beat needs its own frame."))
    for i, k in enumerate(manifest["keyframes"]):
        loc = k["keyframe_id"]
        path = project / k["path"]
        if not path.exists():
            findings.append(_crit("FF-KF-004", f"Image missing: {k['path']}", loc))
            continue
        if sha256_file(path) != k["sha256"]:
            findings.append(_crit("FF-KF-005", "Image changed after it was recorded", loc, "Run `faceless images manifest` again and re-review it."))
        if k.get("width") and k.get("height"):
            ratio = k["width"] / k["height"]
            if abs(ratio - want_ratio) / want_ratio > 0.03:
                findings.append(_crit("FF-KF-006", f"Aspect {k['width']}x{k['height']} does not match {profile['aspect']}", loc, "Regenerate at the right aspect; cropping loses the subject."))
        if k["qa_status"] != "pass":
            findings.append(_crit("FF-KF-007", f"Not visually reviewed/passed (qa_status={k['qa_status']})", loc, "Look at the pixels against the beat text, then `faceless images qa`."))
    return _result(findings)


def check_compose(report: dict, project: Path, state: dict) -> GateResult:
    findings = []
    profile = load_profile(state["format"])
    voice = _load(project, "03-voice/voice_manifest.json") or {}
    audio = voice.get("duration_s", 0)
    for i, r in enumerate(report["renders"]):
        loc = f"renders[{i}] {r['platform']}"
        if not (project / r["path"]).exists():
            findings.append(_crit("FF-RENDER-001", f"Render missing: {r['path']}", loc))
            continue
        if not r["has_audio"]:
            findings.append(_crit("FF-RENDER-002", "Render has no audio track", loc))
        if (r["width"], r["height"]) != (profile["width"], profile["height"]):
            findings.append(_crit("FF-RENDER-003", f"{r['width']}x{r['height']} but {state['format']} is {profile['width']}x{profile['height']}", loc))
        if audio and r["duration_s"] < audio - 0.25:
            findings.append(_crit("FF-RENDER-004", f"Render ({r['duration_s']:.2f}s) is shorter than the narration ({audio:.2f}s)", loc))
        if audio and r["duration_s"] > audio + 12:
            findings.append(_warn("FF-RENDER-005", f"Render runs {r['duration_s'] - audio:.1f}s past the narration", loc))
    if not report["preview_reviewed"]:
        findings.append(_crit("FF-RENDER-006", "Nobody has watched the render yet", "preview_reviewed", "Watch it end to end (or review sampled frames + contact sheet), then `faceless compose report --reviewed`."))
    return _result(findings)


def check_package(pkg: dict, project: Path, state: dict) -> GateResult:
    findings = []
    yt = pkg["youtube"]
    for hit in _todos(pkg):
        findings.append(_crit("FF-TODO", "Placeholder TODO left in the package", hit))
    if len(yt["title"]) > 100:
        findings.append(_crit("FF-PKG-001", f"Title is {len(yt['title'])} chars; YouTube's limit is 100", "youtube.title"))
    elif len(yt["title"]) > 70:
        findings.append(_warn("FF-PKG-002", f"Title is {len(yt['title'])} chars; it will be truncated in search/feed (~70)", "youtube.title"))
    if len(yt["description"]) < 150:
        findings.append(_warn("FF-PKG-003", "Description under 150 chars; the first 2 lines are prime search real estate", "youtube.description"))
    if len(",".join(yt["tags"])) > 500:
        findings.append(_crit("FF-PKG-004", "Tags exceed YouTube's 500-character limit", "youtube.tags"))
    if len(yt["hashtags"]) > 15:
        findings.append(_crit("FF-PKG-005", "More than 15 hashtags: YouTube ignores ALL of them", "youtube.hashtags"))
    elif len(yt["hashtags"]) > 5:
        findings.append(_warn("FF-PKG-006", "Use 3-5 focused hashtags", "youtube.hashtags"))
    chapters = yt.get("chapters") or []
    if chapters:
        secs = [_parse_ts(c["time"]) for c in chapters]
        if secs[0] != 0:
            findings.append(_crit("FF-PKG-007", "The first chapter must start at 0:00", "youtube.chapters[0]"))
        if len(chapters) < 3:
            findings.append(_crit("FF-PKG-008", "YouTube needs at least 3 chapters (or none)", "youtube.chapters"))
        for a, b in zip(secs, secs[1:]):
            if b - a < 10:
                findings.append(_crit("FF-PKG-009", "Chapters must be at least 10s apart", "youtube.chapters"))
                break
    elif state["format"] == "longform":
        findings.append(_warn("FF-PKG-010", "Long-form without chapters", "youtube.chapters"))
    thumb = yt.get("thumbnail_path")
    if thumb and not (project / thumb).exists():
        findings.append(_crit("FF-PKG-011", f"Thumbnail missing: {thumb}", "youtube.thumbnail_path"))
    elif thumb and (project / thumb).stat().st_size > 2 * 1024 * 1024:
        findings.append(_crit("FF-PKG-012", "Thumbnail is over YouTube's 2 MB limit", "youtube.thumbnail_path"))
    elif not thumb and state["format"] == "longform":
        findings.append(_warn("FF-PKG-013", "No custom thumbnail; long-form lives or dies on it", "youtube.thumbnail_path"))
    return _result(findings)


def _parse_ts(value: str) -> int:
    parts = [int(p) for p in value.strip().split(":")]
    total = 0
    for part in parts:
        total = total * 60 + part
    return total


GATES: dict[str, Callable[[dict, Path, dict], GateResult]] = {
    "brief": check_brief,
    "script": check_script,
    "voice": check_voice,
    "transcript": check_transcript,
    "visual_bible": check_visual_bible,
    "beats": check_beats,
    "keyframes": check_keyframes,
    "compose": check_compose,
    "package": check_package,
}


def run_gate(stage: str, payload: dict, project: Path, state: dict) -> GateResult:
    return GATES[stage](payload, Path(project), state)
