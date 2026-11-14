"""Final master, robust to this laptop's random bitstream corruption: encode each chapter (chunk + its patches) separately,
decode-verify it, re-encode on any error, then stream-copy concat the verified segments and mux the mastered mix."""
import json, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE / "remotion/renders/chunks"; PT = HERE / "remotion/renders/patches"; SEG = HERE / "segments"; SEG.mkdir(exist_ok=True)
plan = json.load(open(HERE / "remotion/src/plan.json"))
ch = plan["chapters"]; bounds = [0] + [c["from"] for c in ch[1:]] + [plan["durationInFrames"]]
patches = sorted((int(p.stem[1:].split("_")[0]), int(p.stem.split("_")[1]), p) for p in PT.glob("p*_*.mp4") if "tmp" not in p.name)
X264 = ["-c:v", "libx264", "-preset", "medium", "-crf", "17", "-maxrate", "22M", "-bufsize", "44M", "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-r", "24", "-x264-params", "keyint=48:min-keyint=24"]

def errors(f):
    return len(subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-map", "0:v", "-f", "null", "-"], capture_output=True, text=True).stderr.strip().splitlines())

import sys
REDO = {a for a in sys.argv[1:] if a.endswith(".mp4") and a != "--out"}
segs = []
for i, c in enumerate(ch):
    a, b = bounds[i], bounds[i + 1]
    out = SEG / f"{i}_{c['name']}.mp4"
    ins = ["-i", str(C / f"{c['name']}.mp4")]; fc = ""; last = "0:v"; k = 1
    for pa, pb, p in patches:
        lo, hi = max(pa, a), min(pb, b - 1)
        if lo > hi: continue
        # patch frame pa sits at local frame (pa - a); overlay only inside this chapter
        ins += ["-i", str(p)]; fc += f"[{k}:v]setpts=PTS+({pa}-{a})/24/TB[q{k}];[{last}][q{k}]overlay=enable='between(n,{lo - a},{hi - a})'[v{k}];"
        last = f"v{k}"; k += 1
    # v4: baked RGB-split + static on glitch cuts (2 frames before to 4 after each glitch cut), local frame numbers
    gl = [(max(a, sh["from"] - 2) - a, min(b - 1, sh["from"] + 4) - a) for sh in plan["shots"] if sh.get("trans") == "glitch" and a <= sh["from"] < b]
    if gl:
        en = "+".join(f"between(n,{x},{y})" for x, y in gl)
        fc += f"[{last}]rgbashift=rh=-16:bh=16:gv=4:edge=smear:enable='{en}',noise=alls=28:allf=t:enable='{en}'[gx];"; last = "gx"
    if out.exists() and out.name not in REDO:
        n0 = int(subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v", "-show_entries", "stream=nb_read_packets",
                                 "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip().strip(",") or 0)
        if n0 == b - a and errors(out) == 0: print(f"{c['name']}: reuse verified segment", flush=True); segs.append(out); continue
    for attempt in range(4):
        cmd = ["ffmpeg", "-v", "error", "-y", *ins]
        cmd += (["-filter_complex", fc.rstrip(";"), "-map", f"[{last}]"] if fc else ["-map", "0:v"])
        cmd += [*X264, "-frames:v", str(b - a), "-an", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0: print(r.stderr[-500:]); continue
        in_err = sum(1 for l in r.stderr.splitlines() if "error while decoding" in l or "corrupt" in l)
        n = int(subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v", "-show_entries", "stream=nb_read_packets",
                                "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip().strip(","))
        e = errors(out)
        print(f"{c['name']}: frames {n}/{b - a} decode_errors {e} input_errors {in_err} (attempt {attempt + 1})", flush=True)
        if e == 0 and n == b - a and in_err == 0: break
    else:
        raise SystemExit(f"segment {c['name']} failed verification")
    segs.append(out)

(HERE / "segments.txt").write_text("".join(f"file '{s}'\n" for s in segs))
pic = HERE / "picture_verified.mp4"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(HERE / "segments.txt"), "-c", "copy", str(pic)], check=True)
final = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else HERE.parent / "final.mp4"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(pic), "-i", str(HERE / "mix_stereo.wav"), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-shortest", "-movflags", "+faststart", str(final)], check=True)
print("final decode errors:", errors(final))
print(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_name,width,height,r_frame_rate", "-of", "compact", str(final)],
                     capture_output=True, text=True).stdout)
