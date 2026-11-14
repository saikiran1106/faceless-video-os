"""Bind staged images to beats by what they depict.

ChatGPT returns a batch's images in an arbitrary order - verified live, a
10-item batch came back with item 2's picture in slot 1 and item 1's in slot 5.
Position is therefore not identity, and filing by position is exactly the
mistake that put 86% of EP02's shots on the wrong beat.

So binding is an explicit, recorded decision: a reviewer looks at the batch
contact sheet and states which slot serves which beat. This tool applies that
decision, copies each image to its keyframe_id path, and records the evidence.

Usage:
    python tools/browser/bind_keyframes.py <project> --batch 1 \
        --map P20_B01=5 P20_B02=1 ...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--batch", type=int, required=True)
    ap.add_argument("--map", nargs="+", required=True,
                    help="BEAT_ID=SLOT pairs, e.g. P20_B01=5")
    ap.add_argument("--note", default="bound by contact-sheet review")
    a = ap.parse_args()

    proj = Path(a.project)
    staging = proj / "06-keyframes" / "_staging"
    index = json.loads((staging / "staged_index.json").read_text())
    jobs = json.loads((proj / ".faceless" / "image_jobs.json").read_text())["jobs"]
    by_beat = {j["beat_id"]: j for j in jobs}

    slots = {r["slot"]: r for r in index["images"] if r["batch"] == a.batch}
    pairs = []
    for item in a.map:
        beat, _, slot = item.partition("=")
        pairs.append((beat, int(slot)))

    seen_slots = [s for _, s in pairs]
    if len(set(seen_slots)) != len(seen_slots):
        raise SystemExit("a slot was bound to more than one beat")

    bindings = []
    for beat, slot in pairs:
        if slot not in slots:
            raise SystemExit(f"batch {a.batch} has no slot {slot}")
        if beat not in by_beat:
            raise SystemExit(f"unknown beat {beat}")
        job = by_beat[beat]
        src = Path(slots[slot]["path"])
        dst = proj / job["output_path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        rec = {"beat_id": beat, "keyframe_id": job["keyframe_id"],
               "batch": a.batch, "slot": slot,
               "staged_path": str(src), "output_path": str(dst),
               "sha256": sha256(dst), "note": a.note,
               "bound_at": datetime.now(timezone.utc).isoformat()}
        bindings.append(rec)
        for r in index["images"]:
            if r["batch"] == a.batch and r["slot"] == slot:
                r["bound_to"] = beat

    (staging / "staged_index.json").write_text(json.dumps(index, indent=1))

    ledger = proj / "06-keyframes" / "bindings.json"
    doc = json.loads(ledger.read_text()) if ledger.exists() else {"bindings": []}
    # Key by beat, never by batch: batch numbers restart on every run, so a
    # second run's "batch 1" silently deleted the first run's batch 1 rows and
    # the ledger lost 30 verified bindings while the images stayed correct.
    replaced = {b["beat_id"] for b in bindings}
    doc["bindings"] = [b for b in doc["bindings"]
                       if b["beat_id"] not in replaced] + bindings
    doc["bindings"].sort(key=lambda b: b["beat_id"])
    ledger.write_text(json.dumps(doc, indent=1))

    print(json.dumps({"batch": a.batch, "bound": len(bindings),
                      "beats": [b["beat_id"] for b in bindings],
                      "ledger": str(ledger)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
