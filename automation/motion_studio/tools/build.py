#!/usr/bin/env python3
"""Campaign JSON -> one HyperFrames project per variant (hook x format x CTA).

The campaign says WHAT is in the video (text, scenes, beats); this file and engine/runtime.js decide HOW it
moves. Times in the campaign are beats; positions are fractions of the format's safe band, so the same
campaign lays itself out for 9:16, 1:1 and 16:9.

  python3 tools/build.py campaigns/<id>/campaign.json [--hooks A,B] [--formats 9:16] [--ctas A]
"""
import argparse, hashlib, html, json, os, re, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import validate  # noqa: E402

FORMATS = {
    # W, H, safe band (x, y, w, h) where words may sit, size scale
    "9:16": dict(W=1080, H=1920, band=(80, 168, 920, 1162), s=1.0, slug="9x16"),
    "1:1": dict(W=1080, H=1080, band=(90, 90, 900, 900), s=0.82, slug="1x1"),
    "16:9": dict(W=1920, H=1080, band=(160, 90, 1600, 900), s=0.95, slug="16x9", split=True),
}
SFX_VOL = {"glitch-1": 0.3, "glitch-2": 0.3,"click": 0.55, "click-b": 0.5, "key-press": 0.14, "pop": 0.42, "whoosh": 0.32, "whoosh-b": 0.3,
           "riser": 0.3, "impact-bass-1": 0.62, "impact-bass-2": 0.55, "whoosh-cinematic": 0.3}
TEMPLATE_VERSION = "motion-studio"


def hexa(c, brand):
    """'accent', '#FF7F00', 'accent@0.15', 'none' -> [r, g, b, a]."""
    if c in (None, "none"):
        return [0, 0, 0, 0]
    a = 1.0
    if "@" in c:
        c, a = c.split("@")
        a = float(a)
    c = brand["colors"].get(c, c)
    return [int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16), a]


def pick(d, key, fmt, default=None):
    """Per-format override: 'pos@16:9' wins over 'pos'."""
    return d.get(f"{key}@{fmt}", d.get(key, default))


def peak_and_len(path, cache={}):
    if path not in cache:
        import numpy as np
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                             capture_output=True, check=True).stdout
        a = np.abs(np.frombuffer(raw, dtype=np.int16).astype(float))
        cache[path] = (a.argmax() / 8000, len(a) / 8000)
    return cache[path]


class Build:
    def __init__(self, camp, brand, fmt, hook, cta):
        self.c, self.brand, self.fmtname = camp, brand, fmt
        self.f = FORMATS[fmt]
        self.spb = 60.0 / camp["bpm"]
        self.items, self.html, self.hero, self.cur, self.cam = [], [], [], [], []
        self.clicks, self.holds, self.show, self.sfx, self.scenes = [], [], [], [], []
        self.anchors = {}
        self.n = 0
        self.hero_html, self.foot, self.waves, self.assets = [], [], [], []
        self.cdir = ROOT
        self.seq = [("hook", camp["hooks"][hook])] + [(s["id"], s) for s in camp["body"]] + [("cta", camp["ctas"][cta])]

    # ----- geometry -----
    def S(self, v):
        return v * self.f["s"]

    def set_bands(self, sid, sc):
        bx, by, bw, bh = self.f["band"]
        split = self.f.get("split") and sc.get("split", sid not in ("hook", "cta"))
        self.band = (bx + bw * 0.44, by, bw * 0.56, bh) if split else self.f["band"]
        self.cap_band = (bx, by, bw * 0.40, bh) if split else None

    def P(self, pos, at=None, caption=False):
        """Band fraction [bx, by], 'hero', or 'anchor:name' -> canvas px (cx, cy)."""
        if pos == "hero":
            k = self.hero_at(at)
            return ((k["l"] + k["r"]) / 2, (k["tp"] + k["b"]) / 2)
        if isinstance(pos, str) and pos.startswith("anchor:"):
            a = self.anchors[pos[7:]]
            return (a[0], a[1])
        if caption and self.cap_band:  # a caption moves to the middle of the left column
            bx, by, bw, bh = self.cap_band
            return (bx + bw / 2, by + bh * 0.5)
        bx, by, bw, bh = self.band
        return (bx + pos[0] * bw, by + pos[1] * bh)

    def hero_at(self, t):
        ks = [k for k in self.hero if k["t"] <= t + 1e-6]
        return ks[-1] if ks else self.hero[0]

    def nid(self, p):
        self.n += 1
        return f"{p}{self.n:02d}"

    # ----- markup helpers -----
    def words(self, text):
        out = []
        for li, line in enumerate(text.split("\n")):
            if li:
                out.append("<br>")
            for tok in re.findall(r"\*[^*]+\*|\S+", line):
                acc = tok.startswith("*")
                for w in tok.strip("*").split():
                    out.append(f'<span class="w{" acc" if acc else ""}">{html.escape(w)}</span> ')
        return "".join(out).rstrip()

    def add(self, kind, t0, t1, markup, under=False, **extra):
        it = {"kind": kind, "in": round(t0, 4), "out": round(t1, 4), **extra}
        self.items.append(it)
        (self.cur_under if under else self.cur_html).append(markup)
        return it

    # ----- components -----
    def text(self, d, T, end):
        t0, t1 = T(d["at"]), T(d.get("until", end))
        pos = pick(d, "pos", self.fmtname)
        caption = isinstance(pos, list) and pos[1] <= 0.15 and self.cap_band is not None
        cx, cy = self.P(pos, t0, caption)
        size = self.S(pick(d, "size", self.fmtname, 72))
        if caption:  # as large as the left column allows (bold Inter averages ~0.56 em a character)
            longest = max(len(l) for l in d["text"].replace("*", "").split("\n"))
            size = min(size * 1.3, 0.92 * self.cap_band[2] / (longest * 0.56))
        font = "var(--mono)" if d.get("font") == "mono" else "var(--sans)"
        color = self.brand["colors"].get(d.get("color", "ink"), d.get("color", "ink"))
        align = d.get("align", "center")
        tx = {"center": "-50%", "left": "0", "right": "-100%"}[align]
        i = self.nid("t")
        cls = " ".join(filter(None, ["boxed box-" + d["box"] if d.get("box") else "", d.get("cls", "")]))
        if d.get("box") == "accent":
            color = self.brand["colors"]["accentInk"]
        self.add("text", t0, t1, f'<div id="{i}" class="it txt {cls}" style="left:{cx:.1f}px;top:{cy:.1f}px;font-size:{size:.1f}px;'
                 f'font-family:{font};font-weight:{d.get("weight", 800)};color:{color};text-align:{align};'
                 f'transform:translate({tx},-50%);letter-spacing:{d.get("track", -0.02)}em">{self.words(d["text"])}</div>',
                 id=i, fx=d.get("fx", "words"), tx=tx, **({"ws": [round(T(x), 3) for x in d["ws"]]} if "ws" in d else {}))

    def code(self, d, T, end):
        t0, t1 = T(d["at"]), T(d.get("until", end))
        k = self.hero_at(t0)
        pad = self.S(d.get("pad", 56))
        size = self.S(d.get("size", 40))
        i = self.nid("c")
        toks = []
        for li, line in enumerate(d["lines"]):
            if li:
                toks.append("<br>")
            for m in re.finditer(r"(const|let|return|=>|window)|([A-Za-z_]\w*)|(\s)|(.)", line):
                cls = "kw" if m.group(1) else "id" if m.group(2) else "sp" if m.group(3) else "pu"
                for ch in m.group(0):
                    toks.append(f'<span class="ch {cls}">{"&nbsp;" if ch == " " else html.escape(ch)}</span>')
        nch = sum(len(l) for l in d["lines"])
        cps = d.get("cps", 30)
        x0, y0 = d["xy"] if "xy" in d else (k["l"] + pad, k["tp"] + pad)
        self.add("code", t0, t1, f'<div id="{i}" class="it code{" plain" if d.get("plain") else ""}" style="left:{x0:.1f}px;top:{y0:.1f}px;'
                 f'font-size:{size:.1f}px">{"".join(toks)}<span id="{i}-caret" class="caret"></span></div>',
                 id=i, cps=cps)
        # one soft key tick every third character while typing
        for j in range(0, nch, 3):
            self.sfx.append((t0 + j / cps, "key-press", None))

    def count(self, d, T, end):
        t0, t1 = T(d["at"]), T(d.get("until", end))
        cx, cy = self.P(pick(d, "pos", self.fmtname), t0)
        size = self.S(d.get("size", 96))
        color = self.brand["colors"].get(d.get("color", "ink"), d.get("color"))
        font = "var(--mono)" if d.get("font") == "mono" else "var(--sans)"
        i = self.nid("n")
        roll = [T(d["roll"][0]), d["roll"][1] * self.spb]
        self.add("count", t0, t1, f'<div id="{i}" class="it num-wrap" style="left:{cx:.1f}px;top:{cy:.1f}px;font-size:{size:.1f}px;'
                 f'color:{color};font-family:{font}"><span class="pre">{html.escape(d.get("prefix", ""))}</span>'
                 f'<span class="num">{d["from"]}</span><span class="suf">{html.escape(d.get("suffix", ""))}</span></div>',
                 id=i, roll=roll, **{"from": d["from"], "to": d["to"], "dec": d.get("dec", 0)})
        if d.get("sfx"):
            self.sfx.append((roll[0] + roll[1] * 0.85, d["sfx"], None))

    def scrub(self, d, T, end):
        t0, t1 = T(d["at"]), T(d.get("until", end))
        cx, cy = self.P(pick(d, "pos", self.fmtname), t0)
        w = self.S(d.get("width", 760))
        x0 = cx - w / 2
        i = self.nid("s")
        k = self.hero_at(t0 + 0.6)
        pvs = self.S(110)
        pv = dict(cx=(k["l"] + k["r"]) / 2, cy=(k["tp"] + k["b"]) / 2, r=min(k["r"] - k["l"], k["b"] - k["tp"]) * 0.3, s=pvs)
        self.anchors[f"{d.get('name', 'scrub')}.track"] = (x0, cy, w, 0)
        self.add("scrub", t0, t1,
                 f'<div id="{i}" class="it scrub" style="left:{x0:.1f}px;top:{cy:.1f}px;width:{w:.1f}px;--k:{self.S(44):.1f}px">'
                 f'<div class="trk"></div><div id="{i}-fill" class="fill"></div><div id="{i}-knob" class="knob"></div>'
                 f'<div id="{i}-read" class="read" style="font-size:{self.S(40):.1f}px"></div></div>'
                 f'<div id="{i}-pv" class="pvobj" style="width:{pvs:.1f}px;height:{pvs:.1f}px"></div>',
                 id=i, track=[x0, cy, w], span=d.get("span", 4.0), v0=d.get("v0", 0.0), pv=pv)

    def nodes(self, d, T, end):
        labels, step = d["labels"], d.get("step", 1.0)
        bx, by, bw, bh = self.band
        a0, a1 = pick(d, "area", self.fmtname, [0.27, 0.93])
        n = len(labels)
        tall = bh * (a1 - a0) > bw * 0.6
        if tall:  # stack in a column on vertical frames, a row on wide ones
            w, h = self.S(d.get("w", 600)), self.S(d.get("h", 118))
            ys = [by + bh * (a0 + (a1 - a0) * j / (n - 1)) for j in range(n)]
            rects = [(bx + bw / 2, y, w, h) for y in ys]
        else:
            gap = self.S(40)
            w = (bw - gap * (n - 1)) / n
            h = self.S(d.get("h", 118))
            y = by + bh * (a0 + a1) / 2
            rects = [(bx + w / 2 + j * (w + gap), y, w, h) for j in range(n)]
        name = d.get("name", "nodes")
        for j, (lab, r) in enumerate(zip(labels, rects)):
            self.anchors[f"{name}.{j}"] = r
            t0 = T(d["at"] + j * step)
            i = self.nid("nd")
            self.add("fade", t0, T(d.get("until", end)),
                     f'<div id="{i}" class="it node" style="left:{r[0] - r[2] / 2:.1f}px;top:{r[1] - r[3] / 2:.1f}px;width:{r[2]:.1f}px;'
                     f'height:{r[3]:.1f}px;border-radius:{r[3] / 2:.1f}px"></div>', id=i, scaleIn=0.92, under=True)
            li = self.nid("nl")
            self.add("fade", t0 + 0.08, T(d.get("until", end)), f'<div id="{li}" class="it nodelab" style="left:{r[0]:.1f}px;'
                     f'top:{r[1]:.1f}px;font-size:{self.S(d.get("size", 48)):.1f}px">{html.escape(lab)}</div>', id=li)
            if j:
                p = rects[j - 1]
                li = self.nid("ln")
                if tall:
                    y0, y1 = p[1] + p[3] / 2, r[1] - r[3] / 2
                    st = f"left:{r[0] - 1.5:.1f}px;top:{y0:.1f}px;width:3px;height:{y1 - y0:.1f}px;transform-origin:50% 0"
                else:
                    x0, x1 = p[0] + p[2] / 2, r[0] - r[2] / 2
                    st = f"left:{x0:.1f}px;top:{r[1] - 1.5:.1f}px;width:{x1 - x0:.1f}px;height:3px;transform-origin:0 50%"
                self.add("line", t0 - 0.2, T(d.get("until", end)), f'<div id="{li}" class="it link" style="{st}"></div>',
                         id=li, vertical=tall, under=True)

    def tabs(self, d, T, end):
        t0, t1 = T(d["at"]), T(d.get("until", end))
        cx, cy = self.P(pick(d, "pos", self.fmtname), t0)
        w, h = self.S(d.get("w", 900)), self.S(d.get("h", 150))
        n = len(d["labels"])
        pad = self.S(12)
        tw = (w - 2 * pad) / n
        i = self.nid("tb")
        self.add("fade", t0, t1, f'<div id="{i}" class="it tabs" style="left:{cx - w / 2:.1f}px;top:{cy - h / 2:.1f}px;width:{w:.1f}px;'
                 f'height:{h:.1f}px;border-radius:{h / 2:.1f}px"></div>', id=i, scaleIn=0.96, under=True)
        for j, lab in enumerate(d["labels"]):
            x = cx - w / 2 + pad + tw * (j + 0.5)
            self.anchors[f"{d.get('name', 'tabs')}.{j}"] = (x, cy, tw, h - 2 * pad)
            li = self.nid("tl")
            self.add("fade", t0 + 0.1 + j * 0.06, t1, f'<div id="{li}" class="it tablab" style="left:{x:.1f}px;top:{cy:.1f}px;'
                     f'font-size:{self.S(d.get("size", 50)):.1f}px">{html.escape(lab)}</div>', id=li)

    def frames(self, d, T, end):
        specs = d["items"]
        cx, cy = self.P(pick(d, "pos", self.fmtname), T(d["at"]))
        hmax = self.S(d.get("h", 338))
        sizes = []
        for s in specs:
            aw, ah = (float(v) for v in s["ar"].split(":"))
            k = min(hmax / ah, self.S(d.get("wmax", 360)) / aw)
            sizes.append((aw * k, ah * k))
        gap = self.S(d.get("gap", 40))
        total = sum(w for w, _ in sizes) + gap * (len(sizes) - 1)
        x = cx - total / 2
        for j, ((w, h), s) in enumerate(zip(sizes, specs)):
            r = (x + w / 2, cy, w, h)
            self.anchors[f"{d.get('name', 'frames')}.{j}"] = r
            t0 = T(d["at"] + j * d.get("step", 1.0))
            i = self.nid("fr")
            self.add("fade", t0, T(d.get("until", end)),
                     f'<div id="{i}" class="it frame{" ghost" if s.get("ghost") else ""}" style="left:{x:.1f}px;top:{cy - h / 2:.1f}px;'
                     f'width:{w:.1f}px;height:{h:.1f}px;border-radius:{self.S(18):.1f}px">'
                     f'<span style="font-size:{self.S(34):.1f}px;top:{h + self.S(22):.1f}px">{html.escape(s["label"])}</span></div>',
                     id=i, scaleIn=0.9, under=True)
            x += w + gap

    def logo(self, d, T, end):
        t0, t1 = T(d["at"]), T(d.get("until", end))
        cx, cy = self.P(pick(d, "pos", self.fmtname), t0)
        w = self.S(d.get("width", 560))
        i = self.nid("lg")
        self.add("fade", t0, t1, f'<img id="{i}" class="it logo" src="assets/logo.svg" alt="logo" '
                 f'style="left:{cx - w / 2:.1f}px;top:{cy - w * 150 / 384 / 2:.1f}px;width:{w:.1f}px">', id=i, scaleIn=0.94, inDur=0.4)

    def footage(self, d, T, end):
        """Real footage plays inside the hero shape. Video is cut to the segment; its sound goes to the bed."""
        t0, t1 = T(d["at"]), T(d.get("until", end))
        i = self.nid("v")
        fx, fy = d.get("focus", [0.5, 0.5])
        self.foot.append(dict(id=i, file=d["file"], src=d["src"], t0=t0, dur=t1 - t0, crop=d.get("crop"), vf=d.get("vf"), vol=d.get("vol", 0.3)))
        self.hero_html.append(f'<div id="{i}w" class="footwrap"><video id="{i}" class="clip foot" src="assets/foot/{i}.mp4" data-start="{t0:.3f}" '
                              f'data-duration="{t1 - t0:.3f}" data-track-index="{60 + len(self.foot)}" muted playsinline '
                              f'style="object-position:{fx * 100:.0f}% {fy * 100:.0f}%"></video></div>')
        if d.get("zoom"):  # punch-ins, absolute times: [[t, scale], ...]
            keys = [dict(t=t0 - 0.01, s=1.0)] + [dict(t=round(z[0], 3), s=z[1]) for z in d["zoom"]]
            self.items.append(dict(kind="zoom", id=i + "w", keys=keys, **{"in": t0, "out": t1}))

    def keys(self, d, T, end):
        t0, t1 = T(d["at"]), T(d.get("until", end))
        cx, cy = self.P(pick(d, "pos", self.fmtname), t0)
        k, g = self.S(d.get("size", 104)), self.S(14)
        spots = {"W": (cx, cy - k - g), "A": (cx - k - g, cy), "S": (cx, cy), "D": (cx + k + g, cy)}
        for lab, (x, y) in spots.items():
            box = f'left:{x - k / 2:.1f}px;top:{y - k / 2:.1f}px;width:{k:.1f}px;height:{k:.1f}px;border-radius:{k * 0.2:.1f}px;font-size:{k * 0.42:.1f}px'
            i = self.nid("k")
            self.add("fade", t0 + 0.04 * "WASD".index(lab), t1, f'<div id="{i}" class="it key" style="{box}">{lab}</div>', id=i, scaleIn=0.85)
            for pt, pl in d.get("presses", []):
                if pl != lab:
                    continue
                j = self.nid("kp")
                self.add("fade", T(pt), T(pt) + 0.3, f'<div id="{j}" class="it key on" style="{box};z-index:3">{lab}</div>', id=j, inDur=0.05)
                self.sfx.append((T(pt), "key-press", 0.5))

    def wave(self, d, T, end):
        t0, t1 = T(d["at"]), T(d.get("until", end))
        cx, cy = self.P(pick(d, "pos", self.fmtname), t0)
        w, h = self.S(d.get("w", 560)), self.S(d.get("h", 110))
        i = self.nid("wv")
        bars = "".join('<div class="bar"></div>' for _ in range(d.get("bars", 9)))
        it = self.add("wave", t0, t1, f'<div id="{i}" class="it wave" style="left:{cx - w / 2:.1f}px;top:{cy - h / 2:.1f}px;width:{w:.1f}px;'
                      f'height:{h:.1f}px;font-size:{self.S(d.get("size", 34)):.1f}px"><span class="lab">{html.escape(d.get("label", ""))}</span>{bars}</div>',
                      id=i, env=[], env0=t0)
        self.waves.append(it)

    def chip(self, d, T, end):
        """A typed prompt in a pill, with an enter key that gets pressed."""
        t0, t1 = T(d["at"]), T(d.get("until", end))
        cx, cy = self.P(pick(d, "pos", self.fmtname), t0)
        w, h = self.S(d.get("w", 940)), self.S(d.get("h", 120))
        size = self.S(d.get("size", 40))
        i = self.nid("cb")
        self.add("fade", t0, t1, f'<div id="{i}" class="it chipbox" style="left:{cx - w / 2:.1f}px;top:{cy - h / 2:.1f}px;width:{w:.1f}px;'
                 f'height:{h:.1f}px;border-radius:{h / 2:.1f}px"></div>', id=i, scaleIn=0.94)
        self.code(dict(lines=[d["text"]], at=d["type_at"], until=d.get("until", end), size=d.get("size", 40), cps=d.get("cps", 24),
                       plain=True, xy=(cx - w / 2 + h * 0.42, cy - size * 0.78)), T, end)
        k = h * 0.72
        ex = cx + w / 2 - h * 0.14 - k
        box = f'left:{ex:.1f}px;top:{cy - k / 2:.1f}px;width:{k:.1f}px;height:{k:.1f}px;border-radius:50%;font-size:{k * 0.46:.1f}px'
        j = self.nid("ce")
        self.add("fade", t0 + 0.1, t1, f'<div id="{j}" class="it key" style="{box}">&#8629;</div>', id=j)
        if d.get("enter") is not None:
            e = self.nid("cp")
            self.add("fade", T(d["enter"]), t1, f'<div id="{e}" class="it key on" style="{box};z-index:3">&#8629;</div>', id=e, inDur=0.05)
            self.sfx.append((T(d["enter"]), "click", 0.6))

    def flash(self, d, T, end):
        i = self.nid("fl")
        self.add("flash", T(d["at"]), T(d["at"]) + 0.2, f'<div id="{i}" class="it flash" style="opacity:0;background:{d.get("color", "#fff")}"></div>', id=i)

    def img(self, d, T, end):
        t0, t1 = T(d["at"]), T(d.get("until", end))
        cx, cy = self.P(pick(d, "pos", self.fmtname), t0)
        w = self.S(d.get("w", 160))
        h = self.S(d.get("h", d.get("w", 160)))
        name = os.path.basename(d["src"])
        self.assets.append((d["src"], name))
        i = self.nid("im")
        self.add("fade", t0, t1, f'<img id="{i}" class="it {d.get("cls", "")}" src="assets/{name}" alt="" style="left:{cx - w / 2:.1f}px;'
                 f'top:{cy - h / 2:.1f}px;width:{w:.1f}px;height:{h:.1f}px">', id=i, scaleIn=d.get("scaleIn", 0.9))

    def shake(self, d, T, end):
        """Camera shake: the whole frame jolts and settles (pure function of t, no randomness)."""
        t0 = T(d["at"])
        self.items.append(dict(kind="shake", id=self.nid("sh"), amp=self.S(d.get("amp", 22)), decay=d.get("decay", 9.0),
                               rot=d.get("rot", 0.6), **{"in": round(t0, 4), "out": round(t0 + d.get("dur", 0.55), 4)}))

    def rings(self, d, T, end):
        """Sound rings: n circles grow out of one point, one after another (a beep you can see)."""
        t0, t1 = T(d["at"]), T(d.get("until", end))
        cx, cy = self.P(pick(d, "pos", self.fmtname), t0)
        i = self.nid("rg")
        n = d.get("n", 4)
        rings = "".join('<div class="ring"></div>' for _ in range(n))
        self.add("rings", t0, t1, f'<div id="{i}" class="it rings" style="left:{cx:.1f}px;top:{cy:.1f}px">{rings}</div>', id=i,
                 gap=d.get("gap", 0.16), life=d.get("life", 0.9), rmax=self.S(d.get("r", 420)), sw=self.S(d.get("sw", 10)),
                 bursts=[round(T(b), 3) for b in d.get("bursts", [d["at"]])])

    def box(self, d, T, end):
        """A plain panel (profile card, backing plate) under the hero."""
        t0, t1 = T(d["at"]), T(d.get("until", end))
        cx, cy = self.P(pick(d, "pos", self.fmtname), t0)
        w, h = self.S(d["w"]), self.S(d["h"])
        i = self.nid("bx")
        self.add("fade", t0, t1, f'<div id="{i}" class="it {d.get("cls", "card")}" style="left:{cx - w / 2:.1f}px;top:{cy - h / 2:.1f}px;'
                 f'width:{w:.1f}px;height:{h:.1f}px;border-radius:{self.S(d.get("r", 40)):.1f}px"></div>', id=i, scaleIn=0.96, under=True)

    def dim(self, d, T, end):
        t0, t1 = T(d["at"]), T(d.get("until", end))
        k = self.hero_at(t0)
        i = self.nid("dm")
        self.add("fade", t0, t1, f'<div id="{i}" class="it dim" style="left:{k["l"]:.1f}px;top:{k["tp"]:.1f}px;width:{k["r"] - k["l"]:.1f}px;'
                 f'height:{k["b"] - k["tp"]:.1f}px;border-radius:{k["rad"]:.1f}px;opacity:0"></div>', id=i, inDur=0.35)

    # ----- hero / cursor / camera -----
    def hero_key(self, d, t):
        c = self.brand
        if d.get("full"):
            cx, cy, w, h = self.f["W"] / 2, self.f["H"] / 2, self.f["W"], self.f["H"]
        elif "rect" in d:
            cx, cy, w, h = self.anchors[d["rect"]]
            g = self.S(d.get("grow", 0))
            w, h = w + g, h + g
            if "w" in d:
                w = self.S(d["w"])
            if "h" in d:
                h = self.S(d["h"])
        else:
            cx, cy = self.P(pick(d, "pos", self.fmtname), t)
            w, h = self.S(pick(d, "w", self.fmtname)), self.S(pick(d, "h", self.fmtname))
        k = dict(t=round(t, 4), l=cx - w / 2, r=cx + w / 2, tp=cy - h / 2, b=cy + h / 2, c=[cx, cy],
                 rad=0 if d.get("full") else self.S(d.get("r", min(w, h) / 2 / self.f["s"])), fill=hexa(d.get("fill", "accent"), c),
                 stroke=hexa(d.get("stroke", "none"), c), sw=self.S(d.get("sw", 0)))
        if "lead" in d:
            k["lead"], k["trail"] = d["lead"], d["trail"]
        self.hero.append(k)
        if d.get("whoosh"):
            self.sfx.append((t + 0.1, d["whoosh"] if isinstance(d["whoosh"], str) else "whoosh", None))

    def cursor_steps(self, steps, T, start, end):
        bx, by, bw, bh = self.band
        entry = (bx + bw * 0.92, by + bh * 1.08)
        self.cur.append(dict(t=round(start, 4), x=entry[0], y=entry[1]))
        first = T(steps[0]["at"])
        self.show.append([first - 0.1, end - 0.05])
        down = None
        for n, s in enumerate(steps):
            t = T(s["at"])
            x, y = self.P(s["to"], t)
            if s.get("frac") is not None:  # a point along an anchor's width (scrub track)
                a = self.anchors[s["to"][7:]]
                x, y = a[0] + a[2] * s["frac"], a[1]
            self.cur.append(dict(t=round(t, 4), x=x + self.S(s.get("dx", 0)), y=y + self.S(s.get("dy", 0))))
            pt = t + s.get("arrive", 0.45)
            if s.get("press") == "click":
                self.clicks.append(round(pt, 4))
                self.sfx.append((pt, "click" if n % 2 == 0 else "click-b", None))
            elif s.get("press") == "down":
                down = pt
                self.sfx.append((pt, "click", 0.4))
            elif s.get("press") == "up" and down is not None:
                self.holds.append([round(down, 4), round(pt, 4)])
                self.sfx.append((pt, "click-b", 0.35))
                down = None

    # ----- assemble -----
    def run(self):
        t = 0.0
        for sid, sc in self.seq:
            start, beats = t, sc["beats"]
            end = start + beats * self.spb
            T = (lambda s0: (lambda b: s0 + b * self.spb))(start)
            self.cur_html, self.cur_under = [], []
            self.set_bands(sid, sc)
            # anchors first (components lay out), then hero keys that point at them, then content
            order = sorted(sc.get("items", []), key=lambda d: 0 if d["kind"] in ("nodes", "tabs", "frames", "scrub") else 1)
            heros = sc.get("hero", [])
            heros = heros if isinstance(heros, list) else [heros]
            for d in heros:
                if "rect" not in d:
                    self.hero_key(d, T(d["at"]))
            self.hero.sort(key=lambda k: k["t"])
            for d in order:
                if d["kind"] in ("nodes", "tabs", "frames"):
                    getattr(self, d["kind"])(d, T, beats)
            for d in heros:
                if "rect" in d:
                    self.hero_key(d, T(d["at"]))
            self.hero.sort(key=lambda k: k["t"])
            for d in order:
                if d["kind"] not in ("nodes", "tabs", "frames"):  # footage, text, code, chips...
                    getattr(self, d["kind"])(d, T, beats)
            if sc.get("cursor"):
                self.cursor_steps(sc["cursor"], T, start, end)
            for k in sc.get("cam", []):
                self.cam.append(dict(t=T(k["at"]), s=k.get("s", 1), x=self.S(k.get("x", 0)), y=self.S(k.get("y", 0))))
            for s in sc.get("sfx", []):
                self.sfx.append((T(s["at"]), s["sfx"], s.get("vol")))
            self.scenes.append(dict(id=sid, start=round(start, 3), end=round(end, 3), html=self.cur_html, under=self.cur_under))
            t = end
        self.dur = round(t, 3)
        return self

    def media(self, out):
        """Cut each footage segment to H.264 (cached) and mix the segments' own sound into one bed."""
        import numpy as np, wave
        os.makedirs(os.path.join(out, "assets", "foot"), exist_ok=True)
        cache = os.path.join(self.cdir, ".cache")
        os.makedirs(cache, exist_ok=True)
        bed = np.zeros(int(self.dur * 48000) + 48000, dtype=np.float64)
        for f in self.foot:
            src = os.path.join(self.cdir, f["file"])
            if not os.path.exists(src):
                sys.exit(f"missing footage {f['file']} (media lives in R2): venv/bin/python motion-studio/tools/studio.py assets pull --only "
                         f"{os.path.relpath(self.cdir, ROOT)}")
            key = hashlib.sha1(json.dumps([f["file"], f["src"], round(f["dur"], 3), f["crop"], f["vf"]]).encode()).hexdigest()[:16]
            cut = os.path.join(cache, key + ".mp4")
            if not os.path.exists(cut):
                vf = ([f["vf"]] if f["vf"] else []) + ["fps=30"] + ([f"crop={f['crop'][2]}:{f['crop'][3]}:{f['crop'][0]}:{f['crop'][1]}"] if f["crop"] else [])
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{f['src']:.3f}", "-t", f"{f['dur'] + 0.1:.3f}", "-i", src, "-an",
                                "-vf", ",".join(vf), "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", cut], check=True)
            shutil.copy(cut, os.path.join(out, "assets", "foot", f["id"] + ".mp4"))
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{f['src']:.3f}", "-t", f"{f['dur']:.3f}", "-i", src, "-vn", "-ac", "1",
                                  "-ar", "48000", "-f", "s16le", "-"], capture_output=True).stdout
            a = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768
            tt = f["t0"] + np.arange(len(a)) / 48000
            v = f["vol"]
            env = np.interp(tt, [p[0] for p in v], [p[1] for p in v]) if isinstance(v, list) else np.full(len(a), float(v))
            n = min(len(a), 4800)  # 0.1 s fades at the cut so segments never click
            env[:n] *= np.linspace(0, 1, n)
            env[-n:] *= np.linspace(1, 0, n)
            o = int(f["t0"] * 48000)
            bed[o:o + len(a)] += (a * env)[: len(bed) - o]
        bed = bed[: int(self.dur * 48000)]
        pk = np.abs(bed).max() or 1
        if pk > 0.89:
            bed *= 0.89 / pk
        with wave.open(os.path.join(out, "assets", "bed.wav"), "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(48000)
            w.writeframes((bed * 32767).astype(np.int16).tobytes())
        return bed

    def write(self, out, cid):
        os.makedirs(os.path.join(out, "assets", "sfx"), exist_ok=True)
        shutil.copy(os.path.join(ROOT, self.brand["logo"]), os.path.join(out, "assets", "logo.svg"))
        for src, name in self.assets:
            shutil.copy(os.path.join(ROOT, src), os.path.join(out, "assets", name))
        f, col = self.f, self.brand["colors"]
        # audio: every effect's measured peak lands one frame after its picture event
        audio, used = [], {}
        fr = 1 / self.c["fps"]
        for n, (ev, name, vol) in enumerate(sorted(self.sfx)):
            src = os.path.join(ROOT, "engine", "sfx", name + ".mp3")
            if not os.path.exists(src):
                sys.exit(f"missing engine/sfx/{name}.mp3 (media lives in R2): venv/bin/python motion-studio/tools/studio.py assets pull --only engine/sfx")
            if name not in used:
                shutil.copy(src, os.path.join(out, "assets", "sfx", name + ".mp3"))
                used[name] = 1
            pk, ln = peak_and_len(src)
            st = max(0.0, ev + fr - pk)
            ln = min(ln, self.dur - st)
            if ln <= 0.05:
                continue
            audio.append(f'<audio id="sfx{n:03d}" src="assets/sfx/{name}.mp3" data-start="{st:.3f}" data-duration="{ln:.3f}" '
                         f'data-track-index="{40 + n}" data-volume="{vol if vol is not None else SFX_VOL.get(name, 0.4)}"></audio>')
        if self.foot:
            bed = self.media(out)
            audio.insert(0, f'<audio id="bed" src="assets/bed.wav" data-start="0" data-duration="{self.dur}" data-track-index="31" data-volume="1"></audio>')
            for it in self.waves:
                a, b = int(it["in"] * 48000), int(it["out"] * 48000)
                hop = 48000 // self.c["fps"]
                seg = bed[a:b]
                rms = [float((seg[j:j + hop] ** 2).mean() ** 0.5) for j in range(0, max(1, len(seg) - hop), hop)]
                ref = sorted(rms)[int(len(rms) * 0.95)] if rms else 1
                it["env"] = [round(min(1.0, r / (ref or 1)), 3) for r in rms]
        vo = self.c.get("voice")
        if vo:
            shutil.copy(os.path.join(self.cdir, vo["file"]), os.path.join(out, "assets", "voice" + os.path.splitext(vo["file"])[1]))
            audio.insert(0, f'<audio id="voice" src="assets/voice{os.path.splitext(vo["file"])[1]}" data-start="0" '
                            f'data-duration="{min(self.dur, vo.get("dur", self.dur)):.3f}" data-track-index="29" data-volume="{vo.get("volume", 1)}"></audio>')
        mus = self.c.get("music")
        if mus and mus.get("file"):
            shutil.copy(os.path.join(self.cdir, mus["file"]), os.path.join(out, "assets", "music" + os.path.splitext(mus["file"])[1]))
            audio.insert(0, f'<audio id="music" src="assets/music{os.path.splitext(mus["file"])[1]}" data-start="0" '
                            f'data-duration="{self.dur}" data-track-index="30" data-volume="{mus.get("volume", 0.8)}"></audio>')
        scenes, unders = [], []
        for n, s in enumerate(self.scenes):
            a = max(0.0, s["start"] - 0.6)
            b = min(self.dur, s["end"] + 0.6)
            span = f'data-start="{a:.3f}" data-duration="{b - a:.3f}"'
            scenes.append(f'<div id="sc-{s["id"]}" class="clip scene over" {span} data-track-index="{1 + n % 2}">\n'
                          + "\n".join(s["html"]) + "\n</div>")
            if s["under"]:
                unders.append(f'<div id="sc-{s["id"]}-u" class="clip scene under" {span} data-track-index="{3 + n % 2}">\n'
                              + "\n".join(s["under"]) + "\n</div>")
        data = dict(id=cid, dur=self.dur, fps=self.c["fps"], W=f["W"], H=f["H"],
                    hero=dict(keys=self.hero, zeta=0.82, lead=[0.78, 2.6], trail=[0.86, 1.7]),
                    cursor=dict(keys=self.cur, clicks=self.clicks, holds=self.holds, show=self.show),
                    cam=self.cam, items=self.items)
        css = open(os.path.join(ROOT, "engine", "style.css")).read()
        runtime = open(os.path.join(ROOT, "engine", "runtime.js")).read()  # inline, so check sees the timeline registry
        doc = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={f["W"]}, height={f["H"]}">
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
:root {{ --bg:{col["bg"]}; --panel:{col["panel"]}; --line:{col["line"]}; --ink:{col["ink"]}; --mute:{col["mute"]};
  --paper:{col["paper"]}; --accent:{col["accent"]}; --accent-ink:{col["accentInk"]};
  --sans:"Inter",sans-serif; --mono:"JetBrains Mono",monospace; --u:{f["s"]}; --W:{f["W"]}px; --H:{f["H"]}px; }}
html, body {{ margin:0; width:{f["W"]}px; height:{f["H"]}px; overflow:hidden; background:var(--bg); }}
{css}
</style>
</head>
<body>
<div id="root" data-composition-id="{cid}" data-start="0" data-duration="{self.dur}" data-width="{f["W"]}" data-height="{f["H"]}"
  data-fps="{self.c["fps"]}" data-motion-blur="on" data-motion-blur-events="on" data-layout-allow-overlap>
<div id="ground"></div>
<div id="cam">
{chr(10).join(unders)}
<div id="hero" data-motion-blur="off">{"".join(self.hero_html)}</div>
{chr(10).join(scenes)}
<svg id="cursor" viewBox="0 0 28 34" width="{self.S(56):.0f}" height="{self.S(68):.0f}"><path d="M2 2 L2 27 L8.6 21 L13 31.5 L17.6 29.6 L13.3 19.6 L22.5 19.6 Z" fill="#fff" stroke="#0A0A0B" stroke-width="2" stroke-linejoin="round"/></svg>
</div>
{chr(10).join(audio)}
</div>
<script>window.IM_DATA = {json.dumps(data, separators=(",", ":"))};</script>
<script>
{runtime}
</script>
</body>
</html>
'''
        open(os.path.join(out, "index.html"), "w").write(doc)
        return dict(dur=self.dur, scenes=[{k: s[k] for k in ("id", "start", "end")} for s in self.scenes],
                    sfx=len(audio))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("campaign")
    ap.add_argument("--hooks"), ap.add_argument("--formats"), ap.add_argument("--ctas")
    a = ap.parse_args()
    camp_path = os.path.abspath(a.campaign)
    camp = json.load(open(camp_path))
    brand = json.load(open(os.path.join(ROOT, "brand", "brand.json")))
    errs = validate.check(camp, camp_path, brand, FORMATS)
    if errs:
        print("campaign rejected:\n  " + "\n  ".join(errs))
        sys.exit(1)
    hooks = a.hooks.split(",") if a.hooks else list(camp["hooks"])
    fmts = a.formats.split(",") if a.formats else camp["formats"]
    ctas = a.ctas.split(",") if a.ctas else list(camp["ctas"])
    base = os.path.join(os.path.dirname(camp_path), "build")
    digest = hashlib.sha256(open(camp_path, "rb").read()).hexdigest()[:12]
    manifest = dict(campaign=camp["id"], campaign_sha=digest, template=TEMPLATE_VERSION, bpm=camp["bpm"], fps=camp["fps"], variants=[])
    for h in hooks:
        for fm in fmts:
            for ct in ctas:
                vid = f'{camp["id"]}_{h}_{FORMATS[fm]["slug"]}_{ct}'
                out = os.path.join(base, vid)
                b = Build(camp, brand, fm, h, ct)
                b.cdir = os.path.dirname(camp_path)
                info = b.run().write(out, vid)
                manifest["variants"].append(dict(id=vid, hook=h, format=fm, cta=ct, dir=os.path.relpath(out, ROOT), **info))
                print(f"built {vid}  {info['dur']}s  {info['sfx']} sfx")
    json.dump(manifest, open(os.path.join(base, "build_manifest.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
