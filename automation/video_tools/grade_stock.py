"""Bake chapter grade + vignette + grain (+blur/gray) into per-shot stock segments (1080p24, exact frame count)."""
import json, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; PUB = ROOT / "08-compose/remotion/public"
LOOK = {
 "dusk":  "eq=contrast=1.08:saturation=0.85:brightness=-0.03,colorbalance=rs=-0.04:bs=0.10:rh=0.10:bh=-0.08",
 "ice":   "eq=contrast=1.10:saturation=0.62:brightness=-0.04,colorbalance=rs=-0.08:bs=0.12:rm=-0.05:bm=0.08:rh=-0.03:bh=0.06",
 "night": "eq=contrast=1.18:saturation=0.38:brightness=-0.20:gamma=0.85,colorbalance=rs=-0.15:gs=-0.05:bs=0.20:rm=-0.12:bm=0.15:rh=-0.10:bh=0.05",
 "fire":  "eq=contrast=1.12:saturation=1.05:brightness=-0.03,colorbalance=rs=0.05:bs=0.10:rm=0.08:bm=-0.05:rh=0.12:bh=-0.12",
 "dawn":  "eq=contrast=1.05:saturation=0.95,colorbalance=rs=0.04:rm=0.06:bm=-0.06:rh=0.10:gh=0.03:bh=-0.10",
}
jobs = json.load(open(ROOT / "08-compose/stock_jobs.json"))
(PUB / "shots").mkdir(exist_ok=True)
def run(j):
    out = PUB / j["out"]
    if out.exists(): return "skip"
    secs = j["frames"] / 24 * j["rate"] + 0.3
    vf = [f"setpts=PTS/{j['rate']}" if j["rate"] != 1 else None, LOOK[j["look"]],
          "gblur=sigma=7" if j["blur"] else None, "hue=s=0.15" if j["gray"] else None,
          "vignette=angle=PI/4.2", "noise=alls=7:allf=t", "fps=24", "format=yuv420p"]
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{j['off']:.3f}", "-t", f"{secs:.3f}", "-i", str(ROOT / "08-compose/stock_proxy" / Path(j["src"]).name),
           "-vf", ",".join(x for x in vf if x), "-frames:v", str(j["frames"] + 2), "-an",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-g", "12", str(out)]
    subprocess.run(cmd, check=True); return "ok"
with ThreadPoolExecutor(3) as ex: r = list(ex.map(run, jobs))
print({k: r.count(k) for k in set(r)}, len(jobs))
