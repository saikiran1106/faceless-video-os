"""Verify a render against its beat manifest by sampling the actual video.

Technical checks pass on files that are bound to the wrong beats, so the only
real proof is looking at the frames the viewer will see. This pulls a frame
from the middle of each sampled beat, puts it on a labelled sheet with its
timestamp and narration, and compares it against the keyframe that beat is
bound to.

Usage:
    python tools/browser/verify_render.py <project> <video> [--every 4]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.browser.contact_sheet import build_sheet        # noqa: E402

from PIL import Image                                       # noqa: E402


def grab(video: Path, t: float, out: Path) -> bool:
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video),
         "-frames:v", "1", "-y", str(out)], capture_output=True)
    return r.returncode == 0 and out.exists()


def similar(a: Path, b: Path, size=(64, 114)) -> float:
    """Crude normalised similarity - enough to catch a frame bound to the
    wrong beat, which is a completely different picture, not a subtle one."""
    try:
        ia = Image.open(a).convert("L").resize(size)
        ib = Image.open(b).convert("L").resize(size)
    except Exception:                                        # noqa: BLE001
        return -1.0
    pa, pb = list(ia.getdata()), list(ib.getdata())
    diff = sum(abs(x - y) for x, y in zip(pa, pb)) / len(pa)
    return 1.0 - diff / 255.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("video")
    ap.add_argument("--every", type=int, default=4, help="sample every Nth beat")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    proj = Path(a.project)
    video = Path(a.video)
    beats = json.loads((proj / "05-beats" / "beat_manifest.json").read_text())["beats"]
    jobs = {j["beat_id"]: j for j in
            json.loads((proj / ".faceless" / "image_jobs.json").read_text())["jobs"]}

    work = proj / "08-verify"
    work.mkdir(parents=True, exist_ok=True)
    frames_dir = work / "frames"
    frames_dir.mkdir(exist_ok=True)

    rows, items = [], []
    for b in beats[::a.every]:
        mid = (b["start_s"] + b["end_s"]) / 2
        f = frames_dir / f"{b['beat_id']}_at_{mid:.1f}s.png"
        if not grab(video, mid, f):
            rows.append({"beat_id": b["beat_id"], "error": "frame grab failed"})
            continue
        src = proj / jobs[b["beat_id"]]["output_path"]
        score = similar(f, src) if src.exists() else -1.0
        rows.append({"beat_id": b["beat_id"], "t": round(mid, 2),
                     "keyframe_id": b["keyframe_id"],
                     "similarity_to_bound_keyframe": round(score, 3),
                     "narration": b["narration_te"][:60]})
        items.append((f"{b['beat_id']} @{mid:.0f}s", str(f)))

    out = Path(a.out) if a.out else work / f"{video.stem}_beat_sheet.png"
    if items:
        build_sheet(items, out, cols=5, tile=300,
                    title=f"{video.name} - sampled every {a.every} beats")

    ok = [r for r in rows if r.get("similarity_to_bound_keyframe", -1) >= 0.55]
    report = {"video": str(video), "sampled": len(rows),
              "matching_bound_keyframe": len(ok),
              "accuracy": round(len(ok) / max(1, len(rows)), 3),
              "sheet": str(out) if items else None, "rows": rows}
    (work / f"{video.stem}_verify.json").write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=1))
    for r in rows:
        if r.get("similarity_to_bound_keyframe", 1) < 0.55:
            print("  LOW:", r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
