"""Shot list grammar (02-direction/shotlist.txt) - one row per narration line, every cut on a spoken word.

    L<i>: <spec> ; <anchor word>=<spec> ; <anchor>=<spec> ...     picture for line i (first spec starts at the line)
    O L<i> <anchor> <kind> <seconds> {json props}                 overlay graphic on a word (kw, threat, fact, ...)
    X L<i> <anchor> <sfx name> <gain dB>                          story sound on a word (wolf howl, roar, ...)
    # comment

spec:   S:<stock>[@offset_s]   real footage (02-direction/stock_picks.txt or 06-assets/clips/<name>.mp4)
        P:<plate>[:move]       AI still as 2.5D parallax (06-assets/plates/<plate>.png); moves: push pull panl panr rise drop dolly orbit hold crash
        R:<ref>                real photo evidence card (02-direction/refs.txt)
        M:<graphic>[#key]      full-screen graphic, props from 02-direction/graphics.json[<graphic>#key or <graphic>]
flags:  +t=<transition into the shot>  whip zoom glitch flash punch dip leak ice slide cut
        +fx=snow|embers|dust   +blur   +gray   +nolabel (R only)   +look=<look> (override the chapter grade)
anchor: a word of line i in the SCRIPT's spelling (punctuation ignored), or ^ for the line start. Repeated words resolve
        left to right after the previous anchor of the same row.
"""
from __future__ import annotations

import json
import re

from . import WildDocError

MOVES = ["push", "panr", "pull", "panl", "dolly", "rise", "orbit", "drop"]
TRANSITIONS = {"whip", "zoom", "glitch", "flash", "punch", "dip", "leak", "ice", "slide", "cut"}


def parse_spec(spec: str) -> dict:
    toks = spec.split()
    if not toks:
        raise WildDocError("empty shot spec")
    head, o = toks[0], {}
    for t in toks[1:]:
        if t.startswith("+t="):
            if t[3:] not in TRANSITIONS:
                raise WildDocError(f"unknown transition {t[3:]!r} in {spec!r}; use one of {sorted(TRANSITIONS)}")
            o["trans"] = t[3:]
        elif t.startswith("+fx="):
            o["fx"] = t[4:]
        elif t.startswith("+look="):
            o["look"] = t[6:]
        elif t in ("+blur", "+gray", "+nolabel"):
            o[t[1:]] = True
        else:
            raise WildDocError(f"unknown flag {t!r} in {spec!r}")
    if ":" not in head:
        raise WildDocError(f"bad spec {head!r}: expected S:, P:, R: or M:")
    kind, rest = head.split(":", 1)
    if kind == "S":
        name, _, off = rest.partition("@")
        o.update(kind="stock", name=name, off=float(off or 0))
    elif kind == "R":
        o.update(kind="ref", id=rest)
    elif kind == "P":
        pid, _, mv = rest.partition(":")
        o.update(kind="plate", id=pid, move=mv or "push")
    elif kind == "M":
        mg, _, key = rest.partition("#")
        o.update(kind="mg", mg=mg, key=f"{mg}#{key}" if key else mg)
    else:
        raise WildDocError(f"bad spec kind {kind!r} in {head!r}")
    return o


def parse(text: str) -> dict:
    rows: dict[int, list[str]] = {}
    overlays, story = [], []
    for n, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        try:
            if s.startswith("O "):
                parts = s.split(None, 5)
                overlays.append({"line": int(parts[1][1:]), "anchor": parts[2], "kind": parts[3], "sec": float(parts[4]),
                                 "props": json.loads(parts[5]) if len(parts) > 5 else {}, "row": n})
                continue
            if s.startswith("X "):
                parts = s.split()
                story.append({"line": int(parts[1][1:]), "anchor": parts[2], "name": parts[3],
                              "gain": float(parts[4]) if len(parts) > 4 else -12.0, "row": n})
                continue
            m = re.match(r"L(\d+):\s*(.*)", s)
            if not m:
                raise WildDocError("expected 'L<i>: ...', 'O L<i> ...' or 'X L<i> ...'")
            items = [x.strip() for x in m.group(2).split(";") if x.strip()]
            for j, it in enumerate(items):
                parse_spec(it if j == 0 else it.partition("=")[2])
            rows[int(m.group(1))] = items
        except (ValueError, IndexError, json.JSONDecodeError, WildDocError) as exc:
            raise WildDocError(f"shotlist.txt row {n}: {exc}\n  {s}") from exc
    return {"rows": rows, "overlays": overlays, "story": story}


def draft(timeline: dict, style: dict, plates_per_s: float = 6.0) -> tuple[str, dict]:
    """A complete first cut from AI plates alone (so script + audio always renders end to end).

    One plate per line, a second plate on a mid-line word for lines longer than `plates_per_s`. The plan builder's
    auto jump-cuts keep every picture under the max shot length. The agent then upgrades rows to real stock (S:),
    evidence (R:), graphics (M:, O) and story sounds (X) - see the wild-doc skill."""
    prefix = style.get("plate_prompt_prefix", "")
    words_by_line: dict[int, list[dict]] = {}
    for w in timeline["words"]:
        words_by_line.setdefault(w["line"], []).append(w)
    out = ["# wild-doc shot list - DRAFT (plates only). Grammar: see the header of faceless/wilddoc/shotlist.py",
           "# Upgrade rows: S:<stock>[@s]  R:<ref>  M:<graphic>  ;  <word>=<spec>  ;  flags +t= +fx= +blur +gray +look=",
           "# Overlays:  O L<i> <word> kw 1.2 {\"text\":\"ENGLISH TEXT\",\"tone\":\"red\",\"pos\":\"c\"}",
           "# Story SFX: X L<i> <word> <sfx_name> -12      (define sfx_name in style.json story_sfx)", ""]
    plates: dict[str, dict] = {}
    k = 0
    chapter = None
    for ln in timeline["lines"]:
        if ln["chapter"] != chapter:
            chapter = ln["chapter"]
            out += ["", f"## {chapter}"]
        dur = ln["end"] - ln["start"]
        out.append(f"# L{ln['i']} ({dur:.1f}s) {ln['text']}")
        if not ln.get("spoken", True):
            out.append(f"# L{ln['i']} not spoken in this voice - no row")
            continue
        pid = f"L{ln['i']:03d}"
        first_in_chapter = ln is next(x for x in timeline["lines"] if x["chapter"] == chapter)
        trans = "dip" if first_in_chapter and ln["i"] != 1 else ("whip", "zoom", "glitch", "cut")[k % 4]
        row = f"L{ln['i']}: P:{pid}:{MOVES[k % len(MOVES)]}" + ("" if ln["i"] == 1 else f" +t={trans}")
        plates[pid] = {"line": ln["i"], "prompt": prefix + ln["text"]}
        k += 1
        ws = [w for w in words_by_line.get(ln["i"], []) if w.get("spoken", True)]
        if dur > plates_per_s and len(ws) > 4:
            mid = ws[len(ws) // 2]
            pid2 = pid + "b"
            plates[pid2] = {"line": ln["i"], "prompt": prefix + "a different angle and subject from the same moment: " + ln["text"]}
            row += f" ; {re.sub(r'[;=]', '', mid['text'])}=P:{pid2}:{MOVES[k % len(MOVES)]} +t={('zoom', 'whip', 'glitch')[k % 3]}"
            k += 1
        out.append(row)
    return "\n".join(out) + "\n", plates
