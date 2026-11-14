"""Reject a bad campaign before any render: missing assets, lines too long for the frame, numbers or claims
that no approved source backs up, and scenes that run past their own length."""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAR_W = {"sans": 0.56, "mono": 0.61}  # average advance per character, in em, for bold Inter / JetBrains Mono
MAX_WORDS = {"9:16": 5, "1:1": 6, "16:9": 8}  # words per line on screen for a claim
NUM = r"(?<![A-Za-z])\d+(?:\.\d+)?(?![A-Za-z])"  # standalone numbers, not the 4 in MP4


def _texts(scene):
    for d in scene.get("items", []):
        if d["kind"] == "text":
            yield d, d["text"]
        elif d["kind"] in ("nodes", "tabs"):
            for l in d["labels"]:
                yield d, l


def check(camp, camp_path, brand, formats):
    errs = []
    base = os.path.dirname(camp_path)
    for k in ("id", "bpm", "fps", "hooks", "body", "ctas", "formats"):
        if k not in camp:
            errs.append(f"missing field: {k}")
    if errs:
        return errs
    for f in camp["formats"]:
        if f not in formats:
            errs.append(f"unknown format {f}")
    if not os.path.exists(os.path.join(ROOT, brand["logo"])):
        errs.append(f"logo missing: {brand['logo']}")
    mus = camp.get("music") or {}
    if mus.get("file") and not os.path.exists(os.path.join(base, mus["file"])):
        errs.append(f"music missing: {mus['file']}")

    # approved claims: every number on screen must appear in a claim whose quote is found in its source file
    sources = {}
    for sid, s in camp.get("sources", {}).items():
        p = os.path.join(base, s["file"])
        if not os.path.exists(p):
            errs.append(f"source {sid} missing: {s['file']}")
            continue
        sources[sid] = open(p).read()
    approved = []
    for c in camp.get("claims", []):
        if c["source"] not in sources:
            errs.append(f"claim '{c['text']}' cites unknown source {c['source']}")
        elif c["quote"] not in sources[c["source"]]:
            errs.append(f"claim '{c['text']}': quote not found in source {c['source']}")
        else:
            approved.append(c)
    allowed_nums = set()
    for c in approved:
        allowed_nums |= set(re.findall(NUM, c["text"]))
    allowed_nums |= set(str(n) for n in camp.get("free_numbers", []))

    scenes = [("hook " + k, v) for k, v in camp["hooks"].items()] + [(s["id"], s) for s in camp["body"]] + \
             [("cta " + k, v) for k, v in camp["ctas"].items()]
    for name, sc in scenes:
        beats = sc.get("beats", 0)
        if beats <= 0:
            errs.append(f"{name}: beats must be > 0")
        for d in sc.get("items", []):
            for key in ("at", "until"):
                if key in d and not 0 <= d[key] <= beats:
                    errs.append(f"{name}: {d['kind']} {key}={d[key]} is outside the scene's {beats} beats")
        for d, txt in _texts(sc):
            plain = txt.replace("*", "")
            for n in re.findall(NUM, plain):
                if n not in allowed_nums:
                    errs.append(f"{name}: number '{n}' in \"{plain}\" is not in any approved claim")
            for fmt in camp["formats"]:
                fm = formats[fmt]
                size = d.get(f"size@{fmt}", d.get("size", 72)) * fm["s"]
                font = "mono" if d.get("font") == "mono" or d["kind"] == "nodes" else "sans"
                lines = d.get(f"text@{fmt}", txt).replace("*", "").split("\n") if d["kind"] == "text" else [txt]
                for line in lines:
                    width = len(line) * CHAR_W[font] * size
                    limit = fm["band"][2] if d["kind"] == "text" else fm["band"][2] / max(1, len(d["labels"])) * (
                        1 if d["kind"] == "tabs" else len(d["labels"]))
                    if d["kind"] == "text" and width > limit:
                        errs.append(f"{name} [{fmt}]: \"{line}\" is ~{width:.0f}px wide, band is {limit}px; cut words")
                    nw = len([w for w in line.split() if re.search(r"\w", w)])
                    if d["kind"] == "text" and nw > MAX_WORDS[fmt] + 2:
                        errs.append(f"{name} [{fmt}]: \"{line}\" has {nw} words on one line")
    cta_txt = [t for _, sc in [(k, v) for k, v in camp["ctas"].items()] for _, t in _texts(sc)]
    for t in cta_txt:
        for line in t.replace("*", "").split("\n"):
            if len(line) > 32:
                errs.append(f"CTA line too long ({len(line)} chars): {line}")
    return errs
