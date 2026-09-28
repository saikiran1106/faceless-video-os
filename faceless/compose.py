"""Compose stage: beats + keyframes + narration + captions -> Remotion props -> MP4.

Python computes every frame number; the React composition only draws. That keeps
timing logic testable and means one composition (`StoryVideo`) serves every
project, format and platform - no per-video code.
"""
from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .captions import build_pages, caption_words
from .config import load_channel, load_profile, repo_root
from .engine import ProductionEngine, StateError
from .io import atomic_write_json, load_json, sha256_file, utc_now
from .media import MediaError, probe, require, run

PLATFORMS = ("youtube", "instagram", "tiktok")
TRANSITION_FRAMES = {"crossfade": 10, "dip_to_black": 14, "flash": 6, "cut": 0}


def composer_dir() -> Path:
    path = repo_root() / "composer"
    if not (path / "package.json").exists():
        raise StateError(f"Remotion composer not found at {path}")
    return path


def public_dir(engine: ProductionEngine) -> Path:
    """Each project renders from its own public dir (passed as --public-dir), so the
    composer never accumulates assets and renders never bundle other projects."""
    return engine.project_root / "08-compose" / "public"


def _stage_asset(src: Path, public: Path, name: str) -> str:
    """Copy into the project's render public dir and return the staticFile() path."""
    dest = public / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or sha256_file(dest) != sha256_file(src):
        shutil.copy2(src, dest)
    return name.replace("\\", "/")


def build_props(engine: ProductionEngine, platform: str = "youtube") -> dict[str, Any]:
    if platform not in PLATFORMS:
        raise StateError(f"Unknown platform {platform!r}; expected one of {PLATFORMS}")
    state = engine.state()
    project = engine.project_root
    profile = load_profile(state["format"])
    channel = load_channel()
    fps = profile["fps"]
    voice = load_json(engine.artifact_path("voice"))
    transcript = load_json(engine.artifact_path("transcript"))
    script = load_json(engine.artifact_path("script")) if engine.artifact_path("script").exists() else None
    beats = load_json(engine.artifact_path("beats"))["beats"]
    keyframes = {k["keyframe_id"]: k for k in load_json(engine.artifact_path("keyframes"))["keyframes"]}
    public = public_dir(engine)

    def f(seconds: float) -> int:
        return int(round(seconds * fps))

    narration_frames = math.ceil(voice["duration_s"] * fps)
    cta = channel["cta"]
    end_card_frames = f(cta.get("end_card_seconds", 3.0)) if profile.get("end_card") else 0
    total = narration_frames + end_card_frames

    shots = []
    for index, beat in enumerate(beats):
        kf = keyframes.get(beat["keyframe_id"])
        if not kf:
            raise StateError(f"No keyframe for {beat['beat_id']}; finish the keyframes stage")
        start = f(beat["start_s"])
        end = total if index == len(beats) - 1 else f(beat["end_s"])
        transition = beat.get("transition", "crossfade") if index else "cut"
        shots.append({
            "id": beat["keyframe_id"],
            "src": _stage_asset(project / kf["path"], public, f"images/{Path(kf['path']).name}"),
            "from": start,
            "durationInFrames": max(1, end - start),
            "camera": beat.get("camera") or {"kind": "push_in", "intensity": 0.5},
            "transition": transition,
            "transitionFrames": TRANSITION_FRAMES.get(transition, 10),
        })

    cap_cfg = profile["captions"]
    pages = build_pages(caption_words(transcript, script), cap_cfg["max_words_per_page"], cap_cfg["max_chars_per_page"])
    if channel["style"].get("caption_case") == "upper":
        for page in pages:
            for w in page["words"]:
                w["text"] = w["text"].upper()
    captions = {
        "enabled": bool(cap_cfg["enabled"]),
        "yPercent": cap_cfg["y_percent"],
        "fontSize": cap_cfg["font_size"],
        "pages": [{"from": f(p["start"]), "to": f(p["end"]), "words": [{"text": w["text"], "from": f(w["start"]), "to": f(w["end"])} for w in p["words"]]} for p in pages],
    }

    overlays = []
    for beat in beats:
        ov = beat.get("overlay")
        if ov:
            start_s = ov.get("start_s", beat["start_s"])
            end_s = ov.get("end_s", beat["end_s"])
            overlays.append({"text": ov["text"], "style": ov["style"], "from": f(start_s), "to": f(end_s)})

    ctas = []
    narr = voice["duration_s"]
    if state["format"] == "longform" and cta.get("subscribe_text"):
        ctas.append({"kind": "subscribe", "text": cta["subscribe_text"], "from": f(narr * 0.35), "to": f(narr * 0.35 + 4)})
    comment_text = (script or {}).get("cta", {}).get("end") or cta.get("comment_text")
    if comment_text:
        at = narr * 0.75
        ctas.append({"kind": "comment", "text": comment_text, "from": f(at), "to": f(at + 3)})

    end_line = cta.get("follow_text", "Follow for more") if platform in ("instagram", "tiktok") else cta.get("subscribe_text", "Subscribe")
    style = channel["style"]
    font_src = ""
    if style.get("font_file"):
        font_path = (repo_root() / style["font_file"]).resolve()
        if not font_path.exists():
            raise StateError(f"channel.json style.font_file not found: {font_path}")
        font_src = _stage_asset(font_path, public, f"fonts/{font_path.name}")

    music = None
    track = channel["music"].get("default_track")
    music_path = project / "08-compose" / "music.mp3"
    if not music_path.exists() and track:
        music_path = (repo_root() / track).resolve()
    if music_path.exists():
        music = {"src": _stage_asset(music_path, public, f"audio/{music_path.name}"), "volume": float(channel["music"].get("volume", 0.12))}

    return {
        "fps": fps,
        "width": profile["width"],
        "height": profile["height"],
        "durationInFrames": total,
        "narrationFrames": narration_frames,
        "platform": platform,
        "narration": {"src": _stage_asset(project / voice["master_path"], public, "audio/narration.wav")},
        "music": music,
        "shots": shots,
        "captions": captions,
        "overlays": overlays,
        "ctas": ctas,
        "endCard": {"from": narration_frames, "durationInFrames": end_card_frames, "channelName": channel["channel_name"], "line": end_line} if end_card_frames else None,
        "theme": {
            "fontFamily": style.get("caption_font") or "Noto Sans",
            "fontSrc": font_src,
            "captionColor": style.get("caption_color", "#FFFFFF"),
            "highlightColor": style.get("highlight_color", "#FFD400"),
            "accentColor": style.get("accent_color", "#E53935"),
        },
    }


def write_props(engine: ProductionEngine, platform: str) -> Path:
    props = build_props(engine, platform)
    path = engine.project_root / "08-compose" / f"props_{platform}.json"
    atomic_write_json(path, props)
    return path


def render_remotion(engine: ProductionEngine, platform: str, keep_props: bool = False, extra_args: list[str] | None = None) -> Path:
    comp = composer_dir()
    if not (comp / "node_modules").exists():
        raise StateError(f"Composer dependencies are missing. Run: cd {comp} && npm install")
    props_path = engine.project_root / "08-compose" / f"props_{platform}.json"
    if not (keep_props and props_path.exists()):
        props_path = write_props(engine, platform)
    out = engine.project_root / "08-compose" / "renders" / f"{engine.project_root.name}_{platform}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [require("npx"), "remotion", "render", "src/index.ts", "StoryVideo", str(out), f"--props={props_path.resolve()}", f"--public-dir={public_dir(engine).resolve()}", "--codec=h264", "--crf=18", *(extra_args or [])]
    proc = subprocess.run(cmd, cwd=comp, text=True, capture_output=True)
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or proc.stdout).strip().splitlines()[-25:])
        raise MediaError(f"Remotion render failed:\n{tail}")
    atomic_write_json(out.with_suffix(".meta.json"), {"engine": "remotion", "props": str(props_path), "rendered_at": utc_now()})
    return out


def render_ffmpeg(engine: ProductionEngine, platform: str) -> Path:
    """Fallback when Node/Remotion is unavailable: slow push-in per image, hard cuts, no captions."""
    props = build_props(engine, platform)
    fps, width, height = props["fps"], props["width"], props["height"]
    work = engine.project_root / "08-compose" / "_ffmpeg"
    work.mkdir(parents=True, exist_ok=True)
    public = public_dir(engine)
    clips = []
    for shot in props["shots"]:
        frames = shot["durationInFrames"]
        clip = work / f"{shot['id']}.mp4"
        zoom = "min(zoom+0.0006,1.10)" if shot["camera"]["kind"] != "pull_out" else "if(eq(on,0),1.10,max(zoom-0.0006,1.0))"
        vf = f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,crop={width * 2}:{height * 2},zoompan=z='{zoom}':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps},format=yuv420p"
        run([require("ffmpeg"), "-y", "-loop", "1", "-i", str(public / shot["src"]), "-vf", vf, "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(clip)])
        clips.append(clip)
    concat = work / "concat.txt"
    concat.write_text("".join(f"file '{c.resolve()}'\n" for c in clips), encoding="utf-8")
    out = engine.project_root / "08-compose" / "renders" / f"{engine.project_root.name}_{platform}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    narration = public / props["narration"]["src"]
    total_s = props["durationInFrames"] / fps
    run([require("ffmpeg"), "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(narration), "-map", "0:v", "-map", "1:a", "-af", "apad", "-t", f"{total_s:.3f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out)])
    atomic_write_json(out.with_suffix(".meta.json"), {"engine": "ffmpeg", "rendered_at": utc_now()})
    return out


def report(engine: ProductionEngine, reviewed: bool = False, notes: str = "") -> dict[str, Any]:
    renders_dir = engine.project_root / "08-compose" / "renders"
    files = sorted(renders_dir.glob("*.mp4")) if renders_dir.exists() else []
    if not files:
        raise StateError("No renders found in 08-compose/renders/")
    voice = load_json(engine.artifact_path("voice"))
    path = engine.artifact_path("compose")
    prior = load_json(path) if path.exists() else {}
    renders = []
    for file in files:
        info = probe(file)
        meta_path = file.with_suffix(".meta.json")
        meta = load_json(meta_path) if meta_path.exists() else {}
        renders.append({
            "platform": file.stem.rsplit("_", 1)[-1],
            "engine": meta.get("engine", "remotion"),
            "path": str(file.relative_to(engine.project_root)),
            "sha256": sha256_file(file),
            "width": info.get("width", 0),
            "height": info.get("height", 0),
            "duration_s": round(info["duration_s"], 3),
            "fps": info.get("fps", 0),
            "has_audio": info["has_audio"],
        })
    unchanged = {r["sha256"] for r in prior.get("renders", [])} == {r["sha256"] for r in renders}
    doc = {
        "version": "1.0",
        "audio_duration_s": voice["duration_s"],
        "renders": renders,
        "preview_reviewed": bool(reviewed or (unchanged and prior.get("preview_reviewed"))),
        "review_notes": notes or (prior.get("review_notes", "") if unchanged else ""),
        "reported_at": utc_now(),
    }
    atomic_write_json(path, doc)
    return doc
