"""Picture assets for wild-doc: real stock footage (Pixabay), real-photo evidence (Wikimedia Commons or your own files),
your own/Flow clips, and AI plates (+ depth maps for 2.5D parallax).

Picking is by EYE: every search writes a labelled contact sheet; the agent (or you) looks at it and writes the pick lists:
  02-direction/stock_picks.txt   "<pixabay id> <name>"                         -> S:<name>
  02-direction/refs.txt          "<id> <tag>#<n> | LABEL | sub line | BADGE"    -> R:<id>
                                 "<id> local:<file in 06-assets/ref> | LABEL | sub | BADGE"
  02-direction/plates.json       {"<id>": {"prompt": "..."}}                    -> P:<id>  (images land in 06-assets/plates/<id>.png)
  06-assets/clips/<name>.mp4     your own or Google Flow clips                  -> S:<name>
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from . import WildDocError
from .project import Project, read_json, write_json

UA = {"User-Agent": "FacelessVideoOS/1.0 (open-source video pipeline)"}
DEPTH_MODEL = Path(os.environ.get("FACELESS_DEPTH_MODEL", str(Path.home() / ".faceless" / "models" / "depth-anything-v2-small.onnx"))).expanduser()
DEPTH_URL = "https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/main/onnx/model.onnx"
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")


def _get(url: str, timeout: int = 120) -> bytes:
    r = requests.get(url, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r.content


def _sheet(tiles_src: list[tuple[str, str]], out: Path, w: int = 480, h: int = 270) -> None:
    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.load_default(size=20)
    except TypeError:  # Pillow < 10.1
        font = ImageFont.load_default()
    tiles = []
    for url, label in tiles_src:
        try:
            im = Image.open(io.BytesIO(_get(url, 60))).convert("RGB")
        except Exception:  # noqa: BLE001
            im = Image.new("RGB", (w, h), (60, 0, 0))
        im.thumbnail((w, h))
        t = Image.new("RGB", (w, h))
        t.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
        d = ImageDraw.Draw(t)
        d.rectangle((0, 0, w, 26), fill=(0, 0, 0))
        d.text((6, 3), label, fill=(255, 255, 0), font=font)
        tiles.append(t)
    if not tiles:
        return
    cols = 4
    sheet = Image.new("RGB", (w * cols, h * ((len(tiles) + cols - 1) // cols)))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * w, (i // cols) * h))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=80)


def _safe(q: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in q)[:60]


# ---------------------------------------------------------------- stock (Pixabay)
def stock_search(project: Project, queries: list[str], per_page: int = 12) -> dict:
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        raise WildDocError("PIXABAY_API_KEY is not set (free key: https://pixabay.com/api/docs/). Add it to .env.")
    d = project.p("assets", "stock")
    cpath = d / "candidates.json"
    cands = read_json(cpath, {})
    out = {}
    for q in queries:
        url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode({"key": key, "q": q, "per_page": per_page, "safesearch": "true"})
        hits = requests.get(url, timeout=60).json().get("hits", [])
        rows = []
        for h in hits:
            v = h["videos"]
            big = v.get("large") if v.get("large", {}).get("url") else v["medium"]
            rows.append({"id": h["id"], "dur": h["duration"], "w": big["width"], "h": big["height"], "url": big["url"],
                         "thumb": v["medium"].get("thumbnail") or v["small"].get("thumbnail"), "tags": h["tags"], "page": h["pageURL"]})
        cands[q] = rows
        sheet = d / "sheets" / f"{_safe(q)}.jpg"
        _sheet([(r["thumb"], f"{r['id']}  {r['dur']}s  {r['w']}x{r['h']}") for r in rows], sheet)
        out[q] = {"hits": len(rows), "sheet": str(sheet)}
    write_json(cpath, cands)
    return {"searched": out, "next": "LOOK at each sheet, then add '<id> <name>' lines to 02-direction/stock_picks.txt and run `stock-fetch`."}


def _proxy(src: Path, dst: Path, fps: int) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".tmp.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-an", "-vf",
                    f"scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps={fps},format=yuv420p",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-g", str(fps), str(tmp)], check=True)
    tmp.replace(dst)


def stock_fetch(project: Project) -> dict:
    fps = int(project.style()["fps"])
    picks_txt = project.p("direction", "stock_picks.txt")
    picks = read_json(project.p("assets", "stock", "picks.json"), {})
    cands = read_json(project.p("assets", "stock", "candidates.json"), {})
    by_id = {r["id"]: r for rows in cands.values() for r in rows}
    want = []
    if picks_txt.exists():
        for ln in picks_txt.read_text(encoding="utf-8").splitlines():
            ln = ln.split("#", 1)[0].strip()
            if ln:
                sid, name = ln.split(None, 1)
                want.append((int(sid), name.strip()))
    done, errs = [], []

    def one(item):
        sid, name = item
        rel = f"stock/{name}__{sid}.mp4"
        if name in picks and (project.p("public") / picks[name]["file"]).exists() and picks[name].get("id") == sid:
            return None
        c = by_id.get(sid)
        if not c:
            return f"{name}: id {sid} not in candidates.json (search for it first)"
        raw = project.p("assets", "stock", "raw", f"{name}__{sid}.mp4")
        if not raw.exists():
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_bytes(_get(c["url"], 600))
        _proxy(raw, project.p("public") / rel, fps)
        picks[name] = {"id": sid, "file": rel, "page": c["page"], "tags": c["tags"], "source": "pixabay"}
        done.append(name)
        return None

    with ThreadPoolExecutor(3) as ex:
        errs = [e for e in ex.map(one, want) if e]
    # own / Flow clips
    cdir = project.p("assets", "clips")
    for f in sorted(cdir.glob("*")) if cdir.exists() else []:
        if f.suffix.lower() not in (".mp4", ".mov", ".m4v", ".webm"):
            continue
        rel = f"stock/{f.stem}__clip.mp4"
        dst = project.p("public") / rel
        if not dst.exists() or dst.stat().st_mtime < f.stat().st_mtime:
            _proxy(f, dst, fps)
            done.append(f.stem)
        picks[f.stem] = {"id": None, "file": rel, "source": "clip"}
    write_json(project.p("assets", "stock", "picks.json"), picks)
    return {"fetched": done, "errors": errs, "available": sorted(picks)}


# ---------------------------------------------------------------- real-photo evidence (Wikimedia Commons)
def refs_search(project: Project, pairs: list[tuple[str, str]]) -> dict:
    d = project.p("assets", "ref")
    cpath = d / "ref_candidates.json"
    cands = read_json(cpath, {})
    out = {}
    for tag, q in pairs:
        u = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "query", "format": "json", "generator": "search", "gsrsearch": f"filetype:bitmap {q}", "gsrnamespace": 6,
            "gsrlimit": 12, "prop": "imageinfo", "iiprop": "url|size|extmetadata|mime", "iiurlwidth": 1920})
        pages = requests.get(u, headers=UA, timeout=60).json().get("query", {}).get("pages", {})
        rows = []
        for p in sorted(pages.values(), key=lambda p: p.get("index", 0)):
            ii = p["imageinfo"][0]
            m = ii.get("extmetadata", {})
            if ii["mime"] not in ("image/jpeg", "image/png") or ii["width"] < 900:
                continue
            rows.append({"title": p["title"], "url": ii.get("thumburl") or ii["url"], "w": ii["width"], "h": ii["height"], "page": ii["descriptionurl"],
                         "license": m.get("LicenseShortName", {}).get("value", "?"), "artist": m.get("Artist", {}).get("value", "?")[:200]})
        cands[tag] = rows
        sheet = d / "sheets" / f"{_safe(tag)}.jpg"
        _sheet([(r["url"].replace("1920px", "500px"), f"{i} {r['license'][:14]} {r['w']}x{r['h']}") for i, r in enumerate(rows)], sheet, 480, 320)
        out[tag] = {"hits": len(rows), "sheet": str(sheet)}
    write_json(cpath, cands)
    return {"searched": out, "next": "LOOK at each sheet; add '<id> <tag>#<n> | LABEL | sub | BADGE' lines to 02-direction/refs.txt; run `refs-fetch`."}


def refs_fetch(project: Project) -> dict:
    from PIL import Image, ImageEnhance, ImageFilter

    txt = project.p("direction", "refs.txt")
    if not txt.exists():
        return {"fetched": [], "note": "no 02-direction/refs.txt"}
    cands = read_json(project.p("assets", "ref", "ref_candidates.json"), {})
    refs = read_json(project.p("assets", "ref", "refs.json"), {})
    credits = read_json(project.p("assets", "ref", "credits.json"), {})
    pub = project.p("public", "ref")
    pub.mkdir(parents=True, exist_ok=True)
    done, errs = [], []
    for raw in txt.read_text(encoding="utf-8").splitlines():
        ln = raw.strip()
        if not ln or ln.startswith("#"):
            continue
        parts = [p.strip() for p in ln.split("|")]
        rid, src = parts[0].split(None, 1)
        label, sub, badge = (parts + ["", "", ""])[1:4]
        refs[rid] = {"img": f"ref/{rid}.jpg", "bg": f"ref/{rid}_bg.jpg", "label": label, "sub": sub, "badge": badge}
        if (pub / f"{rid}.jpg").exists() and (pub / f"{rid}_bg.jpg").exists():
            continue
        try:
            if src.startswith("local:"):
                data = (project.p("assets", "ref") / src[6:]).read_bytes()
                credits[rid] = {"source": "own file", "file": src[6:]}
            else:
                tag, _, n = src.partition("#")
                c = cands[tag][int(n or 0)]
                data = _get(c["url"], 180)
                credits[rid] = {k: c[k] for k in ("title", "page", "license", "artist")}
            im = Image.open(io.BytesIO(data)).convert("RGB")
            im.thumbnail((1920, 1080))
            im.save(pub / f"{rid}.jpg", quality=92)
            bg = im.copy()
            s = max(1920 / bg.width, 1080 / bg.height)
            bg = bg.resize((int(bg.width * s) + 1, int(bg.height * s) + 1))
            l, t = (bg.width - 1920) // 2, (bg.height - 1080) // 2
            bg = bg.crop((l, t, l + 1920, t + 1080)).filter(ImageFilter.GaussianBlur(24))
            ImageEnhance.Brightness(bg).enhance(0.45).save(pub / f"{rid}_bg.jpg", quality=85)
            done.append(rid)
        except Exception as e:  # noqa: BLE001
            errs.append(f"{rid}: {e}")
    write_json(project.p("assets", "ref", "refs.json"), refs)
    write_json(project.p("assets", "ref", "credits.json"), credits)
    return {"fetched": done, "errors": errs, "available": sorted(refs)}


# ---------------------------------------------------------------- AI plates + depth
def download_depth_model() -> dict:
    if DEPTH_MODEL.exists() and DEPTH_MODEL.stat().st_size > 1_000_000:
        return {"depth_model": str(DEPTH_MODEL), "status": "present"}
    DEPTH_MODEL.parent.mkdir(parents=True, exist_ok=True)
    tmp = DEPTH_MODEL.with_suffix(".part")
    with requests.get(DEPTH_URL, headers=UA, stream=True, timeout=600) as r:
        r.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    tmp.replace(DEPTH_MODEL)
    return {"depth_model": str(DEPTH_MODEL), "status": "downloaded"}


def _depth_session():
    try:
        import onnxruntime as ort
    except ImportError:
        return None
    if not DEPTH_MODEL.exists():
        return None
    return ort.InferenceSession(str(DEPTH_MODEL), providers=["CPUExecutionProvider"])


def depth_map(src: Path, dst: Path, sess) -> str:
    """Depth-Anything-V2-small (white = near) or, without the model, a pseudo depth (ground plane + soft luminance)."""
    import numpy as np
    from PIL import Image, ImageFilter

    im = Image.open(src).convert("RGB")
    W, H = im.size
    if sess is not None:
        s = 728 / max(W, H)
        w14, h14 = max(14, round(W * s / 14) * 14), max(14, round(H * s / 14) * 14)
        x = np.asarray(im.resize((w14, h14), Image.BICUBIC), dtype=np.float32) / 255.0
        x = ((x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]).transpose(2, 0, 1)[None].astype(np.float32)
        name = sess.get_inputs()[0].name
        d = sess.run(None, {name: x})[0]
        d = d.reshape(d.shape[-2], d.shape[-1])
        kind = "depth-anything-v2-small"
    else:
        g = np.asarray(im.convert("L").resize((W // 4, H // 4)), dtype=np.float32) / 255.0
        ramp = np.linspace(0.0, 1.0, g.shape[0])[:, None] * np.ones((1, g.shape[1]))
        d = 0.75 * ramp + 0.25 * g
        kind = "pseudo (install onnxruntime + `faceless wild-doc setup --depth` for real depth)"
    d = (d - d.min()) / (d.max() - d.min() + 1e-6)
    out = Image.fromarray((d * 255).astype("uint8")).resize((W, H), Image.BICUBIC)
    out = out.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(6))  # dilate + blur: no doubled edges
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst)
    return kind


def prep_plates(project: Project) -> dict:
    from PIL import Image

    src_dir = project.p("assets", "plates")
    pub = project.p("public")
    sess = None
    made, kinds = [], set()
    for f in sorted(src_dir.glob("*")) if src_dir.exists() else []:
        if f.suffix.lower() not in IMG_EXT:
            continue
        jpg, dep = pub / "plates" / f"{f.stem}.jpg", pub / "depth" / f"{f.stem}_depth.png"
        fresh = jpg.exists() and jpg.stat().st_mtime >= f.stat().st_mtime and dep.exists()
        if fresh:
            continue
        jpg.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(f).convert("RGB")
        im.thumbnail((2400, 2400))
        im.save(jpg, quality=92)
        if sess is None:
            sess = _depth_session() or False
        kinds.add(depth_map(jpg, dep, sess or None))
        made.append(f.stem)
    have = sorted(p.stem for p in (pub / "plates").glob("*.jpg")) if (pub / "plates").exists() else []
    return {"prepared": made, "depth": sorted(kinds), "plates_ready": len(have)}


def plate_jobs(project: Project, only: list[str] | None = None) -> list[dict]:
    plates = read_json(project.p("direction", "plates.json"), {})
    src_dir = project.p("assets", "plates")
    jobs = []
    for pid, spec in plates.items():
        if only and pid not in only:
            continue
        if any((src_dir / f"{pid}{e}").exists() for e in IMG_EXT):
            continue
        jobs.append({"id": pid, "prompt": spec["prompt"], "aspect": "16:9", "refs": spec.get("refs", [])})
    return jobs


def status(project: Project) -> dict:
    """What exists, what the shotlist still needs."""
    from . import shotlist as SL

    out: dict = {"project": str(project.root)}
    out["voice_master"] = project.voice_master.exists()
    out["transcript"] = project.p("audio", "transcript.json").exists()
    out["timeline"] = project.timeline_path.exists()
    out["shotlist"] = project.shotlist_path.exists()
    if not out["shotlist"]:
        return out
    sl = SL.parse(project.shotlist_path.read_text(encoding="utf-8"))
    need = {"stock": set(), "plates": set(), "refs": set(), "graphics": set()}
    for items in sl["rows"].values():
        for j, it in enumerate(items):
            o = SL.parse_spec(it if j == 0 else it.partition("=")[2])
            {"stock": need["stock"], "plate": need["plates"], "ref": need["refs"], "mg": need["graphics"]}[o["kind"]].add(
                o.get("name") or o.get("id") or o.get("key"))
    picks = read_json(project.p("assets", "stock", "picks.json"), {})
    refs = read_json(project.p("assets", "ref", "refs.json"), {})
    graphics = read_json(project.p("direction", "graphics.json"), {})
    pub = project.p("public")
    out["missing"] = {
        "stock": sorted(n for n in need["stock"] if n not in picks),
        "plates": sorted(p for p in need["plates"] if not (pub / "plates" / f"{p}.jpg").exists()),
        "plate_prompts": sorted(p for p in need["plates"] if p not in read_json(project.p("direction", "plates.json"), {})),
        "refs": sorted(r for r in need["refs"] if r not in refs),
        "graphics_props": sorted(g for g in need["graphics"] if g not in graphics and g.split("#")[0] not in graphics and g != "black"),
    }
    out["needed"] = {k: len(v) for k, v in need.items()}
    out["overlays"] = len(sl["overlays"])
    out["story_sfx"] = len(sl["story"])
    for k in ("plan", "mix", "master"):
        out[k] = {"plan": project.plan_path, "mix": project.p("compose", "mix.wav"), "master": project.master_path}[k].exists()
    return out
