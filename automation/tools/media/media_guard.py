#!/usr/bin/env python3
"""media_guard: catch this laptop's silent media corruption before it reaches a deliverable.

Background (diagnosed 2026-11-05): during long renders the CPU sits at ~90 C and throttles; bits flip in RAM
(a node binary crashed at one fixed instruction while its on-disk copy was intact; a Remotion chunk was written
with a corrupt macroblock; random Chrome segfaults). The Optane H10's PCIe link also logs correctable RxErr.
So: verify every media file right after it is written, fingerprint it, and re-verify before assembly/upload.

usage:
  media_guard.py seal FILE...      full decode check + frame count; on success write FILE.sha256 (exit 1 if bad)
  media_guard.py check FILE...     re-hash vs FILE.sha256 + decode check (exit 1 if changed or bad)
  media_guard.py retry N -- CMD... run CMD (which must write the file given by --out FILE) up to N times until seal passes
"""
import hashlib, json, os, subprocess, sys


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()


def decode_errors(path):
    """Full decode of every stream; returns (error_lines, video_frames)."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-map", "0", "-f", "null", "-"], capture_output=True, text=True)
    errs = [l for l in r.stderr.splitlines() if l.strip()]
    n = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries",
                        "stream=nb_read_packets", "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip().strip(",")
    return errs + ([f"ffmpeg exit {r.returncode}"] if r.returncode else []), int(n or 0)


def seal(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        print(f"BAD   {path}: missing or empty"); return False
    errs, n = decode_errors(path)
    if errs:
        print(f"BAD   {path}: {len(errs)} decode errors, first: {errs[0][:160]}"); return False
    rec = {"sha256": sha256(path), "bytes": os.path.getsize(path), "frames": n}
    open(path + ".sha256", "w").write(json.dumps(rec))
    print(f"SEAL  {path}: {n} frames, clean"); return True


def check(path):
    side = path + ".sha256"
    if not os.path.exists(side):
        print(f"UNSEALED {path}"); return seal(path)
    rec = json.load(open(side))
    if sha256(path) != rec["sha256"]:
        print(f"CHANGED {path}: bytes differ from sealed fingerprint (corrupted after writing)"); return False
    errs, n = decode_errors(path)
    if errs or n != rec["frames"]:
        print(f"BAD   {path}: {len(errs)} decode errors, frames {n}/{rec['frames']}"); return False
    print(f"OK    {path}"); return True


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    cmd, rest = argv[1], argv[2:]
    if cmd == "seal":
        sys.exit(0 if all([seal(p) for p in rest]) else 1)
    if cmd == "check":
        sys.exit(0 if all([check(p) for p in rest]) else 1)
    if cmd == "retry":
        n = int(rest[0]); run = rest[rest.index("--") + 1:]
        out = run[run.index("--out") + 1] if "--out" in run else run[run.index("-o") + 1]
        run = [a for i, a in enumerate(run) if not (a == "--out" or (i and run[i - 1] == "--out"))]
        for attempt in range(1, n + 1):
            rc = subprocess.run(run).returncode
            if rc == 0 and seal(out):
                print(f"retry: sealed on attempt {attempt}"); sys.exit(0)
            print(f"retry: attempt {attempt} failed (rc={rc}); re-running")
        sys.exit(f"retry: {out} failed {n} attempts")
    sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
