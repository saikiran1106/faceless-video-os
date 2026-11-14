"""Independently transcribe an audio master with ElevenLabs Scribe.

Why this exists
---------------
Forced alignment does NOT verify a script. It forces whatever text you hand it
onto the audio and reports a perfect match, so a script saying one thing while
the voice says another still aligns 311/311. That is exactly how the wrong
deity reached 62 keyframes, a thumbnail and two renders of Part 22.

Independent ASR is the only check that catches it: it asks the audio what it
says without being told the answer first.

Usage:
    python tools/browser/scribe_verify.py <audio> --out report.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

import requests

ENDPOINT = "https://api.elevenlabs.io/v1/speech-to-text"


def load_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if key:
        return key
    for line in Path(".env").read_text().splitlines():
        if line.startswith("ELEVENLABS_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("ELEVENLABS_API_KEY not found")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="scribe_v1")
    ap.add_argument("--language", default="tel")
    a = ap.parse_args()

    src = Path(a.audio)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                "format=duration", "-of", "csv=p=0", str(src)],
                               capture_output=True, text=True).stdout.strip())
    print(f"Scribe: {src.name}  {dur:.2f}s  model={a.model}  lang={a.language}")

    with open(src, "rb") as fh:
        r = requests.post(
            ENDPOINT,
            headers={"xi-api-key": load_key()},
            files={"file": (src.name, fh, "audio/mpeg")},
            data={"model_id": a.model, "language_code": a.language,
                  "timestamps_granularity": "word", "diarize": "false"},
            timeout=600)
    if r.status_code != 200:
        raise SystemExit(f"Scribe failed {r.status_code}: {r.text[:400]}")
    doc = r.json()

    words = doc.get("words") or []
    text = doc.get("text", "")
    out = {"audio": str(src), "duration_s": dur, "model": a.model,
           "language": doc.get("language_code"), "text": text,
           "words": [{"start": w.get("start"), "end": w.get("end"),
                      "word": w.get("text")} for w in words
                     if w.get("type", "word") == "word"],
           "note": "independent ASR - the model was not told what the script says"}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"\n{len(out['words'])} words transcribed -> {a.out}\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
