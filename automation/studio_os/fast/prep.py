"""Plan-driven helpers: storyboard queues, review sheets, clip matching and Remotion props.

Everything derives from <project>/05-visuals/shot_plan.json (never hand-edit derived files).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RC = REPO / "remotion-composer"
ADAPTER = {"image_mode": "chatgpt_playwright", "tool": "playwright_browser", "browser_required": True,
           "execution": "sequential_persistent_chat"}


def _plan(project: Path) -> dict:
    return json.loads((project / "05-visuals/shot_plan.json").read_text())


def build_queues(project: Path) -> dict:
    """refs_queue.json (reference sheets) + storyboard_queue.json (one first-frame per beat)."""
    project = Path(project)
    plan = _plan(project)
    plan_sha = hashlib.sha256((project / "05-visuals/shot_plan.json").read_bytes()).hexdigest()
    rel = project.resolve().relative_to(REPO)
    ref_file = {r["id"]: r["file"] for r in plan["references"]}
    ref_role = {r["id"]: r.get("role", "style") for r in plan["references"]}

    def job(jid, beat, kf, prompt, refs, out):
        return {"version": "1.0", "job_id": jid, "beat_id": beat, "keyframe_id": kf, "host": "claude-code",
                "adapter": ADAPTER, "prompt": prompt, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "reference_paths": [str(rel / ref_file[r]) for r in refs], "output_path": out,
                "max_attempts": 2, "status": "queued"}

    head = "Generate exactly ONE image; no grid, collage or variants.\n\n"
    mascot = plan.get("mascot", "")
    refs_q = [job(f"IMG-{r['id']}", r["id"], r["id"],
                  head + f"{plan['style']}\n\n{mascot if r.get('role') == 'character' else ''}\n\n{r['prompt']}\n\n{plan['rules']}",
                  r.get("refs", []), r["file"]) for r in plan["references"]]
    sb_q = []
    for b in plan["beats"]:
        if b.get("reuse_reference"):
            continue
        parts = [plan["style"]]
        if any(ref_role[r] == "style" for r in b["refs"]):
            parts.append("Match the attached style frame's look and lighting.")
        if mascot and any(ref_role[r] == "character" for r in b["refs"]):
            parts.append(mascot + " Match the attached character sheet exactly.")
        parts += [f"STORYBOARD FRAME (this is the FIRST frame of a video shot): {b['frame']}",
                  f"NARRATION AT THIS BEAT: \"{b['lines']}\"", plan["rules"]]
        sb_q.append(job(f"SB-{b['id']}", b["id"], f"SB_{b['id']}", head + "\n\n".join(parts), b["refs"],
                        f"05-visuals/storyboards/{b['id']}.png"))
    for name, q in (("refs_queue.json", refs_q), ("storyboard_queue.json", sb_q)):
        (project / ".faceless").mkdir(exist_ok=True)
        (project / ".faceless" / name).write_text(json.dumps(
            {"version": "1.0", "host": "claude-code", "shot_plan_sha256": plan_sha, "jobs": q}, ensure_ascii=False, indent=1))
    # beats that reuse a reference image verbatim (e.g. a loop-back frame)
    for b in plan["beats"]:
        if b.get("reuse_reference"):
            dst = project / f"05-visuals/storyboards/{b['id']}.png"
            dst.parent.mkdir(parents=True, exist_ok=True)
            src = project / ref_file[b["reuse_reference"]]
            if src.exists():
                shutil.copy2(src, dst)
    return {"refs": len(refs_q), "storyboards": len(sb_q)}


def contact_sheet(project: Path, out: Path | None = None) -> str:
    from PIL import Image, ImageDraw, ImageFont
    project = Path(project)
    plan = _plan(project)
    beats = plan["beats"]
    W, H, CAP, cols = 300, 533, 92, 5
    rows = (len(beats) + cols - 1) // cols
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 22)
    small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 15)
    sheet = Image.new("RGB", (cols * W, rows * (H + CAP)), (18, 18, 22))
    d = ImageDraw.Draw(sheet)
    for i, b in enumerate(beats):
        x, y = (i % cols) * W, (i // cols) * (H + CAP)
        f = project / f"05-visuals/storyboards/{b['id']}.png"
        if f.exists():
            sheet.paste(Image.open(f).convert("RGB").resize((W - 6, H - 6)), (x + 3, y + 3))
        else:
            d.text((x + 20, y + H // 2), "MISSING", font=font, fill=(255, 80, 80))
        d.text((x + 8, y + H + 4), f"{b['id']}  {b['t0']:.1f}–{b['t1']:.1f}s", font=font, fill=(0, 220, 255))
        words, line, k = b["lines"].split(), "", 0
        for w in words + [None]:
            if w is None or len(line) + len(w) > 40:
                d.text((x + 8, y + H + 32 + k * 18), line, font=small, fill=(230, 230, 230)); k += 1; line = ""
                if w is None or k == 3: break
            line = (line + " " + w).strip()
    out = out or project / "05-visuals/contact_sheet.jpg"
    sheet.save(out, quality=90)
    return str(out)


def match_clips(project: Path) -> list[dict]:
    """First frame of every clip vs every storyboard: proves each clip starts on its own beat."""
    import tempfile
    from PIL import Image, ImageChops, ImageStat
    project = Path(project)
    sb = {p.stem: Image.open(p).convert("L").resize((180, 320))
          for p in sorted((project / "05-visuals/storyboards").glob("B??.png"))}
    rows = []
    for clip in sorted((project / "06-video/clips").glob("B??_v*.mp4")):
        with tempfile.NamedTemporaryFile(suffix=".png") as t:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-frames:v", "1", t.name], check=True)
            fr = Image.open(t.name).convert("L").resize((180, 320))
        sc = sorted((round(ImageStat.Stat(ImageChops.difference(fr, im)).mean[0], 1), k) for k, im in sb.items())
        beat = clip.stem.split("_")[0]
        rows.append({"clip": clip.name, "beat": beat, "best": sc[0][1], "best_diff": sc[0][0],
                     "ok": sc[0][1] == beat or (sc[0][0] < 4 and any(k == beat and d < 4 for d, k in sc[:3]))})
    return rows


def build_props(project: Path, fps: int = 30) -> dict:
    """Remotion props for the generic TechReel composition (clips, morph rates, titles, word captions)."""
    project = Path(project)
    plan = _plan(project)
    slug = plan["project"]
    pub = RC / "public" / slug
    pub.mkdir(parents=True, exist_ok=True)
    off = plan.get("timeline_offset_s", 0.0)

    def dur(f):
        return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                     str(f)], capture_output=True, text=True).stdout)

    beats, prev_morph = [], False
    for b in plan["beats"]:
        clips = sorted((project / "06-video/clips").glob(f"{b['id']}_v*.mp4"))
        clip = clips[-1]
        shutil.copy2(clip, pub / clip.name)
        cd, bd = dur(clip), b["t1"] - b["t0"]
        morph = b["transition"].startswith("first_last:")
        rate = round(cd / bd, 4) if (morph or cd < bd) else 1.0
        beats.append({"id": b["id"], "from": round(b["t0"] * fps), "frames": round(bd * fps),
                      "src": f"{slug}/{clip.name}", "rate": rate, "overlay": b.get("overlay", ""),
                      "titlePos": b.get("title_pos", "top"), "titleTop": b.get("title_top", 230),
                      "titleBig": bool(b.get("title_big")), "punch": not prev_morph and b is not plan["beats"][0]})
        prev_morph = morph
    audio = project / plan["audio"]
    shutil.copy2(audio, pub / "mix.wav")
    total = round(dur(audio) * fps)

    al = json.loads((project / "03-audio/v4/provider_alignment.json").read_text())
    al = al.get("alignment", al)
    words, cur, ws, we, inb = [], "", None, None, False
    for c, s, e in zip(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]):
        if c == "[": inb = True; continue
        if c == "]": inb = False; continue
        if inb: continue
        if c.isspace():
            if cur.strip(): words.append((cur, ws, we))
            cur, ws = "", None; continue
        if ws is None: ws = s
        cur += c; we = e
    if cur.strip(): words.append((cur, ws, we))
    words = [{"w": w.replace("…", "").strip(), "s": round(s + off, 3), "e": round(e + off, 3)}
             for w, s, e in words if w.replace("…", "").strip()]
    chunks, cw = [], []
    for i, w in enumerate(words):
        cw.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        gap = (nxt["s"] - w["e"]) if nxt else 9
        if len(cw) == 3 or re.search(r"[.?!,:]$", w["w"]) or gap > 0.25 or not nxt:
            chunks.append({"s": cw[0]["s"], "e": (nxt["s"] if nxt and gap < 0.6 else cw[-1]["e"] + 0.15), "words": cw})
            cw = []
    props = {"fps": fps, "durationInFrames": total, "audio": f"{slug}/mix.wav", "beats": beats,
             "captions": chunks, "accents": plan.get("accents", {}), "captionTop": plan.get("caption_top", 1400),
             "videoZoom": plan.get("video_zoom", 1.0), "videoZoomOrigin": plan.get("video_zoom_origin", "50% 0%")}
    out = RC / f"props_{slug.replace('-', '_')}.json"
    out.write_text(json.dumps(props, ensure_ascii=False, indent=1))
    return {"props": str(out), "beats": len(beats), "captions": len(chunks), "frames": total}


def render(project: Path, version: str = "v1") -> str:
    project = Path(project)
    slug = _plan(project)["project"]
    props = RC / f"props_{slug.replace('-', '_')}.json"
    out = (project / f"07-final/instagram/{slug}_{version}.mp4").resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["npx", "remotion", "render", "TechReel", str(out), f"--props={props}", "--codec=h264",
                    "--crf=17", "--audio-bitrate=320k", "--log=error"], cwd=RC, check=True)
    return str(out)
