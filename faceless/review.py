"""Review aids: pictures an agent (or human) can actually look at.

`contact_sheet` lays every keyframe beside the narration it must illustrate.
`render_sheet` samples the FINISHED video at each beat's midpoint, so sync and
caption placement are checked on real rendered pixels, not on labels.
"""
from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .config import load_channel, repo_root
from .engine import ProductionEngine, StateError
from .io import load_json
from .media import require


def _font(size: int) -> ImageFont.ImageFont:
    custom = load_channel()["style"].get("font_file")
    if custom and (repo_root() / custom).exists():
        return ImageFont.truetype(str(repo_root() / custom), size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def _grid(cells: list[tuple[Image.Image, str]], out: Path, columns: int, thumb_w: int = 320) -> Path:
    if not cells:
        raise StateError("Nothing to lay out")
    ratio = cells[0][0].height / cells[0][0].width
    thumb_h = int(thumb_w * ratio)
    caption_h = 110
    rows = (len(cells) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * (thumb_w + 12) + 12, rows * (thumb_h + caption_h + 12) + 12), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    font = _font(15)
    for i, (img, label) in enumerate(cells):
        x = 12 + (i % columns) * (thumb_w + 12)
        y = 12 + (i // columns) * (thumb_h + caption_h + 12)
        sheet.paste(img.convert("RGB").resize((thumb_w, thumb_h)), (x, y))
        lines = textwrap.wrap(label, width=42)[:6]
        draw.multiline_text((x, y + thumb_h + 4), "\n".join(lines), fill=(235, 235, 235), font=font, spacing=2)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=88)
    return out


def contact_sheet(engine: ProductionEngine, columns: int = 0) -> Path:
    beats = load_json(engine.artifact_path("beats"))["beats"]
    kf_path = engine.artifact_path("keyframes")
    keyframes = {k["keyframe_id"]: k for k in load_json(kf_path)["keyframes"]} if kf_path.exists() else {}
    cells = []
    for beat in beats:
        kf = keyframes.get(beat["keyframe_id"])
        img_path = engine.project_root / (kf["path"] if kf else f"07-keyframes/images/{beat['keyframe_id']}.png")
        img = Image.open(img_path) if img_path.exists() else Image.new("RGB", (540, 960), (60, 0, 0))
        status = kf["qa_status"] if kf else "MISSING"
        cells.append((img, f"{beat['keyframe_id']} [{status}] {beat['start_s']:.1f}-{beat['end_s']:.1f}s\n{beat['text']}"))
    cols = columns or (6 if cells[0][0].height > cells[0][0].width else 4)
    return _grid(cells, engine.project_root / "07-keyframes" / "contact_sheet.jpg", cols)


def render_sheet(engine: ProductionEngine, platform: str = "youtube", columns: int = 0) -> Path:
    render = engine.project_root / "08-compose" / "renders" / f"{engine.project_root.name}_{platform}.mp4"
    if not render.exists():
        raise StateError(f"No render for {platform}: {render}")
    beats = load_json(engine.artifact_path("beats"))["beats"]
    frames_dir = engine.project_root / "08-compose" / "review_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    cells = []
    for beat in beats:
        mid = (beat["start_s"] + beat["end_s"]) / 2
        out = frames_dir / f"{beat['beat_id']}.jpg"
        subprocess.run([require("ffmpeg"), "-y", "-ss", f"{mid:.3f}", "-i", str(render), "-frames:v", "1", "-q:v", "3", str(out)], capture_output=True, check=True)
        cells.append((Image.open(out), f"{beat['beat_id']} @ {mid:.1f}s\n{beat['text']}"))
    cols = columns or (6 if cells[0][0].height > cells[0][0].width else 4)
    return _grid(cells, engine.project_root / "08-compose" / f"render_sheet_{platform}.jpg", cols)


def summary(engine: ProductionEngine) -> dict[str, Any]:
    state = engine.state()
    return {
        "project": state["project_id"],
        "stage": state["current_stage"],
        "stages": {k: v["status"] for k, v in state["stages"].items()},
        "approvals": {k: v["status"] for k, v in state["approvals"].items()},
        "budget": state["budget"],
    }
