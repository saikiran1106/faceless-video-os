"""Script + word-timed transcript -> timeline.json on the voice's own clock.

The script is the source of truth for TEXT (spelling, line ids, chapters); the audio is the source of truth for TIME.
Every script word gets a start/end from the transcript word it matches (difflib over normalised words), so shot anchors
are written in the script's spelling and keep resolving when the client sends a re-edited voice (iteration v7 lesson:
re-time, don't rebuild).

Script format (plain text, UTF-8):
    ## Hook                 <- chapter heading (optional; title after ##, slug used as id)
    First narration sentence.
    Second sentence. Third sentence on the same line is split into its own line.
    # a single '#' line is a comment
"""
from __future__ import annotations

import difflib
import re
import statistics
from pathlib import Path

from . import WildDocError
from .project import Project, norm, read_json, slugify, write_json

_SENT = re.compile(r"(?<=[.!?।॥])\s+")


def parse_script(text: str, split_sentences: bool = True) -> dict:
    chapters, lines = [], []
    seen: dict[str, int] = {}
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("##"):
            title = s.lstrip("#").strip()
            base = slugify(title)
            seen[base] = seen.get(base, 0) + 1
            name = base if seen[base] == 1 else f"{base}-{seen[base]}"
            chapters.append({"name": name, "title": title})
            continue
        if s.startswith("#"):
            continue
        if not chapters:
            chapters.append({"name": "main", "title": ""})
        parts = [p for p in (_SENT.split(s) if split_sentences else [s]) if p.strip()]
        for part in parts:
            lines.append({"i": len(lines) + 1, "chapter": chapters[-1]["name"], "text": part.strip()})
    if not lines:
        raise WildDocError("The script has no narration lines.")
    return {"chapters": chapters, "lines": lines}


def align_words(script_words: list[dict], heard: list[dict]) -> tuple[list[dict], dict]:
    """Give every script word a time. Returns (words, stats). Script word: {text, line}. Heard word: {text, start, end}."""
    a = [norm(w["text"]) for w in script_words]
    b = [norm(w["text"]) for w in heard]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    out = [dict(w, start=None, end=None, spoken=False) for w in script_words]
    matched, extra = 0, []
    for tag, a1, a2, b1, b2 in sm.get_opcodes():
        if tag == "equal" or (tag == "replace" and a2 - a1 == b2 - b1):
            for k in range(a2 - a1):
                h = heard[b1 + k]
                out[a1 + k].update(start=h["start"], end=h["end"], spoken=True, heard=h["text"])
            matched += (a2 - a1) if tag == "equal" else 0
        elif tag == "replace" and max(a2 - a1, b2 - b1) > 2 * min(a2 - a1, b2 - b1):
            # lopsided block (a dropped sentence next to a misheard word): fuzzy word-by-word alignment, so script words
            # with no counterpart stay unspoken instead of being smeared over one heard word
            pairs = _fuzzy_pairs(a[a1:a2], b[b1:b2])
            for i, j in pairs:
                h = heard[b1 + j]
                out[a1 + i].update(start=h["start"], end=h["end"], spoken=True, heard=h["text"])
            used = {j for _, j in pairs}
            extra.extend(heard[b1 + j]["text"] for j in range(b2 - b1) if j not in used)
        elif tag == "replace":
            # comparable spans (numbers read aloud, split compounds): spread the heard span over the script words by length
            t0, t1 = heard[b1]["start"], heard[b2 - 1]["end"]
            lens = [max(1, len(out[k]["text"])) for k in range(a1, a2)]
            tot, acc = sum(lens), 0
            for k, ln in zip(range(a1, a2), lens):
                s = t0 + (t1 - t0) * acc / tot
                acc += ln
                out[k].update(start=round(s, 3), end=round(t0 + (t1 - t0) * acc / tot, 3), spoken=True, heard=" ".join(h["text"] for h in heard[b1:b2]))
        elif tag == "insert":
            extra.extend(h["text"] for h in heard[b1:b2])
        # "delete": script words not spoken -> filled below
    # unspoken words: zero-length at the previous spoken word's end (or the next start)
    prev_end = 0.0
    for k, w in enumerate(out):
        if w["spoken"]:
            prev_end = w["end"]
            continue
        nxt = next((x["start"] for x in out[k + 1:] if x["spoken"]), prev_end)
        w["start"] = w["end"] = round(min(prev_end, nxt), 3)
    # keep the clock monotonic
    t = 0.0
    for w in out:
        w["start"] = max(w["start"], t)
        w["end"] = max(w["end"], w["start"])
        t = w["start"]
    stats = {"script_words": len(a), "heard_words": len(b), "exact_matches": matched,
             "match_ratio": round(matched / max(1, len(a)), 3), "spoken_ratio": round(sum(w["spoken"] for w in out) / max(1, len(a)), 3),
             "extra_spoken": extra[:60]}
    return out, stats


def _fuzzy_pairs(xs: list[str], ys: list[str], min_sim: float = 0.5) -> list[tuple[int, int]]:
    """Order-preserving best alignment of two word lists by spelling similarity (Needleman-Wunsch, gap = 0)."""
    n, m = len(xs), len(ys)
    if n * m > 250_000:  # pathological block: fall back to nothing matched
        return []
    sim = [[difflib.SequenceMatcher(None, x, y).ratio() for y in ys] for x in xs]
    S = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            take = S[i + 1][j + 1] + sim[i][j] if sim[i][j] >= min_sim else -1.0
            S[i][j] = max(take, S[i + 1][j], S[i][j + 1])
    pairs, i, j = [], 0, 0
    while i < n and j < m:
        if sim[i][j] >= min_sim and S[i][j] == S[i + 1][j + 1] + sim[i][j]:
            pairs.append((i, j))
            i, j = i + 1, j + 1
        elif S[i][j] == S[i + 1][j]:
            i += 1
        else:
            j += 1
    return pairs


def build_timeline(script: dict, transcript: dict, duration: float) -> dict:
    sw = [{"text": tok, "line": ln["i"]} for ln in script["lines"] for tok in ln["text"].split() if norm(tok)]
    words, stats = align_words(sw, transcript["words"])
    lines = []
    for ln in script["lines"]:
        ws = [w for w in words if w["line"] == ln["i"]]
        sp = [w for w in ws if w["spoken"]]
        if sp:
            lines.append(dict(ln, start=sp[0]["start"], end=sp[-1]["end"], spoken=True))
        else:  # dropped by the voice edit: keep the slot so line ids stay stable; the plan skips it
            t = ws[0]["start"] if ws else (lines[-1]["end"] if lines else 0.0)
            lines.append(dict(ln, start=t, end=t, spoken=False))
    chapters = []
    for ch in script["chapters"]:
        ls = [ln for ln in lines if ln["chapter"] == ch["name"] and ln["spoken"]]
        if ls:
            chapters.append({"name": ch["name"], "title": ch["title"], "start": ls[0]["start"], "line": ls[0]["i"]})
    if chapters:
        chapters[0]["start"] = 0.0
    return {"duration": round(duration, 3), "chapters": chapters, "lines": lines, "words": words, "stats": stats}


def run(project: Project, split_sentences: bool = True) -> dict:
    transcript = read_json(project.p("audio", "transcript.json"))
    if transcript is None:
        raise WildDocError("No transcript yet. Run `faceless wild-doc transcribe <project>`.")
    script = parse_script(project.script_path.read_text(encoding="utf-8"), split_sentences)
    from .project import ffprobe_duration

    tl = build_timeline(script, transcript, ffprobe_duration(project.voice_master))
    write_json(project.timeline_path, tl)
    # human-readable line index for directing (L<i> ids used by the shotlist)
    out = []
    for ch in tl["chapters"]:
        out.append(f"## {ch['name']}  ({ch['title']})  @ {ch['start']:.2f}s")
        for ln in (x for x in tl["lines"] if x["chapter"] == ch["name"]):
            mark = "" if ln["spoken"] else "  [NOT SPOKEN - skipped]"
            out.append(f"L{ln['i']}  {ln['start']:7.2f}-{ln['end']:7.2f}  {ln['text']}{mark}")
    Path(project.p("audio", "lines.txt")).write_text("\n".join(out) + "\n", encoding="utf-8")
    st = tl["stats"]
    warn = []
    if st["match_ratio"] < 0.6:
        warn.append("Fewer than 60% of script words matched the audio exactly: is this the right script for this recording, and the right language?")
    unspoken = [ln["i"] for ln in tl["lines"] if not ln["spoken"]]
    project.log("align", **st)
    return {"timeline": str(project.timeline_path), "lines": len(tl["lines"]), "chapters": [c["name"] for c in tl["chapters"]],
            "duration_s": tl["duration"], **{k: v for k, v in st.items() if k != "extra_spoken"},
            "unspoken_lines": unspoken, "extra_spoken_sample": st["extra_spoken"][:15], "warnings": warn,
            "lines_file": str(project.p("audio", "lines.txt"))}


def median_drift(a: list[dict], b: list[dict]) -> tuple[float, float]:
    """Word match ratio and median start drift (s) between two word lists (used by QA)."""
    sm = difflib.SequenceMatcher(None, [norm(w["text"]) for w in a], [norm(w["text"]) for w in b], autojunk=False)
    drift, n = [], 0
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            drift.append(abs(a[blk.a + k]["start"] - b[blk.b + k]["start"]))
            n += 1
    return round(n / max(1, len(a)), 3), round(statistics.median(drift), 3) if drift else 0.0
