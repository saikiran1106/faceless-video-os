"""Package stage: a publish-ready draft (chapters, captions file, hashtags) for the agent to finish.

Titles, description and thumbnail are creative work: the faceless-package skill
fills them - with vidIQ's MCP tools when connected, from the built-in rules when not.
This module computes only what can be computed: chapter timestamps, the SRT, limits.
"""
from __future__ import annotations

from typing import Any

from .captions import build_pages, caption_words, normalize, to_srt
from .config import load_channel, load_profile
from .engine import ProductionEngine, StateError
from .io import atomic_write_json, load_json


def _fmt(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def section_times(script: dict[str, Any], words: list[dict[str, Any]]) -> list[tuple[str, float]]:
    """Start time of each script section, found by walking the timed words in order."""
    timed = [normalize(w["text"]) for w in words]
    times, cursor = [], 0
    for section in script["sections"]:
        head = [t for t in (normalize(x) for x in section["text"].split()) if t][:4]
        found = None
        for i in range(cursor, len(timed)):
            if timed[i : i + len(head)] == head:
                found = i
                break
        if found is None:  # fall back to proportional position
            found = min(len(words) - 1, cursor)
        times.append((section["title"], words[found]["start"]))
        cursor = found + max(1, len(section["text"].split()) - 2)
    return times


def draft(engine: ProductionEngine, force: bool = False) -> dict[str, Any]:
    path = engine.artifact_path("package")
    if path.exists() and not force:
        raise StateError(f"{path} exists; pass --force to rebuild the draft")
    state = engine.state()
    profile = load_profile(state["format"])
    channel = load_channel()
    transcript = load_json(engine.artifact_path("transcript"))
    script = load_json(engine.artifact_path("script"))
    brief = load_json(engine.artifact_path("brief"))
    cap = profile["captions"]
    pages = build_pages(caption_words(transcript, script), cap["max_words_per_page"] * 2, cap["max_chars_per_page"] * 2)
    srt_path = engine.project_root / "09-package" / "captions.srt"
    srt_path.write_text(to_srt(pages), encoding="utf-8")

    chapters = []
    if profile.get("chapters") and len(script["sections"]) >= 3:
        times = section_times(script, caption_words(transcript, script))
        kept: list[tuple[str, float]] = []
        for i, (title, t) in enumerate(times):
            t = 0.0 if i == 0 else t
            if kept and t - kept[-1][1] < 10:  # YouTube rejects chapters closer than 10s
                continue
            kept.append((title, t))
        if len(kept) >= 3:  # YouTube needs at least three, or it shows none
            chapters = [{"time": _fmt(t), "title": title} for title, t in kept]

    hashtags = list(channel["packaging"].get("default_hashtags", []))[:3]
    pkg: dict[str, Any] = {
        "version": "1.0",
        "vidiq_used": False,
        "primary_keyword": "TODO primary search phrase",
        "keyword_research": [],
        "title_candidates": [],
        "youtube": {
            "title": brief["title"],
            "description": f"{script['hook']['text']}\n\nTODO: 2-3 lines that restate the promise with the primary keyword in the first 150 characters.",
            "tags": list(channel["packaging"].get("default_tags", [])),
            "hashtags": hashtags,
            "chapters": chapters,
            "thumbnail_path": "",
            "thumbnail_text": "",
            "made_for_kids": False,
            "pinned_comment": script.get("cta", {}).get("end", ""),
        },
        "captions_srt": str(srt_path.relative_to(engine.project_root)),
    }
    if state["format"] == "short":
        pkg["shorts"] = {"title": brief["title"], "description": "TODO one-line hook + #shorts", "hashtags": hashtags + ["#shorts"]}
        pkg["instagram"] = {"caption": "TODO hook line, then the question, then a comment prompt", "hashtags": hashtags}
    atomic_write_json(path, pkg)
    return {"path": str(path), "chapters": len(chapters), "srt": pkg["captions_srt"]}
