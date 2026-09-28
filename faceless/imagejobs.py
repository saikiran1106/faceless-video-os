"""Keyframe (and reference-sheet) image jobs, shared by every host.

One compiled `image_jobs.json` drives all four hosts:

  codex        the agent calls Codex's built-in image tool per job, then `faceless images record`
  claude-code  `faceless browser generate` drives ChatGPT in a persistent browser session
  api          `faceless images generate` calls the OpenAI Images API directly
  manual       `faceless images prompts` writes PROMPTS.md; a human generates and drops files in

The job, not the host, owns the prompt, references and output path, so a frame
generated on one host is interchangeable with one generated on another.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from PIL import Image

from .config import load_profile
from .engine import ProductionEngine, StateError
from .io import atomic_write_json, load_json, sha256_file, sha256_text, utc_now

SHOT_WORDS = {
    "extreme_wide": "extreme wide establishing shot, subject small in a vast frame",
    "wide": "wide shot, full figures and environment visible",
    "medium": "medium shot, waist-up framing",
    "close": "close-up on the face and emotion",
    "extreme_close": "extreme close-up on a telling detail",
    "insert": "insert shot of a key object, shallow depth of field",
    "overhead": "top-down overhead shot",
}


def _jobs_path(engine: ProductionEngine, sheets: bool = False) -> Path:
    return engine.control_dir / ("sheet_jobs.json" if sheets else "image_jobs.json")


def _abs(project: Path, ref: str) -> str:
    path = Path(ref)
    return str(path if path.is_absolute() else (project / path).resolve())


def compile_keyframe_job(beat: dict[str, Any], bible: dict[str, Any], project: Path, aspect: str) -> dict[str, Any]:
    characters = {c["character_id"]: c for c in bible.get("characters", [])}
    locations = {loc["location_id"]: loc for loc in bible.get("locations", [])}
    refs: list[str] = []
    contracts: list[str] = []
    for cid in beat.get("character_ids", []):
        if cid not in characters:
            raise StateError(f"{beat['beat_id']} uses unknown character {cid}")
        refs += characters[cid].get("reference_paths", [])
        contracts.append(f"CHARACTER {characters[cid]['name']}: {characters[cid]['prompt_contract']}")
    if beat.get("location_id"):
        loc = locations.get(beat["location_id"])
        if not loc:
            raise StateError(f"{beat['beat_id']} uses unknown location {beat['location_id']}")
        refs += loc.get("reference_paths", [])
        contracts.append(f"LOCATION {loc['name']}: {loc['prompt_contract']}")
    orientation = {"9:16": "vertical 9:16", "16:9": "horizontal 16:9", "1:1": "square 1:1"}[aspect]
    shot = SHOT_WORDS.get(beat.get("shot_scale", ""), "")
    prompt = "\n\n".join(part for part in [
        f"Generate exactly ONE {orientation} image. No grid, collage, split screen, variants, text, captions, logos or watermark.",
        f"STYLE: {bible['style_contract']}",
        *contracts,
        f"THIS MOMENT (the narration heard over this frame): {beat['text']}",
        f"SHOW: {beat.get('visual_objective', '')}",
        f"FRAMING: {shot}" if shot else "",
        f"MOOD: {beat['mood']}" if beat.get("mood") else "",
        "Keep the main subject inside the central safe area; the edges may be cropped.",
        f"AVOID: {bible['negative_contract']}" if bible.get("negative_contract") else "",
        "If reference images are attached, match their identity, wardrobe and palette exactly." if refs else "",
    ] if part)
    unique_refs = [_abs(project, r) for r in dict.fromkeys(refs)]
    return {
        "job_id": f"IMG-{beat['beat_id']}",
        "kind": "keyframe",
        "beat_id": beat["beat_id"],
        "keyframe_id": beat["keyframe_id"],
        "aspect": aspect,
        "prompt": prompt,
        "prompt_sha256": sha256_text(prompt),
        "reference_paths": unique_refs,
        "output_path": f"07-keyframes/images/{beat['keyframe_id']}.png",
        "max_attempts": 2,
    }


def compile_sheet_job(entity: dict[str, Any], kind: str, bible: dict[str, Any], project: Path) -> dict[str, Any]:
    ident = entity[f"{kind}_id"]
    if kind == "character":
        body = entity.get("sheet_prompt") or (
            f"Character reference sheet for {entity['name']}: front view, three-quarter view and profile, full body plus one face close-up, "
            f"on a plain neutral background. {entity['prompt_contract']}"
        )
    else:
        body = entity.get("sheet_prompt") or f"Establishing reference plate of {entity['name']}, no people. {entity['prompt_contract']}"
    prompt = f"Generate exactly ONE image. No text, labels or watermark.\n\nSTYLE: {bible['style_contract']}\n\n{body}"
    return {
        "job_id": f"SHEET-{ident}",
        "kind": f"{kind}_sheet",
        "beat_id": f"SHEET-{ident}",
        "keyframe_id": f"SHEET-{ident}",
        "aspect": "16:9" if kind == "location" else "1:1",
        "prompt": prompt,
        "prompt_sha256": sha256_text(prompt),
        "reference_paths": [_abs(project, r) for r in entity.get("reference_paths", [])],
        "output_path": f"05-visual-bible/sheets/{ident}.png",
        "max_attempts": 2,
    }


def compile_jobs(engine: ProductionEngine, sheets: bool = False) -> dict[str, Any]:
    project = engine.project_root
    bible = load_json(engine.artifact_path("visual_bible"))
    if sheets:
        jobs = [compile_sheet_job(c, "character", bible, project) for c in bible["characters"]]
        jobs += [compile_sheet_job(loc, "location", bible, project) for loc in bible["locations"]]
    else:
        beats = load_json(engine.artifact_path("beats"))
        aspect = load_profile(engine.state()["format"])["aspect"]
        missing = [b["beat_id"] for b in beats["beats"] if not b.get("visual_objective", "").strip()]
        if missing:
            raise StateError(f"Direct these beats first (no visual_objective): {missing[:10]}{'...' if len(missing) > 10 else ''}")
        jobs = [compile_keyframe_job(b, bible, project, aspect) for b in beats["beats"]]
    doc = {"version": "1.0", "host": engine.state()["host"], "compiled_at": utc_now(), "jobs": jobs}
    atomic_write_json(_jobs_path(engine, sheets), doc)
    return {"path": str(_jobs_path(engine, sheets)), "jobs": len(jobs)}


def load_jobs(engine: ProductionEngine, sheets: bool = False) -> list[dict[str, Any]]:
    path = _jobs_path(engine, sheets)
    if not path.exists():
        raise StateError(f"No compiled jobs at {path}. Run `faceless images jobs{' --sheets' if sheets else ''}` first.")
    return load_json(path)["jobs"]


def write_prompts(engine: ProductionEngine, sheets: bool = False) -> Path:
    jobs = load_jobs(engine, sheets)
    lines = ["# Image prompts", "", "Generate ONE image per block. Save each with the exact file name shown, then run", "`faceless images record <project> <ID> <file>` (or drop them all in `07-keyframes/inbox/` and run `faceless images ingest`).", ""]
    for job in jobs:
        lines += [f"## {job['keyframe_id']}  ->  `{Path(job['output_path']).name}`", ""]
        if job["reference_paths"]:
            lines += ["Attach these references:", *[f"- {r}" for r in job["reference_paths"]], ""]
        lines += ["```text", job["prompt"], "```", ""]
    out = engine.project_root / ("05-visual-bible" if sheets else "07-keyframes") / ("SHEET_PROMPTS.md" if sheets else "PROMPTS.md")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _aspect_ratio(aspect: str) -> float:
    w, h = aspect.split(":")
    return float(w) / float(h)


MAX_CROP_DEVIATION = 0.20  # e.g. a 2:3 portrait (1024x1536) is 18.5% off 9:16 and is cropped


def fit_aspect(img: Image.Image, aspect: str) -> tuple[Image.Image, bool]:
    """Centre-crop to the exact target aspect when the image is close to it.

    Image models often return 2:3 / 3:2 instead of 9:16 / 16:9. Prompts keep the
    subject in the central safe area, so a centre crop loses only the margins.
    Anything further off than MAX_CROP_DEVIATION is a wrong-shape generation and
    is rejected - cropping it would cut the subject.
    """
    width, height = img.size
    want = _aspect_ratio(aspect)
    deviation = abs(width / height - want) / want
    if deviation <= 0.01:
        return img, False
    if deviation > MAX_CROP_DEVIATION:
        raise StateError(f"Image is {width}x{height} ({deviation:.0%} off {aspect}); regenerate at the right aspect")
    if width / height > want:
        new_w = round(height * want)
        left = (width - new_w) // 2
        return img.crop((left, 0, left + new_w, height)), True
    new_h = round(width / want)
    top = (height - new_h) // 2
    return img.crop((0, top, width, top + new_h)), True


def record(engine: ProductionEngine, ident: str, source: Path, host: str = "", sheets: bool | None = None) -> dict[str, Any]:
    """File one generated image against its job: decode, fit the aspect, save PNG, write a receipt.

    `ident` may be a keyframe_id, beat_id or job_id. Identity comes from the human or agent
    who LOOKED at the image - never from a download's filename or arrival order.
    """
    candidates = []
    for is_sheet in ((False, True) if sheets is None else (sheets,)):
        try:
            candidates += load_jobs(engine, is_sheet)
        except StateError:
            continue
    job = next((j for j in candidates if ident in (j["keyframe_id"], j["beat_id"], j["job_id"])), None)
    if not job:
        raise StateError(f"No image job matches {ident!r}")
    source = Path(source).expanduser()
    if not source.exists():
        raise StateError(f"Image not found: {source}")
    try:
        with Image.open(source) as img:
            img.load()
            original_size = img.size
            rgb = img.convert("RGB")
    except Exception as exc:  # noqa: BLE001
        raise StateError(f"Could not decode {source}: {exc}") from exc
    try:
        fitted, cropped = fit_aspect(rgb, job["aspect"])
    except StateError as exc:
        raise StateError(f"{source.name} for {job['keyframe_id']}: {exc}") from exc
    dest = engine.project_root / job["output_path"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    same_file = dest.exists() and dest.resolve() == source.resolve()
    if dest.exists():
        backup = dest.with_name(f"{dest.stem}.{'orig' if same_file else 'prev'}{dest.suffix}")
        shutil.copy2(dest, backup)
    if cropped or not same_file or source.suffix.lower() != ".png":
        fitted.save(dest, "PNG")
    receipt = {
        "job_id": job["job_id"],
        "keyframe_id": job["keyframe_id"],
        "beat_id": job["beat_id"],
        "prompt_sha256": job["prompt_sha256"],
        "source": host or engine.state()["host"],
        "original_file": str(source),
        "path": job["output_path"],
        "sha256": sha256_file(dest),
        "width": fitted.size[0],
        "height": fitted.size[1],
        "recorded_at": utc_now(),
    }
    if cropped:
        receipt["cropped_from"] = list(original_size)
    receipts = engine.project_root / "07-keyframes" / "receipts"
    atomic_write_json(receipts / f"{job['keyframe_id']}.json", receipt)
    return receipt


def ingest_folder(engine: ProductionEngine, folder: Path) -> dict[str, Any]:
    """Record every file in `folder` whose stem is exactly a keyframe/sheet id (e.g. KF007.png).
    Anything else is reported, not guessed."""
    recorded, skipped = [], []
    ids = {j["keyframe_id"] for j in load_jobs(engine)}
    try:
        ids |= {j["keyframe_id"] for j in load_jobs(engine, True)}
    except StateError:
        pass
    for path in sorted(Path(folder).expanduser().iterdir()):
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            continue
        if path.stem in ids:
            recorded.append(record(engine, path.stem, path)["keyframe_id"])
        else:
            skipped.append(path.name)
    return {"recorded": recorded, "skipped_unrecognised_names": skipped}


def generate_api(engine: ProductionEngine, sheets: bool = False, only: list[str] | None = None, limit: int | None = None) -> dict[str, Any]:
    from .providers.images import OpenAIImages

    client = OpenAIImages()
    jobs = [j for j in load_jobs(engine, sheets) if not (engine.project_root / j["output_path"]).exists()]
    if only:
        jobs = [j for j in jobs if {j["keyframe_id"], j["beat_id"]} & set(only)]
    if limit:
        jobs = jobs[:limit]
    done, failed = [], []
    for job in jobs:
        dest = engine.project_root / "07-keyframes" / "_api" / f"{job['keyframe_id']}.png"
        engine.record_cost(client.estimate_usd(1), "openai-images", f"img:{engine.project_root.name}:{job['keyframe_id']}:{job['prompt_sha256'][:12]}", "keyframes")
        try:
            client.generate(job["prompt"], job["aspect"], dest, job["reference_paths"])
            record(engine, job["keyframe_id"], dest, host="api", sheets=sheets)
            done.append(job["keyframe_id"])
        except Exception as exc:  # noqa: BLE001
            failed.append({"keyframe_id": job["keyframe_id"], "error": str(exc)[:300]})
    return {"generated": done, "failed": failed, "remaining": len(load_jobs(engine, sheets)) - len(done)}


def estimate_api(engine: ProductionEngine, sheets: bool = False) -> dict[str, Any]:
    from .providers.images import OpenAIImages

    client = OpenAIImages()
    todo = [j for j in load_jobs(engine, sheets) if not (engine.project_root / j["output_path"]).exists()]
    return {"model": client.model, "quality": client.quality, "images": len(todo), "estimated_usd": round(client.estimate_usd(len(todo)), 2), "worst_case_usd": round(client.estimate_usd(len(todo) * 2), 2)}


def apply_sheets(engine: ProductionEngine) -> dict[str, Any]:
    """Add generated sheets to their character/location reference_paths in the visual bible."""
    path = engine.artifact_path("visual_bible")
    bible = load_json(path)
    added = []
    for group, key in (("characters", "character_id"), ("locations", "location_id")):
        for item in bible[group]:
            sheet = f"05-visual-bible/sheets/{item[key]}.png"
            if (engine.project_root / sheet).exists() and sheet not in item.setdefault("reference_paths", []):
                item["reference_paths"].insert(0, sheet)
                added.append(item[key])
    atomic_write_json(path, bible)
    return {"added_sheets_for": added}


def build_manifest(engine: ProductionEngine) -> dict[str, Any]:
    """Scan every keyframe job's output. Keeps prior QA verdicts only for unchanged pixels."""
    path = engine.artifact_path("keyframes")
    prior = {k["keyframe_id"]: k for k in load_json(path)["keyframes"]} if path.exists() else {}
    receipts_dir = engine.project_root / "07-keyframes" / "receipts"
    entries, missing = [], []
    for job in load_jobs(engine):
        out = engine.project_root / job["output_path"]
        if not out.exists():
            missing.append(job["keyframe_id"])
            continue
        receipt_path = receipts_dir / f"{job['keyframe_id']}.json"
        receipt = load_json(receipt_path) if receipt_path.exists() else {}
        if receipt.get("sha256") != sha256_file(out):
            # Written straight to output_path by a host (browser adapter, a human): file it properly.
            receipt = record(engine, job["keyframe_id"], out, host=engine.state()["host"], sheets=False)
        digest = sha256_file(out)
        with Image.open(out) as img:
            width, height = img.size
        old = prior.get(job["keyframe_id"], {})
        same = old.get("sha256") == digest
        entries.append({
            "keyframe_id": job["keyframe_id"],
            "beat_id": job["beat_id"],
            "path": job["output_path"],
            "sha256": digest,
            "width": width,
            "height": height,
            "source": receipt.get("source") or engine.state()["host"],
            "prompt_sha256": job["prompt_sha256"],
            "qa_status": old.get("qa_status", "pending") if same else "pending",
            "qa_note": old.get("qa_note", "") if same else "",
        })
    if not entries:
        raise StateError("No keyframe images exist yet")
    atomic_write_json(path, {"version": "1.0", "keyframes": entries})
    return {"path": str(path), "keyframes": len(entries), "missing": missing, "pending_qa": [e["keyframe_id"] for e in entries if e["qa_status"] != "pass"]}


def set_qa(engine: ProductionEngine, ids: list[str], status: str, note: str = "") -> dict[str, Any]:
    path = engine.artifact_path("keyframes")
    doc = load_json(path)
    wanted = set(ids)
    changed = []
    for entry in doc["keyframes"]:
        if "all" in wanted or entry["keyframe_id"] in wanted or entry["beat_id"] in wanted:
            entry["qa_status"], entry["qa_note"] = status, note
            changed.append(entry["keyframe_id"])
    if not changed:
        raise StateError(f"No keyframes matched {ids}")
    atomic_write_json(path, doc)
    return {"updated": changed, "status": status}
