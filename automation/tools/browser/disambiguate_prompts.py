"""Add an explicit identity clause to prompts where two characters get swapped.

Live defect: in the forest-riddle beats the model put the hunting KING with
Ratnavati (the mother, peacock-green sari) when the story requires him to marry
Sugunavati (the daughter, saffron-gold sari). The pairing inversion destroys the
riddle, whose whole point is that the daughter becomes her mother's
mother-in-law.

The visual bible already states both costumes, but stating them in a character
block is not enough - the model has to hold the mapping across a long prompt.
This restates the binding in one short sentence at the END of the prompt, next
to the action, which is where it actually gets applied.

Usage:
    python tools/browser/disambiguate_prompts.py <project> [--apply]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

CLAUSE = (
    "IDENTITY LOCK for this image: SUGUNAVATI is the DAUGHTER - about 24, "
    "taller, SAFFRON-GOLD sari with a crimson border, LARGER feet. RATNAVATI "
    "is the MOTHER - about 43, shorter, MUTED PEACOCK-GREEN sari with a copper "
    "border, a few silver strands in her hair, SMALLER feet. The OLDER bearded "
    "hunting KING is paired with SUGUNAVATI (gold sari). The YOUNGER hunting "
    "SON is paired with RATNAVATI (green sari). Do not swap these two women "
    "and do not swap who is paired with whom."
)

# Beats where both women, or a pairing, can be confused.
TARGET_BEATS = (["P20_B33", "P20_B35"]          # both women together in frame
                + [f"P20_B{i}" for i in range(41, 54)])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    proj = Path(a.project)
    qpath = proj / ".faceless" / "image_jobs.json"
    doc = json.loads(qpath.read_text())

    changed = []
    for j in doc["jobs"]:
        if j["beat_id"] not in TARGET_BEATS:
            continue
        if "IDENTITY LOCK" in j["prompt"]:
            continue
        new = j["prompt"].rstrip() + "\n\n" + CLAUSE + "\n"
        changed.append({"beat_id": j["beat_id"], "keyframe_id": j["keyframe_id"],
                        "old_sha": j["prompt_sha256"],
                        "new_sha": hashlib.sha256(new.encode()).hexdigest()})
        if a.apply:
            j["prompt"] = new
            j["prompt_sha256"] = changed[-1]["new_sha"]

    if a.apply:
        qpath.write_text(json.dumps(doc, ensure_ascii=False, indent=1))

    print(json.dumps({"applied": a.apply, "beats_changed": len(changed),
                      "beats": [c["beat_id"] for c in changed]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
