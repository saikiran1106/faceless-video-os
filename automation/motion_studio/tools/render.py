#!/usr/bin/env python3
"""Render built variants, QA each export, and write the delivery manifest.

  python3 tools/render.py campaigns/<id> [--only seek-t_A_9x16_A,...] [--workers 2]

Run tools/build.py first. Skips a variant whose export is newer than its index.html.
"""
import argparse, hashlib, json, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HF = ["npx", "-y", "hyperframes@0.8.210"]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("campaign_dir")
    ap.add_argument("--only")
    ap.add_argument("--workers", default="2")  # 4 ran out of memory on the laptop
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    cdir = os.path.abspath(a.campaign_dir)
    man = json.load(open(os.path.join(cdir, "build", "build_manifest.json")))
    only = set(a.only.split(",")) if a.only else None
    os.makedirs(os.path.join(cdir, "exports"), exist_ok=True)
    out = dict(campaign=man["campaign"], campaign_sha=man["campaign_sha"], template=man["template"],
               settings=dict(fps=man["fps"], quality="delivery", motion_blur="on (hero off)", hyperframes="0.8.210"), exports=[])
    for v in man["variants"]:
        if only and v["id"] not in only:
            continue
        src = os.path.join(ROOT, v["dir"])
        mp4 = os.path.join(cdir, "exports", v["id"] + ".mp4")
        fresh = os.path.exists(mp4) and os.path.getmtime(mp4) > os.path.getmtime(os.path.join(src, "index.html"))
        if not fresh or a.force:
            t0 = time.time()
            r = subprocess.run(HF + ["render", "--output", mp4, "--workers", a.workers, "--quality", "delivery", "--quiet"],
                               cwd=src, capture_output=True, text=True)
            ok = r.returncode == 0 and os.path.exists(mp4) and os.path.getmtime(mp4) >= t0
            print(f"{'rendered' if ok else 'FAILED  '} {v['id']} in {time.time() - t0:.0f}s", flush=True)
            if not ok:
                print(r.stdout[-1500:], r.stderr[-1500:])
                continue
        q = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "qa.py"), mp4], capture_output=True, text=True).stdout
        bad = [l for l in q.splitlines() if l.startswith("BAD")]
        out["exports"].append(dict(id=v["id"], hook=v["hook"], format=v["format"], cta=v["cta"], dur=v["dur"],
                                   file=os.path.relpath(mp4, ROOT), bytes=os.path.getsize(mp4), sha256=sha(mp4),
                                   qa="pass" if not bad else bad))
        if bad:
            print("  QA:", "; ".join(bad), flush=True)
    path = os.path.join(cdir, "exports", "delivery_manifest.json")
    if os.path.exists(path) and only:  # merge partial runs
        old = {e["id"]: e for e in json.load(open(path)).get("exports", [])}
        old.update({e["id"]: e for e in out["exports"]})
        out["exports"] = sorted(old.values(), key=lambda e: e["id"])
    json.dump(out, open(path, "w"), indent=1)
    print("wrote", os.path.relpath(path, ROOT))


if __name__ == "__main__":
    main()
