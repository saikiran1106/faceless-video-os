"""Build labelled contact sheets from staged keyframes.

Two jobs at once:

* **Binding.** ChatGPT returns a batch's images out of order, so a staged image
  carries no beat identity. A sheet puts a whole batch on one page with its slot
  number burnt in, so the images can be bound to beats by what they depict
  rather than by the position they arrived in.
* **QA.** The reviewer contract requires beat-labelled contact sheets before
  `pixels_reviewed` can be set. The same sheets serve.

Usage:
    python tools/browser/contact_sheet.py <project> [--cols 5] [--tile 340]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size: int):
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/System/Library/Fonts/Helvetica.ttc",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def build_sheet(images, out_path: Path, cols: int = 5, tile: int = 340,
                title: str = "") -> Path:
    """Lay out (label, path) pairs on one sheet, label burnt into each tile."""
    if not images:
        raise ValueError("no images")
    label_h = max(26, tile // 11)
    rows = (len(images) + cols - 1) // cols
    head = 44 if title else 0
    cell_w, cell_h = tile, int(tile * 16 / 9) + label_h

    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h + head), "#111214")
    draw = ImageDraw.Draw(sheet)
    if title:
        draw.text((12, 12), title, fill="#f2f2f2", font=_font(26))

    for i, (label, path) in enumerate(images):
        x = (i % cols) * cell_w
        y = head + (i // cols) * cell_h
        try:
            with Image.open(path) as im:
                im = im.convert("RGB")
                im.thumbnail((tile, int(tile * 16 / 9)), Image.LANCZOS)
                sheet.paste(im, (x + (tile - im.width) // 2, y + label_h))
        except Exception:                          # noqa: BLE001
            draw.rectangle([x, y + label_h, x + tile, y + cell_h], fill="#331111")
        draw.rectangle([x, y, x + cell_w, y + label_h], fill="#1e6fd9")
        draw.text((x + 6, y + 4), label, fill="#ffffff", font=_font(label_h - 10))
    sheet.save(out_path, "PNG")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--cols", type=int, default=5)
    ap.add_argument("--tile", type=int, default=340)
    a = ap.parse_args()

    proj = Path(a.project)
    staging = proj / "06-keyframes" / "_staging"
    index = json.loads((staging / "staged_index.json").read_text())
    out_dir = staging / "sheets"
    out_dir.mkdir(parents=True, exist_ok=True)

    by_batch = {}
    for rec in index["images"]:
        by_batch.setdefault(rec["batch"], []).append(rec)

    made = []
    for b in sorted(by_batch):
        recs = sorted(by_batch[b], key=lambda r: r["slot"])
        cands = recs[0]["candidate_beats"]
        items = [(f"slot {r['slot']:02d}", r["path"]) for r in recs]
        out = out_dir / f"batch{b:02d}_sheet.png"
        build_sheet(items, out, cols=a.cols, tile=a.tile,
                    title=f"batch {b}  -  {len(recs)} images  -  candidate beats "
                          f"{cands[0]}..{cands[-1]}")
        made.append({"batch": b, "sheet": str(out), "images": len(recs),
                     "candidate_beats": cands})
    print(json.dumps(made, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
