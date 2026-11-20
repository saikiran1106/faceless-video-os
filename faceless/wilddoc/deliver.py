"""Voice ingest + transcription (start of the pipeline) and QA + publishing package (end of it)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from . import WildDocError
from .align import median_drift
from .project import Project, decode_errors, ffprobe_duration, frame_count, read_json, write_json


# ---------------------------------------------------------------- voice
def ingest_voice(project: Project, new_audio: Path | None = None) -> dict:
    """Client's voice AS-IS -> 48 kHz mono master. No trimming, levelling, stretching or pitch (iteration v4/v7 lessons).
    With new_audio: replace the voice (a re-edit). Then re-run transcribe -> align -> plan; anchors are script words, so
    the shot list keeps working."""
    if new_audio:
        new_audio = Path(new_audio).expanduser()
        if not new_audio.exists():
            raise WildDocError(f"File not found: {new_audio}")
        dst = project.p("source", f"voice{new_audio.suffix.lower()}")
        old = project.voice_source
        if old.exists() and old != dst:
            old.rename(old.with_name(old.stem + "_prev" + old.suffix))
        shutil.copy(new_audio, dst)
        project.meta["audio"] = str(dst.relative_to(project.root))
        write_json(project.root / "project.json", project.meta)
        for stale in ("transcript.json", "timeline.json"):
            project.p("audio", stale).unlink(missing_ok=True)
    project.voice_master.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(project.voice_source), "-ac", "1", "-ar", "48000", "-c:a", "pcm_s24le",
                    str(project.voice_master)], check=True)
    return {"voice_master": str(project.voice_master), "duration_s": round(ffprobe_duration(project.voice_master), 2),
            "note": "voice used as delivered: no stretch, pitch, trim or levelling"}


def transcribe(project: Project, provider: str = "auto", language: str = "") -> dict:
    from ..providers.transcribe import select_transcriber, transcribe as tx

    if not project.voice_master.exists():
        ingest_voice(project)
    prov = select_transcriber(provider)
    lang = language or project.style().get("language") or project.meta.get("language", "")
    res = tx(project.voice_master, prov, lang, project.p("audio"))
    write_json(project.p("audio", "transcript.json"), res)
    project.log("transcribe", provider=prov, words=len(res["words"]))
    return {"provider": prov, "words": len(res["words"]), "language": res.get("language"), "transcript": str(project.p("audio", "transcript.json"))}


# ---------------------------------------------------------------- QA
def qa(project: Project, provider: str | None = None) -> dict:
    master = project.master_path
    if not master.exists():
        raise WildDocError("No master yet. Run `faceless wild-doc assemble`.")
    plan = read_json(project.plan_path)
    rep: dict = {"master": str(master)}
    rep["decode_errors"] = decode_errors(master) + decode_errors(master, "a")
    rep["frames"], rep["frames_expected"] = frame_count(master), plan["durationInFrames"]
    rep["duration_s"], rep["voice_s"] = round(ffprobe_duration(master), 2), round(ffprobe_duration(project.voice_master), 2)
    o = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(master), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"Summary:.*?I:\s+(-?[\d.]+) LUFS.*?Peak:\s+(-?[\d.]+) dBFS", o, re.S)
    rep["lufs"], rep["true_peak_dbfs"] = (float(m.group(1)), float(m.group(2))) if m else (None, None)
    o = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(master), "-vf", "blackdetect=d=0.5:pix_th=0.06,freezedetect=n=0.003:d=2.5",
                        "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
    rep["black"] = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", o)[:20]
    rep["frozen"] = re.findall(r"freeze_start: ([\d.]+)", o)[:20]
    if provider:
        from ..providers.transcribe import transcribe as tx

        audio = project.p("compose", "qa_mix.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(master), "-vn", "-ac", "1", "-ar", "16000", str(audio)], check=True)
        heard = tx(audio, provider, project.style().get("language", ""), project.p("compose"))
        clean = read_json(project.p("audio", "transcript.json"))
        ratio, drift = median_drift(clean["words"], heard["words"])
        rep["final_mix_word_match"], rep["median_drift_s"] = ratio, drift
    problems = []
    if rep["decode_errors"]:
        problems.append("decode errors in the master: re-run assemble (and check the chunks)")
    if abs(rep["frames"] - rep["frames_expected"]) > 1:
        problems.append("frame count differs from the plan")
    if rep["lufs"] is not None and abs(rep["lufs"] - project.style()["mix"]["lufs"]) > 1.0:
        problems.append(f"loudness {rep['lufs']} LUFS")
    if rep["black"]:
        problems.append("black stretches > 0.5 s: check those shots (dark clip + night grade?)")
    if "final_mix_word_match" in rep and rep["final_mix_word_match"] < 0.9:
        problems.append("the narration is not clearly audible in the final mix (word match < 90%)")
    rep["problems"] = problems
    rep["passed"] = not problems
    write_json(project.p("package", "qa.json"), rep)
    return rep


# ---------------------------------------------------------------- package
def _ts(sec: float) -> str:
    sec = int(round(sec))
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


def package(project: Project) -> dict:
    plan = read_json(project.plan_path)
    fps = plan["fps"]
    chapters = plan["chapters"]
    lines = [f"# {project.meta.get('title', project.slug)}", "", "## Chapters"]
    chs = [c for c in chapters if c.get("title")] or chapters
    if chs and chs[0]["from"] != 0:
        chs = [{"title": "Intro", "from": 0}] + chs
    for c in chs:
        lines.append(f"{_ts(c['from'] / fps)} {c.get('title') or c['name'].replace('-', ' ').title()}")
    lines += ["", "## Credits"]
    picks = read_json(project.p("assets", "stock", "picks.json"), {})
    used_stock = {s.get("name") for s in plan["shots"] if s["kind"] == "stock"}
    for n in sorted(x for x in used_stock if x and picks.get(x, {}).get("source") == "pixabay"):
        lines.append(f"- Footage: Pixabay {picks[n]['page']}")
    credits = read_json(project.p("assets", "ref", "credits.json"), {})
    used_refs = {s.get("id") for s in plan["shots"] if s["kind"] == "ref"}
    for rid in sorted(x for x in used_refs if x in credits):
        c = credits[rid]
        if "page" in c:
            artist = re.sub(r"<[^>]+>", "", c.get("artist", "")).strip()
            lines.append(f"- Image: {c.get('title', rid)} - {artist} - {c.get('license', '')} - {c['page']}")
    out = project.p("package", "youtube.md")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"package": str(out), "chapters": len(chs), "note": "YouTube needs >= 3 chapters, the first at 0:00, each >= 10 s."}
