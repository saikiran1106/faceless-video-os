"""Sound mix: narration (untouched, unity) + chapter score + ambience beds + picture/word-locked SFX, sidechain-ducked
under the voice, mastered to -14 LUFS. Writes 08-compose/mix.wav + mix_report.json.

Rules from the client iterations: never time-stretch or pitch-shift the narration; music ~11.5 dB under the voice
(median, never closer than 9.5 dB in any 3 s window); SFX louder than the music; every transition and text pop has a sound.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from . import WildDocError
from . import shotlist as SL
from . import sound
from .project import Project, norm, write_json

SR = 48000
db = lambda d: 10 ** (d / 20)  # noqa: E731

# overlay kind -> SFX (name, gain dB)
OV_SFX = {"kw": [("pop_text", -6), ("click_a", -10)], "threat": [("hit_short", -5), ("glitch_a", -12)], "danger": [("impact_boom", -4), ("glitch_c", -10)],
          "stamp": [("stamp_thud", -4)], "time": [("typing_burst", -9), ("clock_tick", -16)], "year": [("rewind_time", -7)], "counter": [("rewind_time", -7)],
          "clock": [("clock_tick", -11)], "bigword": [("impact_boom", -4)], "poll": [("ui_reveal", -9), ("click_a", -9)],
          "fact": [("scan_hud", -10), ("typing_burst", -12)], "videocard": [("click_b", -8), ("whoosh_fast_a", -12)],
          "measure": [("whoosh_fast_b", -9), ("click_a", -11)], "horn": [("whoosh_fast_b", -9), ("click_a", -11)],
          "namecard": [("whoosh_b", -10), ("pop_text", -8)], "yeartag": [("pop_text", -8)], "word3": [("hit_short", -5)],
          "question": [("pop_text", -8)], "thermo": [("ice_crackle", -10)], "bodyheat": [("heartbeat", -12)]}


def _load(p: Path, mono: bool = False):
    import numpy as np

    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-ac", "1" if mono else "2", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32)
    return x if mono else x.reshape(-1, 2)


def _lufs(x) -> float:
    o = subprocess.run(["ffmpeg", "-hide_banner", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-af", "ebur128", "-f", "null", "-"],
                       input=x.astype("float32").tobytes(), capture_output=True).stderr.decode()
    return float(o[o.rindex("I:"):].split()[1])


def run(project: Project) -> dict:
    import numpy as np

    plan = json.loads(project.plan_path.read_text(encoding="utf-8"))
    T = project.timeline()
    style = project.style()
    M = style.get("mix", {})
    fps = plan["fps"]
    N = int(plan["durationInFrames"] / fps * SR) + SR
    voice = _load(project.voice_master, mono=True)
    V = np.zeros(N, np.float32)
    V[:min(N, len(voice))] = voice[:N]
    music = np.zeros((N, 2), np.float32)
    beds = np.zeros((N, 2), np.float32)
    sfx = np.zeros((N, 2), np.float32)
    missing: set[str] = set()

    def place(bus, x, t, gain_db=0.0, fade_in=0.0, fade_out=0.0, length=None):
        x = x.copy() * db(gain_db)
        if length is not None:
            x = x[:int(length * SR)]
        n = len(x)
        if fade_in:
            k = min(n, int(fade_in * SR))
            x[:k] *= np.linspace(0, 1, k)[:, None]
        if fade_out:
            k = min(n, int(fade_out * SR))
            x[-k:] *= np.linspace(1, 0, k)[:, None]
        s = int(t * SR)
        if s < 0:
            x, s = x[-s:], 0
        e = min(N, s + len(x))
        if e > s:
            bus[s:e] += x[:e - s]

    def loop_to(x, secs):
        n = int(secs * SR)
        return np.concatenate([x] * (int(np.ceil(n / max(1, len(x)))) + 1))[:n]

    # ---------- score: one cue per chapter
    ch = plan["chapters"]
    starts = [c["from"] / fps for c in ch]
    ends = starts[1:] + [plan["durationInFrames"] / fps]
    for c, s0, s1 in zip(ch, starts, ends):
        cs = project.chapter_style(c["name"])
        f = Path(cs["music_file"]).expanduser() if cs.get("music_file") else project.p("assets", "music", f"{c['name']}.mp3")
        if not f.is_absolute():
            f = project.root / f
        if not f.exists():
            if cs.get("music") or cs.get("music_file"):
                missing.add(f"music:{c['name']}")
            continue
        cue = _load(f)
        cue = cue * db(-16.0 - _lufs(cue))
        if len(cue) / SR < (s1 - s0) + 1.2:
            cue = loop_to(cue, (s1 - s0) + 1.2)
        place(music, cue, max(0, s0 - 0.3), fade_in=0.4, fade_out=1.2, length=(s1 - s0) + 1.2)

    # ---------- ambience beds
    for c, s0, s1 in zip(ch, starts, ends):
        bed = project.chapter_style(c["name"]).get("bed")
        if not bed:
            continue
        name, g = bed[0], float(bed[1]) if len(bed) > 1 else -24.0
        f = sound.find(project, name)
        if not f:
            missing.add(name)
            continue
        place(beds, loop_to(_load(f), s1 - s0 + 1.5), s0 - 0.5, gain_db=g, fade_in=1.2, fade_out=1.5)

    # ---------- SFX
    cache: dict = {}

    def sfxfile(name):
        if name not in cache:
            f = sound.find(project, name)
            if not f:
                missing.add(name)
                cache[name] = None
            else:
                x = _load(f)
                cache[name] = (x, int(np.argmax(np.abs(x).max(1))) / SR)
        return cache[name]

    cues = []
    last_at: dict[str, float] = {}

    def cue(name, t_event, g, align="peak", gap=0.15):
        if t_event - last_at.get(name, -9) < gap:
            return
        got = sfxfile(name)
        if got is None:
            return
        last_at[name] = t_event
        x, pk = got
        place(sfx, x, t_event + 1 / fps - (pk if align == "peak" else 0.0), gain_db=g)
        cues.append((round(t_event, 2), name, g))

    rot = lambda names, k: names[k % len(names)]  # noqa: E731
    kw = kg = 0
    for s in plan["shots"]:
        t, k = s["from"] / fps, s.get("trans")
        if s.get("sub_i"):
            if k == "glitch":
                cue(rot(["glitch_a", "glitch_b", "glitch_c"], kg), t, -11); kg += 1  # noqa: E702
            elif k == "zoom":
                cue("whoosh_fast_b", t, -11)
            else:
                cue("click_b", t, -14)
        elif k == "whip":
            cue(rot(["whoosh_fast_a", "whoosh_fast_b", "whoosh_a"], kw), t, -5); kw += 1  # noqa: E702
        elif k == "zoom":
            cue("zoom_in", t, -6)
        elif k == "glitch":
            cue(rot(["glitch_a", "glitch_b", "glitch_c"], kg), t, -6); kg += 1  # noqa: E702
        elif k == "punch":
            cue("hit_short", t, -4); cue("impact_hit", t, -9)  # noqa: E702
        elif k == "flash":
            cue("camera_flash", t, -8); cue("whoosh_b", t, -11)  # noqa: E702
        elif k == "dip":
            cue("swoosh_rev", t, -11)
        elif k == "leak":
            cue("whoosh_b", t, -11)
        elif k == "ice":
            cue("ice_crackle", t, -9)
        elif k == "cut" and s["kind"] == "mg" and s.get("mg") == "black":
            cue("impact_boom", t, -1)
        if s["kind"] == "ref" and not s.get("sub_i"):
            cue("camera_flash", t + 0.02, -10); cue("scan_hud", t + 0.05, -15, align="start")  # noqa: E702
        if s["kind"] == "mg":
            m = s.get("mg")
            if m == "title":
                r = sfxfile("riser")
                if r:
                    place(sfx, r[0], t - len(r[0]) / SR, gain_db=-9)
                cue("impact_boom", t, -3)
            elif m in ("percent", "dna"):
                cue("shimmer", t, -9)
            elif m in ("scale", "timeline", "endcard", "compare", "card"):
                cue("ui_reveal", t, -9); cue("whoosh_fast_a", t, -9)  # noqa: E702
            elif m == "map":
                cue("whoosh_b", t, -9)
    for o in plan["overlays"]:
        for n, g in OV_SFX.get(o["kind"], [("pop_text", -8)]):
            cue(n, o["from"] / fps + 0.02, g, gap=0.08)

    # story sounds on exact words (X rows)
    sl = SL.parse(project.shotlist_path.read_text(encoding="utf-8"))
    lines = {ln["i"]: ln for ln in T["lines"]}
    boost = float(M.get("story_boost_db", 3))
    for x in sl["story"]:
        ln = lines.get(x["line"])
        if not ln or not ln.get("spoken", True):
            continue
        if x["anchor"] == "^":
            t = ln["start"]
        else:
            ws = [w for w in T["words"] if w["line"] == x["line"] and norm(w["text"]) == norm(x["anchor"])]
            if not ws:
                raise WildDocError(f"X row {x['row']}: anchor '{x['anchor']}' not in L{x['line']}")
            t = ws[0]["start"]
        cue(x["name"], t, x["gain"] + boost, gap=0.0)
    for c in ch[1:]:  # chapter turns never drop to dead air
        t = c["from"] / fps
        cue("sub_drop", t - 0.3, -10, gap=0.0); cue("whoosh_b", t - 0.15, -13, gap=0.0)  # noqa: E702

    # ---------- sidechain duck under the voice
    win = int(0.02 * SR)
    env = np.sqrt(np.convolve(V ** 2, np.ones(win) / win, "same"))
    active = (env > db(-42)).astype(np.float32)
    hop = int(0.005 * SR)

    def duck_curve(depth_db):
        tgt = 1 - active * (1 - db(-depth_db))
        g = np.empty_like(tgt)
        cur = 1.0
        a_att, a_rel = 1 - np.exp(-1 / (0.015 * SR)), 1 - np.exp(-1 / (0.25 * SR))
        for i in range(0, len(tgt), hop):
            t_ = tgt[i]
            a = a_att if t_ < cur else a_rel
            cur += (t_ - cur) * (1 - (1 - a) ** hop)
            g[i:i + hop] = cur
        return g

    gm, gs = duck_curve(M.get("duck_music_db", 6)), duck_curve(M.get("duck_sfx_db", 3))
    W = 3 * SR

    def windows(bgx):
        out = []
        for i in range(0, N - W, W):
            m = active[i:i + W] > 0
            if m.mean() < 0.3:
                continue
            v = np.sqrt(np.mean(V[i:i + W][m] ** 2))
            b = np.sqrt(np.mean(bgx[i:i + W][m] ** 2)) + 1e-9
            out.append((i, float(20 * np.log10(v / b))))
        return out

    MB = (music + beds) * gm[:, None]
    margin, floor = float(M.get("music_margin_db", 11.5)), float(M.get("music_min_db", 9.5))
    w0 = windows(MB)
    fixed = []
    if w0 and np.abs(MB).max() > 0:
        med = float(np.median([m for _, m in w0]))
        MB *= db(med - margin)
        fixg = np.ones(N, np.float32)
        for i, mg in windows(MB):
            if mg < floor:
                g = db(-(floor - mg) - 0.3)
                fixed.append((round(i / SR, 1), round(mg, 1)))
                a_, b2 = max(0, i - SR // 2), min(N, i + W + SR // 2)
                ramp = np.ones(b2 - a_, np.float32) * g
                k = SR // 2
                ramp[:k] = np.linspace(1, g, k)
                ramp[-k:] = np.linspace(g, 1, k)
                fixg[a_:b2] = np.minimum(fixg[a_:b2], ramp)
        MB = MB * fixg[:, None]
    margins = [m for _, m in windows(MB)] if np.abs(MB).max() > 0 else []
    mix = V[:, None] * np.ones((1, 2), np.float32) + MB + sfx * gs[:, None]
    if not np.isfinite(mix).all():
        raise WildDocError("mix produced non-finite samples (flaky numpy run?) - re-run `faceless wild-doc mix`")

    raw = project.p("compose", "mix_raw.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "pcm_f32le", str(raw)],
                   input=mix.astype(np.float32).tobytes(), check=True)
    lufs, tp = float(M.get("lufs", -14)), float(M.get("true_peak", -1.2))
    o = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(raw), "-af", f"loudnorm=I={lufs}:TP={tp}:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    m = json.loads(o[o.rindex("{"):o.rindex("}") + 1])
    out = project.p("compose", "mix.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af",
                    f"loudnorm=I={lufs}:TP={tp}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
                    f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,alimiter=limit=0.89:level=false",
                    "-ar", str(SR), "-c:a", "pcm_s24le", str(out)], check=True)
    raw.unlink(missing_ok=True)
    rep = {"mix": str(out), "cues": len(cues), "missing_sounds": sorted(missing),
           "voice_over_music_db": {"min": round(min(margins), 1), "median": round(float(np.median(margins)), 1)} if margins else None,
           "music_pulled_down_windows": fixed[:20]}
    write_json(project.p("compose", "mix_report.json"), rep)
    project.log("mix", cues=len(cues), missing=sorted(missing))
    return rep
