#!/usr/bin/env python3
"""Motion Studio: one command for every stage, brief to delivered links.

  venv/bin/python motion-studio/tools/studio.py doctor
  venv/bin/python motion-studio/tools/studio.py new <id> [--from seek-t] [--title "..."]
  venv/bin/python motion-studio/tools/studio.py validate <id>
  venv/bin/python motion-studio/tools/studio.py build <id> [--hooks A] [--formats 9:16] [--ctas A]
  venv/bin/python motion-studio/tools/studio.py check <id> [--variant <vid>]
  venv/bin/python motion-studio/tools/studio.py snapshot <id> --variant <vid> --at 0.5,4,8.2
  venv/bin/python motion-studio/tools/studio.py render <id> [--only <vid,...>] [--workers 2]
  venv/bin/python motion-studio/tools/studio.py status <id>
  venv/bin/python motion-studio/tools/studio.py deliver <id> --hero <vid> [--extra thumb.png caption.txt]
  venv/bin/python motion-studio/tools/studio.py assets status|lock|push|pull [--only <prefix>]

<id> is a folder name under motion-studio/campaigns/ or a path to one. Each stage is a thin wrapper around
the tool that does the work (validate.py, build.py, render.py, qa.py, deliver.py, assets.py), so those keep
working on their own. Stages never spend money; deliver uploads to R2 (the owner's bucket) and nothing else.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
HF_VERSION = "0.8.210"
HF = ["npx", "-y", f"hyperframes@{HF_VERSION}"]
PY = sys.executable


def campaign_dir(ref: str) -> Path:
    p = Path(ref)
    if (p / "campaign.json").exists():
        return p.resolve()
    p = ROOT / "campaigns" / ref
    if (p / "campaign.json").exists():
        return p
    known = ", ".join(sorted(d.name for d in (ROOT / "campaigns").iterdir() if (d / "campaign.json").exists()))
    sys.exit(f"no campaign '{ref}' (known: {known})")


def run(cmd: list[str], cwd: Path | None = None) -> int:
    print("$", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], cwd=cwd).returncode


def variants(cdir: Path, only: str | None = None) -> list[Path]:
    man = cdir / "build" / "build_manifest.json"
    if not man.exists():
        sys.exit(f"nothing built yet for {cdir.name}: run `studio.py build {cdir.name}` first")
    ids = [v["id"] for v in json.loads(man.read_text())["variants"]]
    if only:
        want = set(only.split(","))
        missing = want - set(ids)
        if missing:
            sys.exit(f"not built: {', '.join(sorted(missing))}")
        ids = [i for i in ids if i in want]
    return [cdir / "build" / i for i in ids]


# ---- stages -------------------------------------------------------------------------------------------

def doctor(_a) -> int:
    ok = True

    def line(good: bool, what: str, fix: str = "") -> None:
        nonlocal ok
        ok &= good
        print(f"{'ok  ' if good else 'FAIL'} {what}" + ("" if good or not fix else f"\n     fix: {fix}"))

    for mod in ("numpy", "PIL", "boto3"):
        line(importlib.util.find_spec(mod) is not None, f"python module {mod}",
             "run with the repo venv (venv/bin/python), or pip install -r requirements.txt")
    for exe in ("ffmpeg", "ffprobe", "node", "npx"):
        line(shutil.which(exe) is not None, f"{exe} on PATH", "install it (ffmpeg via apt/brew, node >= 20)")
    if shutil.which("node"):
        v = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip()
        m = re.match(r"v(\d+)", v)
        line(bool(m) and int(m.group(1)) >= 20, f"node {v} (HyperFrames needs >= 20)", "upgrade node")
    for f in ("engine/runtime.js", "engine/style.css", "brand/brand.json"):
        line((ROOT / f).exists(), f)
    brand = json.loads((ROOT / "brand" / "brand.json").read_text())
    line((ROOT / brand["logo"]).exists(), f"brand logo {brand['logo']}")
    sys.path.insert(0, str(TOOLS))
    import build  # noqa: PLC0415
    sfx = ROOT / "engine" / "sfx"
    missing = [n for n in build.SFX_VOL if not (sfx / f"{n}.mp3").exists()]
    line(not missing, f"engine SFX ({len(build.SFX_VOL) - len(missing)}/{len(build.SFX_VOL)})",
         "venv/bin/python motion-studio/tools/studio.py assets pull --only engine/sfx")
    env = ROOT.parent / ".env"
    have = env.exists() and all(re.search(rf"^{k}=", env.read_text(), re.M) for k in ("R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"))
    line(have, "R2 credentials in repo .env (needed for assets push/pull and deliver)", "copy .env from the laptop; never commit it")
    print("\nall good" if ok else "\nfix the FAIL lines, then run doctor again")
    return 0 if ok else 1


def new(a) -> int:
    src = campaign_dir(a.template)
    dst = ROOT / "campaigns" / a.id
    if dst.exists():
        sys.exit(f"{dst.relative_to(ROOT)} already exists")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", a.id):
        sys.exit("campaign id: lowercase letters, digits and dashes")
    camp = json.loads((src / "campaign.json").read_text())
    camp["id"] = a.id
    camp["title"] = a.title or a.id.replace("-", " ").title()
    (dst / "sources").mkdir(parents=True)
    (dst / "footage").mkdir()
    (dst / "audio").mkdir()
    (dst / "campaign.json").write_text(json.dumps(camp, indent=1, ensure_ascii=False) + "\n")
    (dst / "sources" / "notes.md").write_text(
        f"# Sources for {camp['title']}\n\n"
        "Paste the exact sentences every on-screen number or claim rests on, with the URL above each block.\n"
        "validate.py rejects any number on screen that no claim quote below backs up.\n\n"
        f"<!-- copied from {src.name}: replace every quote, then update `claims` in campaign.json -->\n"
        + (src / "sources" / "notes.md").read_text())
    (dst / "PLAN.md").write_text(
        f"# {camp['title']}: plan (draft for the owner)\n\n"
        "**Idea:** one sentence.\n\n"
        "| # | Beats | Voiceover / on-screen line | Hero shape becomes | Cursor / camera | Sound |\n"
        "|---|---|---|---|---|---|\n| 1 Hook | | | | | |\n\n"
        "## Hooks (3-hook test)\n- A (problem):\n- B (result):\n- C (surprising mechanism):\n\n"
        "## CTAs\n- A (Instagram follow):\n- B (YouTube subscribe):\n\n"
        "## Fact check\nEvery line traces to sources/notes.md.\n\n## Music\nSai's 120 BPM track / ElevenLabs Music (ask first) / SFX only\n")
    print(f"created campaigns/{a.id} from {src.name}. Next: write sources/notes.md and PLAN.md, edit campaign.json,\n"
          f"then `studio.py build {a.id} --hooks A --formats 9:16 --ctas A`")
    return 0


def validate(a) -> int:
    cdir = campaign_dir(a.campaign)
    sys.path.insert(0, str(TOOLS))
    import build  # noqa: PLC0415
    import validate as v  # noqa: PLC0415
    camp = json.loads((cdir / "campaign.json").read_text())
    brand = json.loads((ROOT / "brand" / "brand.json").read_text())
    errs = v.check(camp, str(cdir / "campaign.json"), brand, build.FORMATS)
    for e in errs:
        print("  " + e)
    n = len(camp.get("hooks", {})) * len(camp.get("formats", [])) * len(camp.get("ctas", {}))
    print(f"{cdir.name}: {'REJECTED, ' + str(len(errs)) + ' problems' if errs else 'valid'} ({n} variants)")
    return 1 if errs else 0


def build_(a) -> int:
    cdir = campaign_dir(a.campaign)
    cmd = [PY, TOOLS / "build.py", cdir / "campaign.json"]
    for k in ("hooks", "formats", "ctas"):
        if getattr(a, k):
            cmd += [f"--{k}", getattr(a, k)]
    return run(cmd)


def check(a) -> int:
    rc = 0
    for vdir in variants(campaign_dir(a.campaign), a.variant):
        rc |= run(HF + ["check"], cwd=vdir)
    return rc


def snapshot(a) -> int:
    (vdir,) = variants(campaign_dir(a.campaign), a.variant)
    rc = run(HF + ["snapshot", "--at", a.at], cwd=vdir)
    print(f"read the PNGs in {vdir.relative_to(ROOT)}/.hyperframes/artifacts/snapshots/")
    return rc


def render(a) -> int:
    cmd = [PY, TOOLS / "render.py", campaign_dir(a.campaign), "--workers", str(a.workers)]
    if a.only:
        cmd += ["--only", a.only]
    if a.force:
        cmd.append("--force")
    return run(cmd)


def status(a) -> int:
    cdir = campaign_dir(a.campaign)
    camp = json.loads((cdir / "campaign.json").read_text())
    n = len(camp["hooks"]) * len(camp["formats"]) * len(camp["ctas"])
    print(f"{camp['id']}: {camp.get('title', '')}  |  {n} variants planned")
    man = cdir / "build" / "build_manifest.json"
    built = json.loads(man.read_text())["variants"] if man.exists() else []
    dman = cdir / "exports" / "delivery_manifest.json"
    exports = {e["id"]: e for e in json.loads(dman.read_text())["exports"]} if dman.exists() else {}
    print(f"built {len(built)}/{n}  rendered {len(exports)}  QA pass {sum(e.get('qa') == 'pass' for e in exports.values())}")
    for v in built:
        e = exports.get(v["id"])
        review = cdir / "qa" / v["id"] / "REVIEW.md"
        approved = review.exists() and re.search(r"- \[x\] Approved", review.read_text(), re.I)
        qa = "-" if not e else ("pass" if e.get("qa") == "pass" else "QA ISSUES")
        print(f"  {v['id']:28} {v['dur']:>6}s  render:{'yes' if e else 'no ':3}  qa:{qa:9}  approved:{'yes' if approved else 'no'}")
    links = cdir / "exports" / "r2_links.json"
    print("delivered: " + (f"yes ({len(json.loads(links.read_text())['links'])} links in exports/r2_links.json)" if links.exists() else "no"))
    return 0


def deliver(a) -> int:
    cmd = [PY, TOOLS / "deliver.py", campaign_dir(a.campaign)]
    if a.hero:
        cmd += ["--hero", a.hero]
    if a.extra:
        cmd += ["--extra", *a.extra]
    return run(cmd)


def assets(a) -> int:
    return run([PY, TOOLS / "assets.py", *a.rest])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="stage", required=True)
    sub.add_parser("doctor").set_defaults(fn=doctor)
    p = sub.add_parser("new")
    p.add_argument("id")
    p.add_argument("--from", dest="template", default="seek-t")
    p.add_argument("--title")
    p.set_defaults(fn=new)
    for name, fn in (("validate", validate), ("status", status)):
        p = sub.add_parser(name)
        p.add_argument("campaign")
        p.set_defaults(fn=fn)
    p = sub.add_parser("build")
    p.add_argument("campaign")
    p.add_argument("--hooks"), p.add_argument("--formats"), p.add_argument("--ctas")
    p.set_defaults(fn=build_)
    p = sub.add_parser("check")
    p.add_argument("campaign")
    p.add_argument("--variant")
    p.set_defaults(fn=check)
    p = sub.add_parser("snapshot")
    p.add_argument("campaign")
    p.add_argument("--variant", required=True)
    p.add_argument("--at", required=True, help="seconds, comma separated")
    p.set_defaults(fn=snapshot)
    p = sub.add_parser("render")
    p.add_argument("campaign")
    p.add_argument("--only")
    p.add_argument("--workers", type=int, default=2, help="2 on the laptop: 4 ran out of memory")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=render)
    p = sub.add_parser("deliver")
    p.add_argument("campaign")
    p.add_argument("--hero")
    p.add_argument("--extra", nargs="*")
    p.set_defaults(fn=deliver)
    p = sub.add_parser("assets")
    p.add_argument("rest", nargs=argparse.REMAINDER)
    p.set_defaults(fn=assets)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
