"""Grade stock -> render chunks (Remotion, software GL, verified + sealed) -> verified master -> thumbnail.

Lessons baked in: bake the stock grade with ffmpeg (CSS filters cost ~2 s/frame in software GL); render in ~60 s chunks
with 2 workers and `nice` (long hot renders flip bits on weak laptops); check every chunk's FRAME COUNT and decode, not
just a seal; encode the master per chunk, decode-verify each, then stream-copy concat; never run two heavy renders at once.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import WildDocError
from .project import REMOTION_DIR, Project, decode_errors, ffprobe_duration, frame_count, read_json, write_json

GRADE = {
    "neutral": "eq=contrast=1.04:saturation=0.95",
    "dusk": "eq=contrast=1.08:saturation=0.85:brightness=-0.03,colorbalance=rs=-0.04:bs=0.10:rh=0.10:bh=-0.08",
    "ice": "eq=contrast=1.10:saturation=0.62:brightness=-0.04,colorbalance=rs=-0.08:bs=0.12:rm=-0.05:bm=0.08:rh=-0.03:bh=0.06",
    "night": "eq=contrast=1.18:saturation=0.38:brightness=-0.20:gamma=0.85,colorbalance=rs=-0.15:gs=-0.05:bs=0.20:rm=-0.12:bm=0.15:rh=-0.10:bh=0.05",
    "fire": "eq=contrast=1.12:saturation=1.05:brightness=-0.03,colorbalance=rs=0.05:bs=0.10:rm=0.08:bm=-0.05:rh=0.12:bh=-0.12",
    "dawn": "eq=contrast=1.05:saturation=0.95,colorbalance=rs=0.04:rm=0.06:bm=-0.06:rh=0.10:gh=0.03:bh=-0.10",
    "jungle": "eq=contrast=1.08:saturation=1.08:brightness=-0.02,colorbalance=rs=-0.04:gs=0.04:gm=0.05:rh=0.05:bh=-0.06",
    "desert": "eq=contrast=1.08:saturation=0.9:brightness=0.0,colorbalance=rs=0.06:bs=-0.06:rm=0.08:bm=-0.08:rh=0.10:bh=-0.12",
    "ocean": "eq=contrast=1.08:saturation=0.85:brightness=-0.03,colorbalance=rs=-0.10:gs=0.02:bs=0.12:rm=-0.06:bm=0.08",
}
GUARD = Path(__file__).resolve().parents[2] / "automation" / "tools" / "media" / "media_guard.py"


def _x264(fps: int, crf: int = 17) -> list[str]:
    return ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-maxrate", "22M", "-bufsize", "44M", "-pix_fmt", "yuv420p",
            "-profile:v", "high", "-r", str(fps), "-x264-params", f"keyint={2 * fps}:min-keyint={fps}"]


def ensure_node() -> None:
    if not shutil.which("npx"):
        raise WildDocError("Node.js (npx) not found. Run ./install.sh or install Node 18+.")
    if not (REMOTION_DIR / "node_modules" / "remotion").exists():
        subprocess.run(["npm", "install", "--no-audit", "--no-fund", "--loglevel=error"], cwd=REMOTION_DIR, check=True)


# ---------------------------------------------------------------- stock grade
def grade(project: Project, workers: int = 3) -> dict:
    fps = int(project.style()["fps"])
    pub = project.p("public")
    jobs = read_json(project.p("compose", "stock_jobs.json"), [])
    (pub / "shots").mkdir(parents=True, exist_ok=True)

    def run(j):
        out = pub / j["out"]
        if out.exists() and frame_count(out) >= j["frames"]:
            return "skip"
        secs = j["frames"] / fps * j["rate"] + 0.3
        vf = [f"setpts=PTS/{j['rate']}" if j["rate"] != 1 else None, GRADE[j["look"]],
              "gblur=sigma=7" if j["blur"] else None, "hue=s=0.15" if j["gray"] else None,
              "vignette=angle=PI/4.2", "noise=alls=7:allf=t", f"fps={fps}", "format=yuv420p"]
        tmp = out.with_suffix(".tmp.mp4")
        for _ in range(3):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{j['off']:.3f}", "-t", f"{secs:.3f}", "-i", str(pub / j["src"]),
                            "-vf", ",".join(x for x in vf if x), "-frames:v", str(j["frames"] + 2), "-an",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-g", "12", str(tmp)], check=True)
            if frame_count(tmp) >= j["frames"] and decode_errors(tmp) == 0:
                tmp.replace(out)
                return "ok"
        return f"FAIL {j['out']}"

    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(run, jobs))
    # dark-clip check (v4 lesson: the night grade crushes already-dark clips to black)
    dark = []
    for j in jobs:
        out = pub / j["out"]
        if out.exists():
            y = _yavg(out)
            if y is not None and y < 20:
                dark.append({"segment": j["out"], "src": j["src"], "look": j["look"], "yavg": round(y, 1)})
    return {"segments": len(jobs), "made": res.count("ok"), "skipped": res.count("skip"), "failed": [r for r in res if r.startswith("FAIL")],
            "too_dark": dark[:30]}


def _yavg(path: Path) -> float | None:
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(path), "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YAVG", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    vals = [float(x.split("=")[1]) for x in r.splitlines() if "YAVG=" in x]
    return sum(vals) / len(vals) if vals else None


# ---------------------------------------------------------------- chunks
def _template_hash() -> str:
    h = hashlib.sha1()
    for f in sorted((REMOTION_DIR / "src").glob("*.tsx")):
        h.update(f.read_bytes())
    return h.hexdigest()[:8]


def chunks(plan: dict, chunk_s: float) -> list[tuple[int, int]]:
    fps, nf = plan["fps"], plan["durationInFrames"]
    starts = sorted({s["from"] for s in plan["shots"]})
    bounds, target = [0], chunk_s * fps
    for s in starts:
        if s - bounds[-1] >= target and nf - s > fps * 5:
            bounds.append(s)
    bounds.append(nf)
    return list(zip(bounds, bounds[1:]))


def _chunk_key(plan: dict, a: int, b: int, th: str) -> str:
    def touches(x, dur):
        return x < b and x + dur > a

    data = {"a": a, "b": b, "th": th, "theme": plan.get("theme"),
            "shots": [s for s in plan["shots"] if touches(s["from"] - 8, s["dur"] + 16)],
            "ov": [o for o in plan["overlays"] if touches(o["from"], o["dur"])],
            "caps": [c for c in plan["captions"] if touches(c["from"], c["to"] - c["from"])]}
    return hashlib.sha1(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:10]


def materialize_links(public: Path) -> list[str]:
    """Remotion's file server 404s files symlinked outside public/: replace such links with real copies."""
    fixed = []
    root = public.resolve()
    for f in public.rglob("*"):
        if f.is_symlink() and f.is_file():
            target = f.resolve()
            if root not in target.parents:
                f.unlink()
                shutil.copy2(target, f)
                fixed.append(str(f.relative_to(public)))
    return fixed


def _seal(path: Path) -> None:
    if GUARD.exists():
        subprocess.run([sys.executable, "-I", str(GUARD), "seal", str(path)], capture_output=True)


def render(project: Project, only: list[int] | None = None, concurrency: int | None = None) -> dict:
    ensure_node()
    style = project.style()
    R = style.get("render", {})
    plan = json.loads(project.plan_path.read_text(encoding="utf-8"))
    props = write_json(project.p("compose", "film_props.json"), {"plan": plan}, indent=None)
    th = _template_hash()
    cdir = project.p("compose", "chunks")
    cdir.mkdir(parents=True, exist_ok=True)
    tmpdir = project.root / ".wilddoc" / "tmp"
    tmpdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TMPDIR=str(tmpdir))
    manifest, made, times = [], [], []
    bundle = project.root / ".wilddoc" / "bundle"
    bundled = False
    for idx, (a, b) in enumerate(chunks(plan, float(R.get("chunk_s", 60)))):
        key = _chunk_key(plan, a, b, th)
        out = cdir / f"c{idx:02d}_{a}_{b}_{key}.mp4"
        manifest.append({"i": idx, "a": a, "b": b, "file": out.name})
        if out.exists() or (only is not None and idx not in only):
            continue
        if not bundled:  # bundle + copy public/ ONCE per run, not once per chunk (a full film's public/ is GBs)
            materialize_links(project.p("public"))
            shutil.rmtree(bundle, ignore_errors=True)
            subprocess.run(["npx", "remotion", "bundle", "src/index.tsx", f"--public-dir={project.p('public')}", f"--out-dir={bundle}",
                            "--log=error"], cwd=REMOTION_DIR, env=env, check=True, capture_output=True)
            bundled = True
        for stale in cdir.glob(f"c{idx:02d}_*.mp4"):
            stale.unlink()
        tmp = out.with_suffix(".tmp.mp4")
        ok = False
        for attempt in range(3):
            t0 = time.time()
            cmd = ["nice", "-n", "5"] if shutil.which("nice") else []
            cmd += ["npx", "remotion", "render", str(bundle), "Film", str(tmp), f"--props={props}",
                    f"--frames={a}-{b - 1}", f"--gl={R.get('gl', 'swangle')}", f"--concurrency={concurrency or R.get('concurrency', 2)}",
                    f"--crf={R.get('crf', 16)}", "--muted", f"--timeout={R.get('timeout_ms', 180000)}", "--log=error"]
            r = subprocess.run(cmd, cwd=REMOTION_DIR, env=env, capture_output=True, text=True)
            n = frame_count(tmp) if tmp.exists() else 0
            if r.returncode == 0 and n == b - a and decode_errors(tmp) == 0:
                tmp.replace(out)
                _seal(out)
                ok = True
                times.append(round(time.time() - t0))
                break
            (cdir / f"c{idx:02d}.log").write_text(f"attempt {attempt}: rc={r.returncode} frames={n}/{b - a}\n{r.stdout[-3000:]}\n{r.stderr[-6000:]}")
            time.sleep(5)
        if not ok:
            raise WildDocError(f"chunk {idx} (frames {a}-{b - 1}) failed 3 times; see {cdir / f'c{idx:02d}.log'}")
        made.append(idx)
    write_json(project.p("compose", "chunks.json"), manifest)
    return {"chunks": len(manifest), "rendered": made, "seconds_per_chunk": times}


# ---------------------------------------------------------------- master
def assemble(project: Project) -> dict:
    plan = json.loads(project.plan_path.read_text(encoding="utf-8"))
    fps = plan["fps"]
    manifest = read_json(project.p("compose", "chunks.json"))
    mix = project.p("compose", "mix.wav")
    if not manifest:
        raise WildDocError("No rendered chunks. Run `faceless wild-doc render`.")
    if not mix.exists():
        raise WildDocError("No mix. Run `faceless wild-doc mix`.")
    cdir, sdir = project.p("compose", "chunks"), project.p("compose", "segments")
    sdir.mkdir(parents=True, exist_ok=True)
    segs = []
    for c in manifest:
        src = cdir / c["file"]
        if not src.exists():
            raise WildDocError(f"chunk {c['i']} missing ({c['file']}): re-run `faceless wild-doc render`")
        a, b = c["a"], c["b"]
        out = sdir / f"seg_{Path(c['file']).stem}.mp4"
        segs.append(out)
        if out.exists() and frame_count(out) == b - a and decode_errors(out) == 0:
            continue
        # baked RGB split + static on glitch cuts (2 frames before to 4 after), local frame numbers
        gl = [(max(a, s["from"] - 2) - a, min(b - 1, s["from"] + 4) - a) for s in plan["shots"] if s.get("trans") == "glitch" and a <= s["from"] < b]
        vf = []
        if gl:
            en = "+".join(f"between(n,{x},{y})" for x, y in gl)
            vf = ["-vf", f"rgbashift=rh=-16:bh=16:gv=4:edge=smear:enable='{en}',noise=alls=28:allf=t:enable='{en}'"]
        for attempt in range(4):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), *vf, *_x264(fps), "-an", str(out)], check=True)
            if frame_count(out) == b - a and decode_errors(out) == 0:
                break
        else:
            raise WildDocError(f"segment {out.name} keeps failing to encode cleanly (flaky hardware?)")
    lst = sdir / "concat.txt"
    lst.write_text("".join(f"file '{s}'\n" for s in segs))
    master = project.master_path
    master.parent.mkdir(parents=True, exist_ok=True)
    tmp = master.with_suffix(".tmp.mp4")
    for attempt in range(3):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(mix), "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-shortest", "-movflags", "+faststart", str(tmp)], check=True)
        nf, errs = frame_count(tmp), decode_errors(tmp) + decode_errors(tmp, "a")
        if abs(nf - plan["durationInFrames"]) <= 1 and errs == 0:
            tmp.replace(master)
            _seal(master)
            break
    else:
        raise WildDocError(f"master failed verification (frames {nf}/{plan['durationInFrames']}, decode errors {errs})")
    sha = hashlib.sha256(master.read_bytes()).hexdigest()
    rep = {"master": str(master), "duration_s": round(ffprobe_duration(master), 2), "frames": frame_count(master), "sha256": sha,
           "size_mb": round(master.stat().st_size / 1e6, 1)}
    write_json(project.p("package", "master.json"), rep)
    project.log("assemble", **rep)
    return rep


def thumbnail(project: Project) -> dict:
    ensure_node()
    style = project.style()
    th = dict(style.get("thumbnail", {}))
    plan = read_json(project.plan_path, {})
    if not th.get("bg"):
        th["bg"] = next((s["img"] for s in plan.get("shots", []) if s["kind"] == "plate"), "")
    props = write_json(project.p("compose", "thumb.json"), th)
    out = project.p("package", "thumbnail.jpg")
    subprocess.run(["npx", "remotion", "still", "src/index.tsx", "Thumb", str(out), f"--props={props}", f"--public-dir={project.p('public')}",
                    "--image-format=jpeg", "--jpeg-quality=92", "--log=error"], cwd=REMOTION_DIR, check=True)
    return {"thumbnail": str(out), "bg": th["bg"]}
