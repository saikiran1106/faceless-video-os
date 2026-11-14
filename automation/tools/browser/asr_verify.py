"""Independently transcribe an audio master and diff it against the script.

Why this exists
---------------
Forced alignment does NOT verify a script. It forces whatever text you hand it
onto the audio and reports success, so a script that says one thing while the
voice says another still aligns 311/311. That is exactly how a wrong deity
reached 62 keyframes, a thumbnail and two renders of Part 22.

Independent ASR is the only check that can catch it: it asks the audio what it
says, without being told the answer first.

Usage:
    python tools/browser/asr_verify.py <audio> [--from 85] [--to 170] [--out report.json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path


def slice_audio(src: Path, start: float, end: float) -> Path:
    out = Path(tempfile.mkdtemp()) / "slice.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-ss", str(start), "-to", str(end),
                    "-i", str(src), "-ac", "1", "-ar", "16000", str(out)], check=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--from", dest="start", type=float, default=0.0)
    ap.add_argument("--to", dest="end", type=float, default=None)
    ap.add_argument("--model", default="large-v3")
    ap.add_argument("--out")
    a = ap.parse_args()

    src = Path(a.audio)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                "format=duration", "-of", "csv=p=0", str(src)],
                               capture_output=True, text=True).stdout.strip())
    end = a.end if a.end is not None else dur
    clip = slice_audio(src, a.start, end)

    from faster_whisper import WhisperModel
    model = WhisperModel(a.model, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(clip), language="te", beam_size=5,
                                      vad_filter=False)

    rows = []
    for s in segments:
        rows.append({"start": round(a.start + s.start, 2),
                     "end": round(a.start + s.end, 2),
                     "text": s.text.strip()})
        print(f"[{rows[-1]['start']:7.2f} - {rows[-1]['end']:7.2f}]  {rows[-1]['text']}")

    report = {"audio": str(src), "window": [a.start, end],
              "model": a.model, "language": info.language,
              "segments": rows,
              "note": "independent ASR - the audio was NOT told what it should say"}
    if a.out:
        Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=1))
        print(f"\nwritten: {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
