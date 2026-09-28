"""Thin wrappers over ffmpeg/ffprobe. Every other module goes through these."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


class MediaError(RuntimeError):
    pass


def require(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        raise MediaError(f"`{binary}` is not installed or not on PATH. See docs/01-getting-started.md.")
    return path


def run(cmd: list[str], timeout: int = 3600) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-12:]
        raise MediaError(f"Command failed ({proc.returncode}): {' '.join(cmd[:4])} ...\n" + "\n".join(tail))
    return proc


def probe(path: Path) -> dict[str, Any]:
    out = run([require("ffprobe"), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]).stdout
    data = json.loads(out)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    info: dict[str, Any] = {"duration_s": float(data.get("format", {}).get("duration") or 0), "has_audio": audio is not None, "has_video": video is not None}
    if video:
        info["width"], info["height"] = int(video.get("width", 0)), int(video.get("height", 0))
        num, _, den = (video.get("r_frame_rate") or "0/1").partition("/")
        info["fps"] = round(float(num) / float(den or 1), 3) if float(den or 1) else 0.0
    if audio:
        info["sample_rate"] = int(audio.get("sample_rate") or 0)
        info["channels"] = int(audio.get("channels") or 0)
    return info


def duration(path: Path) -> float:
    return probe(path)["duration_s"]


def normalize_voice(src: Path, dest: Path, target_lufs: float = -16.0) -> Path:
    """Mono 48 kHz WAV, loudness-normalised for spoken word. Never edits the source."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    run([require("ffmpeg"), "-y", "-i", str(src), "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11", "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(dest)])
    return dest


def compress_for_upload(src: Path, dest: Path, bitrate: str = "48k") -> Path:
    """Small mono MP3 for transcription APIs with upload caps (OpenAI: 25 MB)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    run([require("ffmpeg"), "-y", "-i", str(src), "-ac", "1", "-ar", "16000", "-b:a", bitrate, str(dest)])
    return dest


def concat_audio(parts: list[Path], dest: Path, gap_s: float = 0.0) -> Path:
    """Concatenate audio chunks, optionally with a short silence between them."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    inputs: list[str] = []
    filters: list[str] = []
    labels: list[str] = []
    for index, part in enumerate(parts):
        inputs += ["-i", str(part)]
        filters.append(f"[{index}:a]aresample=48000,aformat=channel_layouts=mono[a{index}]")
        labels.append(f"[a{index}]")
        if gap_s > 0 and index < len(parts) - 1:
            filters.append(f"anullsrc=r=48000:cl=mono,atrim=0:{gap_s}[g{index}]")
            labels.append(f"[g{index}]")
    graph = ";".join(filters) + ";" + "".join(labels) + f"concat=n={len(labels)}:v=0:a=1[out]"
    run([require("ffmpeg"), "-y", *inputs, "-filter_complex", graph, "-map", "[out]", "-c:a", "pcm_s16le", str(dest)])
    return dest
