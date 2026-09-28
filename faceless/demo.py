"""`faceless demo`: a complete, free, offline run through every stage.

It proves an install works end to end without any API key or image tool:
narration from the OS voice (macOS `say`, Linux `espeak-ng`/`espeak`, else a tone),
word timings spread across each spoken sentence, placeholder keyframes drawn
with Pillow, then the real beats/gates/compose/package code paths.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .config import repo_root
from .engine import ProductionEngine
from .io import atomic_write_json, load_json, sha256_file
from .media import concat_audio, duration, normalize_voice, require, run

SENTENCES = [
    "In nineteen twelve, the Titanic sank on her first voyage.",
    "But she was not alone.",
    "Her twin sister, the Olympic, sailed for twenty four more years.",
    "Why did one ship die, and the other survive?",
    "After the disaster, the Olympic was rebuilt with a second hull.",
    "That hidden wall of steel is why she earned the name Old Reliable.",
    "Would you have sailed on her? Tell me in the comments.",
]
PALETTE = [(29, 43, 100), (120, 40, 60), (20, 90, 90), (90, 60, 20), (50, 30, 90), (10, 70, 40), (100, 20, 20)]


def _speak(text: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("say"):
        aiff = dest.with_suffix(".aiff")
        subprocess.run(["say", "-o", str(aiff), text], check=True)
        run([require("ffmpeg"), "-y", "-i", str(aiff), str(dest)])
        aiff.unlink(missing_ok=True)
    elif shutil.which("espeak-ng") or shutil.which("espeak"):
        subprocess.run([shutil.which("espeak-ng") or shutil.which("espeak"), "-w", str(dest), text], check=True)
    else:  # no TTS on this machine: a tone as long as the sentence would take to say
        secs = max(1.2, len(text.split()) / 2.6)
        run([require("ffmpeg"), "-y", "-f", "lavfi", "-i", f"sine=frequency=220:duration={secs}", "-ac", "1", str(dest)])
    return dest


def _placeholder(path: Path, size: tuple[int, int], color: tuple[int, int, int], label: str) -> None:
    img = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(img)
    w, h = size
    for i in range(0, w + h, 40):
        draw.line([(i, 0), (0, i)], fill=tuple(min(255, c + 25) for c in color), width=3)
    draw.rectangle([w * 0.1, h * 0.4, w * 0.9, h * 0.6], fill=(0, 0, 0))
    try:
        from PIL import ImageFont

        font = ImageFont.load_default(size=int(min(w, h) * 0.06))
    except TypeError:
        font = None
    draw.text((w * 0.14, h * 0.46), label, fill=(255, 255, 255), font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def run_demo(fmt: str = "short", render: bool = True, engine_name: str = "remotion") -> dict[str, Any]:
    root = repo_root() / "projects"
    slug = f"demo-{fmt}"
    target = root / slug
    if target.exists():
        shutil.rmtree(target)
    engine = ProductionEngine.initialize(root, slug, "The Titanic Had a Twin", fmt, "upload", "manual", "en", 0.0)
    p = engine.project_root

    atomic_write_json(engine.artifact_path("brief"), {
        "version": "1.0", "topic": "Titanic's sister ship", "title": "The Titanic Had a Twin", "format": fmt, "language": "en",
        "promise": {"question": "Why did the twin survive?", "payoff": "She was rebuilt with a double hull"},
        "target_duration_s": 25 if fmt == "short" else 200, "voice_mode": "upload",
    })
    engine.complete("brief")

    # Voice: synthesize per sentence so we know where each sentence sits in time.
    tmp = p / "03-voice" / "_demo"
    parts = [_speak(s, tmp / f"s{i:02d}.wav") for i, s in enumerate(SENTENCES)]
    raw = concat_audio(parts, tmp / "raw.wav", gap_s=0.25)
    from .voice import ingest

    ingest(engine, raw)
    engine.complete("voice")

    # Transcript: spread each sentence's words across its measured span, by character length.
    words, cursor = [], 0.0
    for sentence, part in zip(SENTENCES, parts):
        span = duration(part)
        tokens = sentence.split()
        total_chars = sum(len(t) for t in tokens)
        t = cursor
        for token in tokens:
            d = span * len(token) / total_chars
            words.append({"text": token, "start": round(t, 3), "end": round(t + d * 0.92, 3)})
            t += d
        cursor += span + 0.25
    voice = load_json(engine.artifact_path("voice"))
    master = p / voice["master_path"]
    atomic_write_json(engine.artifact_path("transcript"), {
        "version": "1.0", "provider": "demo-synthetic", "model": "", "language": "en", "audio_path": voice["master_path"],
        "audio_sha256": sha256_file(master), "duration_s": voice["duration_s"], "text": " ".join(SENTENCES), "words": words,
    })
    engine.complete("transcript")

    from .transcript import script_from_transcript

    script_from_transcript(engine)
    script = load_json(engine.artifact_path("script"))
    script["promise"] = {"question": "Why did the twin survive?", "payoff": "She was rebuilt with a double hull"}
    for i, section in enumerate(script["sections"], 1):
        section["title"] = f"Part {i}"
    atomic_write_json(engine.artifact_path("script"), script)
    engine.complete("script")
    engine.approve("cp1_story", "demo")

    aspect = "9:16" if fmt == "short" else "16:9"
    atomic_write_json(engine.artifact_path("visual_bible"), {
        "version": "1.0", "aspect": aspect,
        "style_contract": "Placeholder colour plates for the offline demo; a real project describes its look here in detail.",
        "characters": [], "locations": [{"location_id": "ocean", "name": "North Atlantic", "prompt_contract": "Cold dark ocean at night under a starry sky, icebergs on the horizon"}],
    })
    engine.complete("visual_bible")

    from .cli import _build_beats

    _build_beats(engine, force=True)
    beats_doc = load_json(engine.artifact_path("beats"))
    cameras = ["push_in", "pan_left", "pull_out", "drift", "pan_right", "push_in", "pan_up"]
    scales = ["wide", "medium", "close", "extreme_wide", "insert", "medium", "close"]
    for i, beat in enumerate(beats_doc["beats"]):
        beat.update({"visual_objective": f"Illustrate: {beat['text']}", "shot_scale": scales[i % len(scales)], "camera": {"kind": cameras[i % len(cameras)], "intensity": 0.6}, "location_id": "ocean"})
    beats_doc["beats"][0]["overlay"] = {"text": "1912", "style": "label"}
    beats_doc["directed"] = True
    atomic_write_json(engine.artifact_path("beats"), beats_doc)
    engine.complete("beats")

    from . import imagejobs

    imagejobs.compile_jobs(engine)
    size = (1080, 1920) if fmt == "short" else (1920, 1080)
    for i, job in enumerate(imagejobs.load_jobs(engine)):
        src = p / "07-keyframes" / "_demo" / f"{job['keyframe_id']}.png"
        _placeholder(src, size, PALETTE[i % len(PALETTE)], job["keyframe_id"])
        imagejobs.record(engine, job["keyframe_id"], src, host="demo")
    imagejobs.build_manifest(engine)
    imagejobs.set_qa(engine, ["all"], "pass", "demo placeholders")
    engine.complete("keyframes")

    result: dict[str, Any] = {"project": str(p)}
    if render:
        from . import compose

        out = compose.render_ffmpeg(engine, "youtube") if engine_name == "ffmpeg" else compose.render_remotion(engine, "youtube")
        compose.report(engine, reviewed=True, notes="demo render")
        engine.complete("compose")
        engine.approve("cp2_final_preview", "demo")
        from . import package

        package.draft(engine)
        pkg = load_json(engine.artifact_path("package"))
        pkg["primary_keyword"] = "titanic sister ship"
        pkg["youtube"]["description"] = "The Titanic had a twin sister ship, the Olympic, and she survived for 24 more years. Here is the hidden reason why, told in under a minute."
        if "shorts" in pkg:
            pkg["shorts"]["description"] = "The Titanic's twin survived. Why? #shorts"
            pkg["instagram"]["caption"] = "The Titanic had a twin. Why did she survive? Comment your guess."
        atomic_write_json(engine.artifact_path("package"), pkg)
        engine.complete("package")
        result["render"] = str(out)
    result["next"] = engine.next_action()
    return result
