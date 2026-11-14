#!/usr/bin/env python3
"""Media inputs live in R2, not git. This keeps a checksum lock in git and syncs the bytes.

  python3 tools/assets.py status            # what is present, missing or changed locally
  python3 tools/assets.py lock              # (re)write assets.lock.json from the files on disk
  python3 tools/assets.py push              # upload every locked file that R2 does not have yet
  python3 tools/assets.py pull [--only campaigns/genie-4]   # download missing/changed files, verify sha256

Inputs are what a build needs and cannot regenerate: engine SFX, a campaign's footage/, and its audio/ media
(voice takes, music beds). Renders, QA sheets and build/ are outputs and are never locked.
R2 keys: motion-studio/<path relative to motion-studio/>. Credentials come from the repo .env via
tools/storage/r2.py and are never printed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
LOCK = ROOT / "assets.lock.json"
PREFIX = "motion-studio/"
MEDIA = {".mp3", ".wav", ".m4a", ".aac", ".mp4", ".mov", ".webm", ".png", ".jpg", ".jpeg", ".webp"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def input_files() -> list[Path]:
    """Every media input on disk: engine/sfx/*, campaigns/*/footage/**, campaigns/*/audio/* (media only)."""
    found = [p for p in (ROOT / "engine" / "sfx").glob("*") if p.suffix.lower() in MEDIA]
    for camp in sorted((ROOT / "campaigns").glob("*/")):
        for sub in ("footage", "audio", "music"):
            found += [p for p in (camp / sub).rglob("*") if p.is_file() and p.suffix.lower() in MEDIA]
    return sorted(found)


def load_lock() -> dict:
    return json.loads(LOCK.read_text()) if LOCK.exists() else {"prefix": PREFIX, "files": {}}


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def r2():
    sys.path.insert(0, str(REPO / "tools" / "storage"))
    import r2 as store  # noqa: PLC0415  repo helper: env from .env, byte-exact transfers
    return store


def cmd_lock(_a) -> int:
    lock = load_lock()
    files = {}
    for p in input_files():
        files[rel(p)] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    dropped = sorted(set(lock["files"]) - set(files))
    lock["files"] = files
    LOCK.write_text(json.dumps(lock, indent=1, sort_keys=True) + "\n")
    print(f"locked {len(files)} files ({sum(f['bytes'] for f in files.values()) / 1e6:.1f} MB) -> {rel(LOCK)}")
    for d in dropped:
        print(f"  no longer on disk, removed from lock: {d}")
    return 0


def state(path: str, meta: dict) -> str:
    p = ROOT / path
    if not p.exists():
        return "missing"
    if p.stat().st_size != meta["bytes"] or sha256(p) != meta["sha256"]:
        return "changed"
    return "ok"


def cmd_status(a) -> int:
    lock = load_lock()["files"]
    counts: dict[str, int] = {}
    for path, meta in sorted(lock.items()):
        if a.only and not path.startswith(a.only):
            continue
        s = state(path, meta)
        counts[s] = counts.get(s, 0) + 1
        if s != "ok":
            print(f"{s:8} {path}")
    unlocked = [rel(p) for p in input_files() if rel(p) not in lock and (not a.only or rel(p).startswith(a.only))]
    for u in unlocked:
        print(f"unlocked {u}   (run: tools/assets.py lock)")
    print(", ".join(f"{v} {k}" for k, v in sorted(counts.items())) or "lock is empty", f"| {len(unlocked)} unlocked")
    return 1 if counts.get("missing") or counts.get("changed") or unlocked else 0


def cmd_push(a) -> int:
    store = r2()
    lock = load_lock()
    pushed = 0
    for path, meta in sorted(lock["files"].items()):
        if a.only and not path.startswith(a.only):
            continue
        if state(path, meta) != "ok":
            print(f"skip {path}: local file is {state(path, meta)}; run lock first")
            continue
        key = lock.get("prefix", PREFIX) + path
        if store.object_exists(key) and not a.force:
            continue
        res = store.put_file(ROOT / path, key)
        assert res["sha256"] == meta["sha256"], f"hash drift while uploading {path}"
        pushed += 1
        print(f"pushed {path}")
    print(f"{pushed} uploaded, {len(lock['files']) - pushed} already in R2 or skipped")
    return 0


def cmd_pull(a) -> int:
    store = r2()
    lock = load_lock()
    fails = 0
    for path, meta in sorted(lock["files"].items()):
        if a.only and not path.startswith(a.only):
            continue
        if state(path, meta) == "ok":
            continue
        dst = ROOT / path
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".part")
        store.client().download_file(store.bucket(), lock.get("prefix", PREFIX) + path, str(tmp))
        if sha256(tmp) != meta["sha256"]:
            tmp.unlink()
            print(f"BAD  {path}: downloaded bytes do not match the lock")
            fails += 1
            continue
        os.replace(tmp, dst)
        print(f"pulled {path}")
    return 1 if fails else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("status", "lock", "push", "pull"):
        p = sub.add_parser(name)
        p.add_argument("--only", help="path prefix, e.g. engine/sfx or campaigns/genie-4")
        if name == "push":
            p.add_argument("--force", action="store_true", help="re-upload even if the key exists")
    a = ap.parse_args(argv)
    return {"status": cmd_status, "lock": cmd_lock, "push": cmd_push, "pull": cmd_pull}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
