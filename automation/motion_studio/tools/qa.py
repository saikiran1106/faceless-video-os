#!/usr/bin/env python3
"""Inspect a rendered export before anyone calls it done.

  python3 tools/qa.py campaigns/<id>/exports/<variant>.mp4

Writes next to the export, in qa/<variant>/:
  contact.jpg   one frame per second
  seams.jpg     5 frames around every scene boundary (a broken transition hides between contact frames)
  phone.jpg     the contact sheet at phone size (360 px wide frames)
  REVIEW.md     timestamps inspected, measured numbers, and blanks for issues, fixes and human approval
"""
import json, os, re, subprocess, sys
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def frame(video, t, w):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", "-vf", f"scale={w}:-2",
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    from io import BytesIO
    return Image.open(BytesIO(raw)).convert("RGB")


def sheet(video, times, w, cols, path, label=True):
    ims = [frame(video, t, w) for t in times]
    fw, fh = ims[0].size
    rows = (len(ims) + cols - 1) // cols
    s = Image.new("RGB", (cols * fw, rows * (fh + 22)), "#222")
    d = ImageDraw.Draw(s)
    for i, (t, im) in enumerate(zip(times, ims)):
        x, y = (i % cols) * fw, (i // cols) * (fh + 22)
        s.paste(im, (x, y + 22))
        if label:
            d.text((x + 5, y + 4), f"{t:.2f}s", fill="white")
    s.save(path, quality=86)


def main():
    video = os.path.abspath(sys.argv[1])
    vid = os.path.splitext(os.path.basename(video))[0]
    camp_dir = os.path.dirname(os.path.dirname(video))
    out = os.path.join(camp_dir, "qa", vid)
    os.makedirs(out, exist_ok=True)
    man = json.load(open(os.path.join(camp_dir, "build", "build_manifest.json")))
    v = next((x for x in man["variants"] if x["id"] == vid), None)
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate",
                                       "-of", "json", video], capture_output=True, text=True).stdout)
    dur = float(probe["format"]["duration"])
    vs = next(s for s in probe["streams"] if s["codec_type"] == "video")
    has_audio = any(s["codec_type"] == "audio" for s in probe["streams"])
    lufs = peak = None
    if has_audio:
        log = subprocess.run(["ffmpeg", "-nostats", "-i", video, "-af", "ebur128=peak=true", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
        m = re.findall(r"I:\s+(-?[\d.]+) LUFS", log)
        p = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", log)
        lufs, peak = (float(m[-1]) if m else None), (float(p[-1]) if p else None)

    tall = vs["height"] > vs["width"]
    cw = 216 if tall else 384
    secs = [i + 0.5 for i in range(int(dur))]
    sheet(video, secs, cw, 8 if tall else 5, os.path.join(out, "contact.jpg"))
    sheet(video, secs, 120 if tall else 200, 11 if tall else 7, os.path.join(out, "phone.jpg"), label=False)
    seam_t = []
    if v:
        for s in v["scenes"][1:]:
            b = s["start"]
            seam_t += [b - 0.4, b - 0.2, b, b + 0.2, b + 0.4]
        sheet(video, [max(0, t) for t in seam_t], 160 if tall else 288, 5, os.path.join(out, "seams.jpg"))

    expect = man and v and v["dur"]
    checks = [
        ("duration", f"{dur:.2f}s", expect is None or abs(dur - expect) < 0.1),
        ("size", f'{vs["width"]}x{vs["height"]}', True),
        ("fps", vs["r_frame_rate"], vs["r_frame_rate"] in ("30/1", "60/1")),
        ("audio", "yes" if has_audio else "none", has_audio),
        ("loudness", f"{lufs} LUFS" if lufs is not None else "n/a", lufs is not None and -18 <= lufs <= -12),
        ("true peak", f"{peak} dBFS" if peak is not None else "n/a", peak is not None and peak <= -1.0),
    ]
    md = [f"# Review: {vid}", "", f"Export: `{os.path.relpath(video, ROOT)}`", "",
          "## Measured", "", "| check | value | ok |", "|---|---|---|"]
    md += [f"| {a} | {b} | {'yes' if c else '**NO**'} |" for a, b, c in checks]
    md += ["", "## Inspected", "", f"- contact.jpg: {', '.join(f'{t:.1f}' for t in secs)} s",
           f"- seams.jpg: {', '.join(f'{t:.2f}' for t in seam_t)} s", "- phone.jpg: every second at phone size", "",
           "## Issues found", "", "- ", "", "## Fixes applied", "", "- ", "", "## Remaining concerns", "",
           "- Audio was measured, not listened to.", "", "## Human approval", "", "- [ ] Approved for delivery by: ____"]
    open(os.path.join(out, "REVIEW.md"), "w").write("\n".join(md) + "\n")
    for a, b, c in checks:
        print(f"{'ok ' if c else 'BAD'} {a}: {b}")
    print("wrote", os.path.relpath(out, ROOT))


if __name__ == "__main__":
    main()
