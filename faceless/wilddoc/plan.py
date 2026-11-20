"""timeline.json + shotlist.txt + assets -> 08-compose/plan.json (frames) and stock_jobs.json.

Every cut, overlay and story sound is placed on the first sound of its anchor word. Shots longer than
style.cut.max_shot_s are auto-split into punch-in jump cuts (zoom/cut/glitch cycle) so the picture changes every
<= ~3 s (iteration v4 note: "much faster cutting"). Stressed words (loudness > line median + 2.6 dB) become camera kicks.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

from . import WildDocError
from . import shotlist as SL
from .project import Project, norm, read_json, write_json

LOOKS = {"neutral", "dusk", "ice", "night", "fire", "dawn", "jungle", "desert", "ocean"}


def stressed_words(project: Project, words: list[dict], style: dict) -> None:
    """Mark w['stress'] from the voice loudness (needs numpy + ffmpeg; silently skipped otherwise)."""
    try:
        import numpy as np
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(project.voice_master), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                             capture_output=True, check=True).stdout
    except Exception:  # noqa: BLE001 - optional enhancement
        for w in words:
            w["stress"] = False
        return
    pcm = np.frombuffer(raw, np.float32)
    for w in words:
        seg = pcm[int(w["start"] * 16000):max(int(w["end"] * 16000), int(w["start"] * 16000) + 160)]
        w["db"] = float(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9)) if len(seg) else -120.0
    st = style.get("stress", {})
    by: dict[int, list[dict]] = {}
    for w in words:
        by.setdefault(w["line"], []).append(w)
    for ws in by.values():
        sp = [w["db"] for w in ws if w.get("spoken", True)]
        med = float(np.median(sp)) if sp else 0.0
        for w in ws:
            w["stress"] = bool(w.get("spoken", True) and w["db"] > med + st.get("db_over_median", 2.6)
                               and (w["end"] - w["start"]) > st.get("min_len_s", 0.22))


def _clipdur(public: Path, rel: str, cache: dict) -> float:
    if rel not in cache:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(public / rel)],
                             capture_output=True, text=True).stdout.strip()
        cache[rel] = float(out) if out else 0.0
    return cache[rel]


def build(project: Project, allow_missing: bool = False) -> dict:
    style = project.style()
    fps = int(style["fps"])
    T = project.timeline()
    LINES = {ln["i"]: ln for ln in T["lines"]}
    WORDS = T["words"]
    DUR = T["duration"]
    NF = int(round(DUR * fps))
    f = lambda s: int(round(s * fps))  # noqa: E731
    if not project.shotlist_path.exists():
        raise WildDocError("No shotlist yet. Run `faceless wild-doc draft <project>` and direct it.")
    sl = SL.parse(project.shotlist_path.read_text(encoding="utf-8"))
    stressed_words(project, WORDS, style)
    by_line: dict[int, list[dict]] = {}
    for w in WORDS:
        by_line.setdefault(w["line"], []).append(w)

    def anchor_time(li: int, anchor: str, after: int = -1) -> tuple[float, int]:
        if li not in LINES:
            raise WildDocError(f"L{li} is not a script line (the script has {len(LINES)} lines; see 01-audio/lines.txt)")
        ws = by_line.get(li, [])
        if anchor == "^":
            return LINES[li]["start"], -1
        for k, w in enumerate(ws):
            if k > after and norm(anchor) == norm(w["text"]):
                return w["start"], k
        raise WildDocError(f"anchor '{anchor}' not found in L{li} (after word {after + 1}): {' '.join(w['text'] for w in ws)}")

    public = project.p("public")
    picks = read_json(project.p("assets", "stock", "picks.json"), {})
    refs = read_json(project.p("assets", "ref", "refs.json"), {})
    graphics = read_json(project.p("direction", "graphics.json"), {})
    missing: dict[str, set] = {"stock": set(), "plates": set(), "refs": set(), "graphics": set()}

    # ---------- rows -> timed shots
    shots = []
    first_line = min((li for li in sl["rows"] if LINES.get(li, {}).get("spoken", True)), default=None)
    for li in sorted(sl["rows"]):
        L = LINES.get(li)
        if L is None:
            raise WildDocError(f"shotlist row L{li}: no such script line")
        if not L.get("spoken", True):
            continue  # line dropped by the voice edit
        idx = -1
        for j, item in enumerate(sl["rows"][li]):
            if j == 0:
                spec, t0 = item, (0.0 if li == first_line else max(0.0, L["start"] - 0.12))
            else:
                a, _, spec = item.partition("=")
                t0, idx = anchor_time(li, a.strip(), idx)
                t0 -= 0.04
            o = SL.parse_spec(spec)
            o.update(t0=t0, line=li, chapter=L["chapter"])
            shots.append(o)
    if not shots:
        raise WildDocError("The shotlist has no rows for spoken lines.")
    shots.sort(key=lambda o: o["t0"])
    for a, b in zip(shots, shots[1:]):
        a["t1"] = b["t0"]
    shots[-1]["t1"] = DUR

    cut = style.get("cut", {})
    max_shot, split_to = cut.get("max_shot_s", 3.3), cut.get("split_to_s", 2.4)
    cyc = cut.get("jump_cycle", ["zoom", "cut", "glitch"])
    split = []
    for o in shots:
        d = o["t1"] - o["t0"]
        if o["kind"] == "mg" or d <= max_shot:
            split.append(o)
            continue
        n = int(math.ceil(d / split_to))
        step = d / n
        for k in range(n):
            p = dict(o, t0=o["t0"] + k * step, t1=o["t0"] + (k + 1) * step)
            if k:
                p["sub_i"] = k
                p["trans"] = cyc[k % len(cyc)]
                if p["kind"] == "stock":
                    p["off"] = o["off"] + k * step  # the clip keeps running across the jump cut
            split.append(p)
    shots = split

    stock_jobs, cache, out_shots = [], {}, []
    for n, o in enumerate(shots):
        fr, to = f(o["t0"]), f(o["t1"])
        if to - fr < 2:
            continue
        look = o.get("look") or project.chapter_style(o["chapter"]).get("look", "neutral")
        if look not in LOOKS:
            raise WildDocError(f"unknown look {look!r} (chapter {o['chapter']}); use one of {sorted(LOOKS)}")
        sh = {"i": n, "from": fr, "dur": to - fr, "kind": o["kind"], "look": look, "line": o["line"], "chapter": o["chapter"]}
        for k in ("trans", "fx", "blur", "gray", "sub_i"):
            if k in o:
                sh[k] = o[k]
        if o["kind"] == "stock":
            pk = picks.get(o["name"])
            if not pk or not (public / pk["file"]).exists():
                missing["stock"].add(o["name"])
                if allow_missing:
                    sh.update(kind="mg", mg="card", props={"kicker": "MISSING STOCK", "title": o["name"]})
                    out_shots.append(sh)
                continue
            sh.update(file=pk["file"], off=o["off"], name=o["name"])
            cd = _clipdur(public, pk["file"], cache)
            need = (to - fr) / fps
            if sh["off"] + need > cd - 0.15:
                sh["off"] = max(0.0, cd - 0.15 - need)
            if need > cd - 0.15:
                sh["off"] = 0.0
                sh["rate"] = round(max(0.4, (cd - 0.2) / need), 3)
            key = f'{pk["file"]}_{look}_{sh["off"]:.2f}_{sh.get("rate", 1)}_{to - fr}_{int(bool(o.get("blur")))}{int(bool(o.get("gray")))}'
            seg = "shots/S" + hashlib.md5(key.encode()).hexdigest()[:10] + ".mp4"
            stock_jobs.append({"src": pk["file"], "out": seg, "off": sh["off"], "frames": to - fr, "rate": sh.get("rate", 1),
                               "look": look, "blur": bool(o.get("blur")), "gray": bool(o.get("gray"))})
            sh["seg"] = seg
        elif o["kind"] == "ref":
            r = refs.get(o["id"])
            if not r or not (public / r["img"]).exists():
                missing["refs"].add(o["id"])
                if allow_missing:
                    sh.update(kind="mg", mg="card", props={"kicker": "MISSING REF", "title": o["id"]})
                    out_shots.append(sh)
                continue
            sh.update(id=o["id"], img=r["img"], bg=r["bg"])
            if not o.get("nolabel"):
                sh.update(label=r.get("label", ""), sub=r.get("sub", ""), badge=r.get("badge", ""))
        elif o["kind"] == "plate":
            img, dep = f"plates/{o['id']}.jpg", f"depth/{o['id']}_depth.png"
            if not ((public / img).exists() and (public / dep).exists()):
                missing["plates"].add(o["id"])
                if allow_missing:
                    sh.update(kind="mg", mg="card", props={"kicker": "MISSING PLATE", "title": o["id"]})
                    out_shots.append(sh)
                continue
            sh.update(img=img, depth=dep, move=o["move"], id=o["id"])
        else:
            props = dict(graphics.get(o["key"], graphics.get(o["mg"], {})))
            if o["mg"] not in ("black",) and o["key"] not in graphics and o["mg"] not in graphics:
                missing["graphics"].add(o["key"])
            bg = props.pop("bg", None)
            if bg:
                name, _, off = bg.partition("@")
                pk = picks.get(name)
                if pk:
                    props.update(bgFile=pk["file"], bgFrom=float(off or 0))
            if "punchWord" in props:
                props["punchAt"] = f(anchor_time(o["line"], props.pop("punchWord"))[0]) - fr
            sh.update(mg=o["mg"], props=props)
        sh["kicks"] = [f(w["start"]) - fr for w in WORDS if w.get("stress") and o["t0"] + 0.2 < w["start"] < o["t1"] - 0.1]
        out_shots.append(sh)

    hard_missing = {k: sorted(v) for k, v in missing.items() if v and k != "graphics"}
    if hard_missing and not allow_missing:
        raise WildDocError("Assets missing for the plan: " + json.dumps(hard_missing, ensure_ascii=False) +
                           "  -> make them (see `faceless wild-doc status`), or preview with `plan --allow-missing`.")

    # ---------- overlays
    out_ov = []
    for ov in sl["overlays"]:
        t0, _ = anchor_time(ov["line"], ov["anchor"])
        t0 -= 0.05
        props = dict(ov["props"])
        if ov["kind"] == "poll":
            try:
                props["commentAt"] = f(anchor_time(ov["line"], props.pop("commentWord", "Comment"))[0]) - f(t0)
            except WildDocError:
                pass
        look = project.chapter_style(LINES[ov["line"]]["chapter"]).get("look", "neutral")
        out_ov.append({"from": f(t0), "dur": f(ov["sec"]), "kind": ov["kind"], "props": props, "look": look})
    cuts = [s["from"] for s in out_shots]
    for o in out_ov:  # end on a nearby cut: no card fading over the next picture
        if o["kind"] == "poll":
            continue
        end = o["from"] + o["dur"]
        near = [c for c in cuts if abs(c - end) <= 18 and c - o["from"] >= fps]
        if near:
            o["dur"] = min(near, key=lambda c: abs(c - end)) - o["from"]

    # ---------- captions (off by default: the delivered film had no subtitles) - script spelling, karaoke chunks
    caps = []
    if style.get("captions"):
        nocap = [(s["from"], s["from"] + s["dur"]) for s in out_shots if s["kind"] == "mg" and s.get("mg") in ("title", "endcard")]
        for li in sorted(by_line):
            ws = [w for w in by_line[li] if w.get("spoken", True)]
            chunk = []
            for k, w in enumerate(ws):
                chunk.append({"t": w["text"], "from": f(w["start"]), "to": f(w["end"]), "s": bool(w.get("stress"))})
                n_chars = sum(len(c["t"]) + 1 for c in chunk)
                left = len(ws) - 1 - k
                soft = (len(chunk) >= 5 or n_chars > 30) and not (0 < left <= 2 and len(chunk) < 7)
                endp = w["text"].endswith(("।", ",", "?", ".", "!"))
                if soft or (endp and len(chunk) >= 2 and left != 1) or k == len(ws) - 1:
                    a = chunk[0]["from"]
                    if not any(x <= a < y for x, y in nocap):
                        caps.append({"from": a, "to": chunk[-1]["to"], "w": chunk})
                    chunk = []
        for a, b in zip(caps, caps[1:]):
            a["to"] = min(a["to"] + f(0.25), b["from"])
        if caps:
            caps[-1]["to"] += f(0.4)

    plan = {"fps": fps, "width": style.get("width", 1920), "height": style.get("height", 1080), "durationInFrames": NF,
            "shots": out_shots, "overlays": out_ov, "captions": caps, "theme": style.get("theme", {}),
            "chapters": [{"name": c["name"], "title": project.chapter_style(c["name"]).get("title") or c["title"], "from": f(c["start"])}
                         for c in T["chapters"]]}
    write_json(project.plan_path, plan, indent=None)
    write_json(project.p("compose", "stock_jobs.json"), stock_jobs, indent=0)

    durs = [s["dur"] / fps for s in out_shots]
    reuse = []
    seen: dict[str, int] = {}
    for s in out_shots:
        k = s.get("name") or s.get("id")
        if k and k in seen and s["from"] - seen[k] < 60 * fps:
            reuse.append(f"{k}@L{s['line']}")
        if k:
            seen[k] = s["from"]
    report = {"plan": str(project.plan_path), "shots": len(out_shots), "avg_shot_s": round(sum(durs) / len(durs), 2),
              "max_shot_s": round(max(durs), 2), "overlays": len(out_ov), "captions": len(caps), "stock_segments": len(stock_jobs),
              "kinds": {k: sum(s["kind"] == k for s in out_shots) for k in ("stock", "plate", "ref", "mg")},
              "reused_within_60s": reuse[:30], "missing": {k: sorted(v) for k, v in missing.items() if v}}
    project.log("plan", **{k: v for k, v in report.items() if k != "reused_within_60s"})
    return report
