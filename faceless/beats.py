"""Measured word timings -> a continuous beat timeline.

A beat is one narration slot that gets exactly one keyframe. Beats cover the
audio end to end with no gaps or overlaps, so the edit can never drift from the
voice. Boundaries follow the speech: sentence ends first, then clause pauses,
then word count - never an arbitrary fixed interval.
"""
from __future__ import annotations

import re
from typing import Any

SENTENCE_END = re.compile(r"[.!?।॥。！？]['\"”’)]*$")
CLAUSE_END = re.compile(r"[,;:—–\-،、]['\"”’)]*$")


def _sentences(words: list[dict[str, Any]], pause_s: float = 0.7) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for index, word in enumerate(words):
        current.append(word)
        nxt = words[index + 1] if index + 1 < len(words) else None
        long_pause = nxt is not None and nxt["start"] - word["end"] >= pause_s
        if SENTENCE_END.search(word["text"]) or long_pause or nxt is None:
            groups.append(current)
            current = []
    return groups


def _split_long(group: list[dict[str, Any]], target_s: float, max_s: float) -> list[list[dict[str, Any]]]:
    """Split one sentence that runs longer than max_s at the best clause/pause point."""
    if group[-1]["end"] - group[0]["start"] <= max_s or len(group) < 2:
        return [group]
    start = group[0]["start"]
    min_part = max(0.8, target_s * 0.4)
    best_index, best_score = None, float("inf")
    for i in range(1, len(group)):
        left = group[i - 1]["end"] - start
        if left < min_part or group[-1]["end"] - group[i]["start"] < min_part:
            continue
        score = abs(left - target_s)
        if CLAUSE_END.search(group[i - 1]["text"]):
            score -= target_s * 0.6
        score -= min(group[i]["start"] - group[i - 1]["end"], 0.5) * 2
        if score < best_score:
            best_index, best_score = i, score
    if best_index is None:
        best_index = len(group) // 2
    return _split_long(group[:best_index], target_s, max_s) + _split_long(group[best_index:], target_s, max_s)


def build_beats(words: list[dict[str, Any]], audio_duration_s: float, pacing: dict[str, float]) -> list[dict[str, Any]]:
    if not words:
        raise ValueError("Transcript has no words; cannot build beats")
    min_s, target_s, max_s = pacing["min_s"], pacing["target_s"], pacing["max_s"]
    groups: list[list[dict[str, Any]]] = []
    for sentence in _sentences(words):
        groups.extend(_split_long(sentence, target_s, max_s))

    # Merge beats that would flash by too fast into whichever neighbour gives the
    # shorter combined beat, as long as that stays under the longest allowed hold.
    max_hold = pacing.get("max_hold_s", max_s * 1.25)
    merged: list[list[dict[str, Any]]] = [list(g) for g in groups]

    def screen_end(k: int) -> float:
        """A beat stays on screen until the next beat's first word (or the audio ends)."""
        return merged[k + 1][0]["start"] if k + 1 < len(merged) else max(audio_duration_s, merged[k][-1]["end"])

    changed = True
    while changed and len(merged) > 1:
        changed = False
        for i, group in enumerate(merged):
            if screen_end(i) - group[0]["start"] >= min_s:
                continue
            options = []
            if i > 0:
                options.append((screen_end(i) - merged[i - 1][0]["start"], i - 1))
            if i + 1 < len(merged):
                options.append((screen_end(i + 1) - group[0]["start"], i + 1))
            combined, j = min(options)
            if combined > max_hold:
                continue
            lo, hi = sorted((i, j))
            merged[lo : hi + 1] = [merged[lo] + merged[hi]]
            changed = True
            break

    beats: list[dict[str, Any]] = []
    for index, group in enumerate(merged):
        start = 0.0 if index == 0 else beats[-1]["end_s"]
        if index + 1 < len(merged):
            nxt = merged[index + 1][0]["start"]
            end = max(group[-1]["end"], nxt - 0.05) if nxt - group[-1]["end"] > 0.1 else nxt
            end = max(end, start + 0.1)
        else:
            end = max(audio_duration_s, group[-1]["end"])
        number = index + 1
        beats.append({
            "beat_id": f"B{number:03d}",
            "keyframe_id": f"KF{number:03d}",
            "start_s": round(start, 3),
            "end_s": round(end, 3),
            "text": " ".join(w["text"] for w in group),
            "visual_objective": "",
            "shot_scale": "",
            "camera": {"kind": "push_in", "intensity": 0.5},
            "character_ids": [],
            "location_id": "",
            "transition": "crossfade",
        })
    return beats


DIRECTION_FIELDS = ("visual_objective", "shot_scale", "camera", "character_ids", "location_id", "mood", "overlay", "transition", "long_hold_reason")


def carry_directions(new_beats: list[dict[str, Any]], old_beats: list[dict[str, Any]]) -> dict[str, Any]:
    """Re-attach directions (and the beat/keyframe ids they are bound to) to re-timed beats.

    A new beat inherits from an old beat only when their spoken text is identical, so a
    keyframe stays on exactly the line it was drawn for. Changed lines get fresh ids and
    empty directions - they need new keyframes, which is the point.
    """
    from .captions import normalize

    def key(text: str) -> str:
        return " ".join(t for t in (normalize(w) for w in text.split()) if t)

    pool: dict[str, list[dict[str, Any]]] = {}
    for old in old_beats:
        pool.setdefault(key(old["text"]), []).append(old)
    used_numbers = [int(re.sub(r"\D", "", b["beat_id"]) or 0) for b in old_beats]
    next_number = max(used_numbers, default=0) + 1
    kept, fresh = [], []
    for beat in new_beats:
        match = pool.get(key(beat["text"]))
        if match:
            old = match.pop(0)
            beat["beat_id"], beat["keyframe_id"] = old["beat_id"], old["keyframe_id"]
            for field in DIRECTION_FIELDS:
                if field in old:
                    beat[field] = old[field]
            kept.append(beat["beat_id"])
        else:
            beat["beat_id"], beat["keyframe_id"] = f"B{next_number:03d}", f"KF{next_number:03d}"
            next_number += 1
            fresh.append(beat["beat_id"])
    return {"kept": kept, "new_needing_direction": fresh}
