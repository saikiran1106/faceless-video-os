"""Flag images that came back as grids or collages instead of single frames.

ChatGPT sometimes answers a batch item with a contact sheet of small panels even
when the prompt forbids grids, collages and variants. Such an image is unusable
as a keyframe, and it is not caught by any technical check: it decodes, it is
the right size, and it is 9:16.

A panelled image has gutters - full-height or full-width lines where the picture
changes abruptly and stays changed. We score each interior column and row by how
strongly it separates its neighbours, and flag an image that has several such
lines. Reported, never auto-deleted: the operator confirms on the contact sheet.

Usage:
    python tools/browser/detect_grids.py <staging_dir> [--threshold 3]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

# A gutter is a strong, narrow, sustained discontinuity. Panels in a ChatGPT
# contact sheet are separated by a bright or dark 1-4px rule.
EDGE_Z = 6.0          # how many std devs above the mean a gutter must stand
MIN_GAP = 0.08        # gutters closer together than 8% of the axis are one line


def gutters(diff: np.ndarray) -> list:
    """Indices of sustained full-span discontinuities along one axis."""
    if diff.size < 16:
        return []
    mean, std = float(diff.mean()), float(diff.std()) or 1.0
    lo, hi = int(0.06 * len(diff)), int(0.94 * len(diff))   # ignore the border
    cand = [i for i in range(lo, hi) if (diff[i] - mean) / std > EDGE_Z]
    out = []
    for i in cand:
        if not out or (i - out[-1]) > MIN_GAP * len(diff):
            out.append(i)
    return out


def analyse(path: Path) -> dict:
    with Image.open(path) as im:
        a = np.asarray(im.convert("L").resize((360, 640)), dtype=np.float64)
    col = np.abs(np.diff(a, axis=1)).mean(axis=0)      # vertical gutters
    row = np.abs(np.diff(a, axis=0)).mean(axis=1)      # horizontal gutters
    vc, hr = gutters(col), gutters(row)
    # One centre split is a diptych; two or more on an axis, or splits on both
    # axes, is a panel grid.
    panels = (len(vc) + 1) * (len(hr) + 1)
    return {"file": path.name, "vertical_gutters": len(vc),
            "horizontal_gutters": len(hr), "implied_panels": panels,
            "suspect": panels >= 3}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("staging")
    a = ap.parse_args()
    d = Path(a.staging)
    rows = [analyse(p) for p in sorted(d.glob("*.png"))]
    bad = [r for r in rows if r["suspect"]]
    print(json.dumps({"checked": len(rows), "suspect": len(bad),
                      "files": [f"{r['file']} ({r['implied_panels']} panels)"
                                for r in bad]}, indent=1))
    (d / "grid_report.json").write_text(json.dumps(rows, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
