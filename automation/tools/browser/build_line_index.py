"""Turn a forced alignment into per-line timings.

The aligner gives word timings; beats are built from LINES, because a line is
the unit the script was written in and the unit a shot serves. This walks the
script's lines through the aligned word list in order, so a line's bounds are
the first and last word actually spoken in it - never an even division of the
runtime.

Usage:
    python tools/browser/build_line_index.py <project> <alignment.json> <cleaned.txt>
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def norm(w: str) -> str:
    return re.sub(r"[^ఀ-౿\w]", "", w or "").strip().lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("alignment")
    ap.add_argument("cleaned")
    a = ap.parse_args()

    proj = Path(a.project)
    doc = json.loads(Path(a.alignment).read_text())
    words = doc.get("words") or doc.get("segments") or doc
    if isinstance(words, dict):
        words = words.get("words", [])

    aligned = []
    for w in words:
        t = w.get("word") or w.get("text") or w.get("label") or ""
        s = w.get("start", w.get("start_s"))
        e = w.get("end", w.get("end_s"))
        if s is None or e is None:
            continue
        aligned.append({"w": norm(t), "start": float(s), "end": float(e)})

    lines = [l.strip() for l in Path(a.cleaned).read_text().splitlines() if l.strip()]

    idx, cursor, unmatched = [], 0, 0
    for ln, text in enumerate(lines, 1):
        n = len([t for t in text.split() if norm(t)])
        if n == 0 or cursor >= len(aligned):
            continue
        w0 = cursor
        w1 = min(cursor + n - 1, len(aligned) - 1)
        idx.append({"line": ln, "w0": w0, "w1": w1,
                    "start": round(aligned[w0]["start"], 2),
                    "end": round(aligned[w1]["end"], 2),
                    "text": text, "nwords": n})
        cursor = w1 + 1

    # make the timeline continuous: a line starts where the previous ended
    for i in range(1, len(idx)):
        idx[i]["start"] = idx[i - 1]["end"]
    if idx:
        idx[0]["start"] = 0.0

    out = proj / ".faceless" / "line_index.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    print(json.dumps({"lines": len(idx), "aligned_words": len(aligned),
                      "script_words": sum(l["nwords"] for l in idx),
                      "span": [idx[0]["start"], idx[-1]["end"]] if idx else None,
                      "out": str(out)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
