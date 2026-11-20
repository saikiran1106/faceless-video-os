"""Project layout, style loading and small shared helpers for wild-doc."""
from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from . import WildDocError

STYLE_DIR = Path(__file__).resolve().parents[2] / "styles" / "wild-doc"
REMOTION_DIR = STYLE_DIR / "remotion"

LAYOUT = {
    "source": "00-source",
    "audio": "01-audio",
    "direction": "02-direction",
    "assets": "06-assets",
    "compose": "08-compose",
    "public": "08-compose/public",
    "package": "09-package",
}


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any, indent: int | None = 1) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")
    tmp.replace(path)
    return path


_PUNCT = re.compile(r"[।॥]")  # Devanagari danda / double danda


def norm(word: str) -> str:
    """Normalised comparison form of a word: NFC, no punctuation, lower case."""
    w = unicodedata.normalize("NFC", word or "")
    w = _PUNCT.sub("", w)
    w = "".join(ch for ch in w if not unicodedata.category(ch).startswith("P") and unicodedata.category(ch) not in ("Sm", "Sk", "So"))
    return w.lower().strip()


def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()).strip("-").lower()
    return s or "chapter"


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def ffprobe_duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    try:
        return float(out)
    except ValueError as exc:
        raise WildDocError(f"ffprobe could not read {path}") from exc


def frame_count(path: Path) -> int:
    out = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries",
                          "stream=nb_read_packets", "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout
    try:
        return int(out.strip().strip(",") or 0)
    except ValueError:
        return 0


def decode_errors(path: Path, stream: str = "v") -> int:
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", f"0:{stream}", "-f", "null", "-"], capture_output=True, text=True)
    return len([ln for ln in r.stderr.splitlines() if ln.strip()]) + (1 if r.returncode else 0)


class Project:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        if not (self.root / "project.json").exists():
            raise WildDocError(f"No wild-doc project at {self.root} (missing project.json). Start one with `faceless wild-doc new`.")
        self.meta = read_json(self.root / "project.json")

    # ---- paths
    def p(self, key: str, *parts: str) -> Path:
        return self.root.joinpath(LAYOUT[key], *parts)

    @property
    def slug(self) -> str:
        return self.meta["slug"]

    @property
    def script_path(self) -> Path:
        return self.p("source", "script.txt")

    @property
    def voice_source(self) -> Path:
        return self.root / self.meta["audio"]

    @property
    def voice_master(self) -> Path:
        return self.p("audio", "voice_master.wav")

    @property
    def timeline_path(self) -> Path:
        return self.p("audio", "timeline.json")

    @property
    def shotlist_path(self) -> Path:
        return self.p("direction", "shotlist.txt")

    @property
    def plan_path(self) -> Path:
        return self.p("compose", "plan.json")

    @property
    def master_path(self) -> Path:
        return self.p("package", f"{self.slug}.mp4")

    # ---- style
    def style(self) -> dict:
        base = read_json(STYLE_DIR / "style.json", {})
        return deep_merge(base, read_json(self.root / "style.json", {}))

    def chapter_style(self, name: str) -> dict:
        ch = self.style().get("chapters", {})
        return deep_merge(ch.get("*", {}), ch.get(name, {}))

    def timeline(self) -> dict:
        t = read_json(self.timeline_path)
        if t is None:
            raise WildDocError("No timeline yet. Run `faceless wild-doc align <project>` (after transcribe).")
        return t

    def log(self, event: str, **data: Any) -> None:
        path = self.root / ".wilddoc" / "log.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": datetime.now().isoformat(timespec="seconds"), "event": event, **data}, ensure_ascii=False) + "\n")

    @classmethod
    def create(cls, root: Path, slug: str, script: Path, audio: Path, title: str = "", language: str = "", channel: str = "") -> "Project":
        root = Path(root) / slug
        if (root / "project.json").exists():
            raise WildDocError(f"{root} already exists. Use it, or pick another name.")
        script, audio = Path(script).expanduser(), Path(audio).expanduser()
        for f in (script, audio):
            if not f.exists():
                raise WildDocError(f"File not found: {f}")
        for key in LAYOUT.values():
            (root / key).mkdir(parents=True, exist_ok=True)
        shutil.copy(script, root / LAYOUT["source"] / "script.txt")
        audio_dst = root / LAYOUT["source"] / f"voice{audio.suffix.lower()}"
        shutil.copy(audio, audio_dst)
        write_json(root / "project.json", {"slug": slug, "title": title or slug.replace("-", " ").title(), "language": language,
                                           "audio": str(audio_dst.relative_to(root)), "style": "wild-doc",
                                           "created": datetime.now().isoformat(timespec="seconds")})
        style = {"_doc": "Overrides for styles/wild-doc/style.json. Edit chapters (look/title/music/bed), story_sfx, channel, thumbnail."}
        if language:
            style["language"] = language
        if channel:
            style["channel"] = {"name": channel}
        write_json(root / "style.json", style)
        return cls(root)
