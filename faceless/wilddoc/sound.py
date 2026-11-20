"""Sound for wild-doc: the transition/graphics SFX kit, story sounds on words, ambience beds and the chapter score.

Kit      ~/.faceless/sfx-kit/wild-doc/<name>.(mp3|wav)   shared by every project. `kit --via elevenlabs` (paid, best) or
         `kit --via procedural` (free, synthesized placeholders - fine for drafts, replace before delivery).
Story    style.json "story_sfx": {"wolf_howl_far": ["Several wolves howling in the far distance at night", 12], ...}
         -> 06-assets/sfx/<name>.mp3 (ElevenLabs) or drop your own file there with that name.
Beds     style.json chapters.<name>.bed = ["wind_howl_bed", -24]  (a story_sfx name, looped under the chapter)
Music    style.json chapters.<name>.music = "<prompt>" (ElevenLabs music, paid) or .music_file = "path/to.mp3"
"""
from __future__ import annotations

import json
import os
import wave
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from . import WildDocError
from .project import Project

KIT_DIR = Path(os.environ.get("FACELESS_SFX_KIT", str(Path.home() / ".faceless" / "sfx-kit" / "wild-doc"))).expanduser()

KIT: dict[str, tuple[str, float]] = {
    "whoosh_fast_a": ("Very fast short air whoosh swish transition", 0.6),
    "whoosh_fast_b": ("Short sharp cinematic swish, fast pass-by", 0.7),
    "whoosh_a": ("Fast cinematic whoosh transition, airy", 1.5),
    "whoosh_b": ("Deep heavy cinematic swoosh with low rumble", 2.0),
    "zoom_in": ("Fast zoom-in whoosh with rising pitch ending in a soft impact", 1.0),
    "swoosh_rev": ("Reverse whoosh sucking in, building to a cut", 1.2),
    "glitch_a": ("Short digital glitch stutter, data corruption burst, electronic", 0.8),
    "glitch_b": ("Digital glitch transition, bit-crushed static zap", 1.0),
    "glitch_c": ("Quick electronic glitch with RGB static crackle and a low thump", 1.0),
    "click_a": ("Crisp modern UI click for text popping on screen", 0.5),
    "click_b": ("Snappy click with a tiny pop", 0.5),
    "pop_text": ("Punchy text pop-in sound: short swish ending in a click", 0.7),
    "hit_short": ("Tight deep cinematic punch hit, short", 0.8),
    "impact_hit": ("Short punchy cinematic hit, low and tight", 1.5),
    "impact_boom": ("Huge deep cinematic impact boom with long sub tail", 4.0),
    "sub_drop": ("Deep sub bass drop, cinematic", 3.0),
    "riser": ("Cinematic tension riser building for four seconds, then cut", 4.0),
    "camera_flash": ("Camera flash pop with a short bright shimmer", 0.8),
    "scan_hud": ("Futuristic scanner beep sweep, HUD data scan", 1.5),
    "typing_burst": ("Fast keyboard typing burst, six quick clicks", 1.0),
    "stamp_thud": ("Rubber stamp slammed on paper, heavy thud", 0.8),
    "ui_reveal": ("Subtle shimmering reveal sound for a fact card appearing", 1.5),
    "clock_tick": ("Old clock ticking, slow, isolated", 6.0),
    "rewind_time": ("Time rewind effect, reverse whoosh with swirling sounds traveling back in time", 3.0),
    "ice_crackle": ("Ice crystals freezing and crackling, close, delicate", 4.0),
    "heartbeat": ("A slow heavy human heartbeat, deep, cinematic", 12.0),
    "shimmer": ("Magical scientific shimmer, soft glittering tone", 3.0),
}

SR = 48000


def find(project: Project | None, name: str) -> Path | None:
    dirs = ([project.p("assets", "sfx")] if project else []) + [KIT_DIR]
    for d in dirs:
        for ext in (".mp3", ".wav", ".ogg", ".flac"):
            if (d / f"{name}{ext}").exists():
                return d / f"{name}{ext}"
    return None


def _eleven(url: str, body: dict, out: Path) -> str:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise WildDocError("ELEVENLABS_API_KEY not set")
    if out.exists() and out.stat().st_size > 1000:
        return f"skip {out.name}"
    r = requests.post(url, json=body, headers={"xi-api-key": key}, timeout=600)
    if r.status_code != 200:
        return f"FAIL {out.name} {r.status_code} {r.text[:160]}"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(r.content)
    return f"ok {out.name}"


def _sfx_job(prompt: str, dur: float, out: Path):
    return ("https://api.elevenlabs.io/v1/sound-generation",
            {"text": prompt, "duration_seconds": max(0.5, min(22.0, dur)), "prompt_influence": 0.6, "model_id": "eleven_text_to_sound_v2"}, out)


def kit_plan(via: str) -> dict:
    todo = [n for n in KIT if not find(None, n)]
    return {"provider": via, "kit_dir": str(KIT_DIR), "missing": len(todo), "sfx_seconds": round(sum(KIT[n][1] for n in todo), 1),
            "note": "ElevenLabs sound generation spends your ElevenLabs credits." if via == "elevenlabs" else "free, offline"}


def make_kit(via: str = "procedural") -> dict:
    todo = [n for n in KIT if not find(None, n)]
    KIT_DIR.mkdir(parents=True, exist_ok=True)
    if via == "elevenlabs":
        with ThreadPoolExecutor(2) as ex:
            res = list(ex.map(lambda n: _eleven(*_sfx_job(KIT[n][0], KIT[n][1], KIT_DIR / f"{n}.mp3")), todo))
    else:
        res = [f"ok {n}.wav" for n in todo if _procedural(n, KIT_DIR / f"{n}.wav")]
    return {"kit_dir": str(KIT_DIR), "made": res, "total": len(KIT)}


def story_plan(project: Project) -> dict:
    st = project.style().get("story_sfx", {})
    todo = {n: v for n, v in st.items() if not find(project, n)}
    return {"provider": "elevenlabs", "missing": sorted(todo), "sfx_seconds": round(sum(float(v[1]) for v in todo.values()), 1)}


def make_story(project: Project) -> dict:
    st = project.style().get("story_sfx", {})
    todo = {n: v for n, v in st.items() if not find(project, n)}
    if not todo:
        return {"made": [], "note": "all story sounds present"}
    with ThreadPoolExecutor(2) as ex:
        res = list(ex.map(lambda kv: _eleven(*_sfx_job(kv[1][0], float(kv[1][1]), project.p("assets", "sfx", f"{kv[0]}.mp3"))), todo.items()))
    return {"made": res}


def music_plan(project: Project) -> dict:
    T = project.timeline()
    ch = T["chapters"]
    ends = [c["start"] for c in ch[1:]] + [T["duration"]]
    todo = []
    for c, e in zip(ch, ends):
        cs = project.chapter_style(c["name"])
        if cs.get("music_file") or not cs.get("music") or project.p("assets", "music", f"{c['name']}.mp3").exists():
            continue
        todo.append({"chapter": c["name"], "seconds": round(min(e - c["start"] + 6, 300), 1)})
    return {"provider": "elevenlabs-music", "cues": todo, "music_seconds": round(sum(t["seconds"] for t in todo), 1)}


def make_music(project: Project) -> dict:
    base = project.style().get("music_base_prompt", "")
    jobs = []
    for t in music_plan(project)["cues"]:
        cs = project.chapter_style(t["chapter"])
        jobs.append(("https://api.elevenlabs.io/v1/music", {"prompt": base + cs["music"], "music_length_ms": int(t["seconds"] * 1000),
                                                            "force_instrumental": True}, project.p("assets", "music", f"{t['chapter']}.mp3")))
    with ThreadPoolExecutor(2) as ex:
        return {"made": list(ex.map(lambda j: _eleven(*j), jobs))}


# ---------------------------------------------------------------- procedural placeholder kit (free)
def _procedural(name: str, out: Path) -> bool:
    import numpy as np

    rng = np.random.default_rng(zlib.crc32(name.encode()))
    dur = KIT[name][1]
    n = int(SR * dur)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)

    def lp(x, a):  # one-pole low-pass, a in (0,1): larger = darker
        y = np.empty_like(x)
        acc = 0.0
        for i in range(len(x)):
            acc = a * acc + (1 - a) * x[i]
            y[i] = acc
        return y

    def env(attack, decay):
        e = np.minimum(1, t / max(attack, 1e-3)) * np.exp(-np.maximum(0, t - attack) / max(decay, 1e-3))
        return e

    if name.startswith(("whoosh", "swoosh", "zoom")):
        shape = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 2
        if name == "swoosh_rev":
            shape = (t / dur) ** 3
        x = lp(noise, 0.75 if name in ("whoosh_b",) else 0.45) * shape
        if name == "zoom_in":
            x += 0.4 * np.sin(2 * np.pi * (200 + 900 * t / dur) * t) * shape
    elif name.startswith("glitch"):
        gate = (rng.random(n // 400 + 1) > 0.45).repeat(400)[:n]
        x = np.sign(noise) * gate * env(0.002, dur / 3) * 0.6 + 0.5 * np.sin(2 * np.pi * 60 * t) * env(0.001, 0.08)
    elif name in ("click_a", "click_b", "pop_text", "camera_flash"):
        x = lp(noise, 0.2) * env(0.0005, 0.012) + (0.3 * np.sin(2 * np.pi * 2400 * t) * env(0.0005, 0.03) if name != "click_a" else 0)
        if name == "camera_flash":
            x += 0.15 * np.sin(2 * np.pi * 5200 * t) * env(0.01, 0.25)
    elif name in ("hit_short", "impact_hit", "impact_boom", "stamp_thud", "sub_drop"):
        f0, dec = {"hit_short": (70, 0.18), "impact_hit": (60, 0.35), "impact_boom": (45, 1.4), "stamp_thud": (110, 0.09), "sub_drop": (55, 1.0)}[name]
        sweep = f0 * (1 + 1.5 * np.exp(-t / 0.05)) if name != "sub_drop" else f0 * (1 + 1.2 * np.exp(-t / 0.6))
        x = np.sin(2 * np.pi * np.cumsum(sweep) / SR) * env(0.002, dec) + 0.25 * lp(noise, 0.5) * env(0.001, 0.03)
    elif name == "riser":
        x = lp(noise, 0.6) * (t / dur) ** 2 + 0.3 * np.sin(2 * np.pi * np.cumsum(100 + 700 * (t / dur) ** 2) / SR) * (t / dur) ** 2
    elif name in ("scan_hud", "ui_reveal", "shimmer"):
        x = sum(np.sin(2 * np.pi * f * t + k) for k, f in enumerate((1760, 2637, 3520))) / 3 * env(0.05, dur / 3)
        if name == "scan_hud":
            x *= 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 12 * t))
    elif name in ("typing_burst", "clock_tick"):
        x = np.zeros(n)
        step = 0.15 if name == "typing_burst" else 1.0
        for k in range(int(dur / step)):
            s = int(k * step * SR)
            m = min(n - s, int(0.02 * SR))
            x[s:s + m] += lp(rng.standard_normal(m), 0.2) * np.exp(-np.arange(m) / (0.003 * SR))
    elif name == "heartbeat":
        x = np.zeros(n)
        for b in np.arange(0, dur - 0.4, 1.0):
            for off, g in ((0.0, 1.0), (0.28, 0.7)):
                s = int((b + off) * SR)
                m = min(n - s, int(0.25 * SR))
                tt = np.arange(m) / SR
                x[s:s + m] += g * np.sin(2 * np.pi * 50 * tt) * np.exp(-tt / 0.07)
    elif name in ("ice_crackle", "rewind_time"):
        x = lp(noise, 0.1) * (rng.random(n) > 0.995) * 4 + (0.3 * np.sin(2 * np.pi * np.cumsum(800 - 600 * t / dur) / SR) * env(0.1, dur) if name == "rewind_time" else 0)
    else:
        return False
    x = np.asarray(x, dtype=np.float64)
    x = x / (np.max(np.abs(x)) + 1e-9) * 0.7
    fade = min(n, int(0.005 * SR))
    x[-fade:] *= np.linspace(1, 0, fade)
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return True


def plan_all(project: Project) -> dict:
    return {"kit": kit_plan("elevenlabs"), "story": story_plan(project), "music": music_plan(project)}


def describe() -> str:
    return json.dumps({k: v[0] for k, v in KIT.items()}, indent=1)
