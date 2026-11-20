"""`faceless wild-doc ...` - script + audio -> finished wild-doc film. Every command prints JSON.

Fast path:
    faceless wild-doc new my-film --script script.txt --audio voice.wav [--lang hi] [--channel "MY CHANNEL"]
    faceless wild-doc run my-film            # ingest -> transcribe -> align -> draft shot list, then stops for direction
    (direct 02-direction/shotlist.txt, plates.json, picks, graphics.json, style.json - the wild-doc skill does this)
    faceless wild-doc run my-film --yes      # makes missing images/sounds, plan, grade, render, mix, assemble, QA, package
    faceless wild-doc run my-film --auto     # skip direction: render the plates-only draft as is
"""
from __future__ import annotations

import json
from pathlib import Path

from . import WildDocError
from . import align as A
from . import assets as AS
from . import deliver as D
from . import mix as MX
from . import plan as PL
from . import render as R
from . import shotlist as SL
from . import sound as SO
from .project import Project, read_json, write_json


def _print(o) -> None:
    print(json.dumps(o, ensure_ascii=False, indent=1, default=str))


def _proj(ref: str) -> Project:
    from ..config import repo_root

    p = Path(ref).expanduser()
    if (p / "project.json").exists():
        return Project(p)
    q = repo_root() / "projects" / ref
    if (q / "project.json").exists():
        return Project(q)
    raise WildDocError(f"No wild-doc project at {ref!r} (looked in {p} and {q}).")


def add_parser(sub) -> None:
    w = sub.add_parser("wild-doc", help="script + audio -> fast-cut wildlife/natural-history documentary (the 7-iteration client style)")
    ws = w.add_subparsers(dest="wd_cmd", required=True)
    c = ws.add_parser("new", help="start a project from a script and the narration audio")
    c.add_argument("slug")
    c.add_argument("--script", required=True)
    c.add_argument("--audio", required=True)
    c.add_argument("--title", default="")
    c.add_argument("--lang", default="", help="narration language code for transcription, e.g. hi, en, te")
    c.add_argument("--channel", default="", help="channel name for the end card")
    c.add_argument("--root", help="projects folder (default ./projects)")
    c = ws.add_parser("setup", help="one-time: Remotion packages, depth model, SFX kit")
    c.add_argument("--depth", action="store_true", help="download the Depth-Anything-V2-small ONNX model (~100 MB)")
    c.add_argument("--kit", choices=["procedural", "elevenlabs"], help="build the shared SFX kit")
    c.add_argument("--yes", action="store_true")

    def proj(name, helptext):
        x = ws.add_parser(name, help=helptext)
        x.add_argument("project")
        return x

    c = proj("transcribe", "word timings of the narration")
    c.add_argument("--provider", default="auto", choices=["auto", "elevenlabs", "openai", "local"])
    c.add_argument("--yes", action="store_true")
    c = proj("align", "map the transcript onto the script -> timeline.json + lines.txt")
    c.add_argument("--no-split", action="store_true", help="keep each script line whole (do not split sentences)")
    c = proj("draft", "write a plates-only shot list + plates.json (complete first cut)")
    c.add_argument("--force", action="store_true")
    proj("status", "what exists and what the shot list still needs")
    c = proj("stock-search", "Pixabay video search -> contact sheets")
    c.add_argument("queries", nargs="+")
    proj("stock-fetch", "download + proxy the picks in 02-direction/stock_picks.txt and 06-assets/clips")
    c = proj("refs-search", "Wikimedia Commons search -> contact sheets: TAG \"query\" [TAG \"query\" ...]")
    c.add_argument("pairs", nargs="+")
    proj("refs-fetch", "download the picks in 02-direction/refs.txt (+ blurred backgrounds, credits)")
    c = proj("images", "generate missing plates from 02-direction/plates.json with the connected generator")
    c.add_argument("--via", choices=["codex", "browser", "api"])
    c.add_argument("--workers", type=int, default=2)
    c.add_argument("--only", nargs="*")
    c.add_argument("--yes", action="store_true")
    proj("plates", "plates -> public jpg + depth maps")
    c = ws.add_parser("kit", help="build the shared transition/graphics SFX kit")
    c.add_argument("--via", choices=["procedural", "elevenlabs"], default="procedural")
    c.add_argument("--yes", action="store_true")
    c = proj("sound", "story SFX + chapter music from style.json via ElevenLabs (paid)")
    c.add_argument("--yes", action="store_true")
    c = proj("plan", "build plan.json from timeline + shot list + assets")
    c.add_argument("--allow-missing", action="store_true", help="placeholder cards for missing assets (preview)")
    proj("grade", "bake the chapter grade into per-shot stock segments")
    c = proj("render", "render verified chunks")
    c.add_argument("--chunks", nargs="*", type=int)
    c.add_argument("--concurrency", type=int)
    proj("mix", "voice + score + beds + SFX -> mix.wav at -14 LUFS")
    proj("assemble", "verified master -> 09-package/<slug>.mp4")
    proj("thumbnail", "render the thumbnail")
    c = proj("qa", "decode, frames, loudness, black/freeze; --transcribe checks the narration in the final mix")
    c.add_argument("--transcribe", choices=["elevenlabs", "openai", "local"])
    proj("package", "youtube.md with chapters + credits")
    c = proj("voice", "replace the narration with a re-edited file and re-time everything")
    c.add_argument("audio")
    c.add_argument("--provider", default="auto", choices=["auto", "elevenlabs", "openai", "local"])
    c.add_argument("--yes", action="store_true")
    c = proj("run", "do every step whose inputs are ready, in order; stops with the exact next action")
    c.add_argument("--yes", action="store_true", help="allow paid steps (transcription, ElevenLabs sounds, API images)")
    c.add_argument("--auto", action="store_true", help="accept the drafted plates-only shot list without direction")
    c.add_argument("--images-via", choices=["codex", "browser", "api"])
    c.add_argument("--provider", default="auto", choices=["auto", "elevenlabs", "openai", "local"])
    c.add_argument("--preview", action="store_true", help="render even with missing assets (placeholder cards)")


def _transcribe(p: Project, provider: str, yes: bool) -> dict:
    from ..providers.transcribe import estimate_usd, select_transcriber

    if not p.voice_master.exists():
        D.ingest_voice(p)
    from .project import ffprobe_duration

    prov = select_transcriber(provider)
    usd = estimate_usd(prov, ffprobe_duration(p.voice_master))
    if usd > 0 and not yes:
        return {"confirm_required": True, "provider": prov, "estimated_usd": round(usd, 3),
                "next": "Re-run with --yes to spend this, or use --provider local (free). Nothing was charged."}
    return D.transcribe(p, prov)


def _draft(p: Project, force: bool) -> dict:
    if p.shotlist_path.exists() and not force:
        raise WildDocError(f"{p.shotlist_path} exists (maybe directed). Use --force to overwrite it.")
    text, plates = SL.draft(p.timeline(), p.style())
    p.shotlist_path.write_text(text, encoding="utf-8")
    pj = p.p("direction", "plates.json")
    old = read_json(pj, {})
    write_json(pj, {**plates, **old})
    gpath = p.p("direction", "graphics.json")
    if not gpath.exists():
        ch = p.style().get("channel", {})
        write_json(gpath, {"_doc": "Props for M:<graphic>[#key] shots. 'bg': '<stock name>@<seconds>' sets a blurred footage background.",
                           "title": {"kicker": ch.get("name", ""), "lines": ["YOUR", "TITLE", "HERE?"]},
                           "endcard": {"name": ch.get("name", ""), "tagline": ch.get("tagline", ""), "cta": ch.get("cta", "SUBSCRIBE")}})
    return {"shotlist": str(p.shotlist_path), "plates": len(plates), "plates_json": str(pj),
            "next": "Direct it: real stock (S:), evidence (R:), graphics (M:/O), story SFX (X), chapter looks in style.json. "
                    "Or render the draft as is with `run --auto`."}


def _images(p: Project, via, workers, only, yes) -> dict:
    from .. import gen

    jobs = AS.plate_jobs(p, only)
    if not jobs:
        return {"done": 0, "note": "every plate in plates.json has an image"}
    write_json(p.p("direction", "image_jobs.json"), jobs)
    return gen.images(jobs, p.p("assets", "plates"), via, workers, yes=yes)


def run_all(p: Project, yes: bool, auto: bool, images_via, provider: str, preview: bool) -> dict:
    steps: list = []

    def step(name, fn, *a, **k):
        r = fn(*a, **k)
        steps.append({name: r})
        return r

    if not p.voice_master.exists():
        step("voice", D.ingest_voice, p)
    if not p.p("audio", "transcript.json").exists():
        r = step("transcribe", _transcribe, p, provider, yes)
        if r.get("confirm_required"):
            return {"stopped_at": "transcribe", "steps": steps, "next": r["next"]}
    stale = not p.timeline_path.exists() or p.timeline_path.stat().st_mtime < max(p.script_path.stat().st_mtime,
                                                                                  p.p("audio", "transcript.json").stat().st_mtime)
    if stale:
        step("align", A.run, p)
    if not p.shotlist_path.exists():
        r = step("draft", _draft, p, False)
        if not auto:
            return {"stopped_at": "direction", "steps": steps, "next": r["next"]}
    st = AS.status(p)
    miss = st["missing"]
    if (miss["stock"] and p.p("direction", "stock_picks.txt").exists()) or p.p("assets", "clips").exists():
        step("stock-fetch", AS.stock_fetch, p)
    if miss["refs"] and p.p("direction", "refs.txt").exists():
        step("refs-fetch", AS.refs_fetch, p)
    if miss["plates"]:
        if miss["plate_prompts"]:
            steps.append({"plates": f"no prompt in plates.json for {miss['plate_prompts'][:12]}"})
        from .. import logins

        via = images_via or logins.load().get("images", {}).get("via")
        if via:
            r = step("images", _images, p, via, 2, None, yes)
            if r.get("confirm_required"):
                return {"stopped_at": "images", "steps": steps, "next": r["next"]}
        elif not preview:
            return {"stopped_at": "images", "steps": steps,
                    "next": "Connect an image generator: `faceless login images` (or put PNGs named <plate id>.png in 06-assets/plates/)."}
    step("plates", AS.prep_plates, p)
    import os

    if not all(SO.find(None, n) for n in SO.KIT):
        kit_via = "elevenlabs" if (os.environ.get("ELEVENLABS_API_KEY") and yes) else "procedural"
        step("kit", SO.make_kit, kit_via)
    sp = SO.story_plan(p)
    mp = SO.music_plan(p)
    if (sp["missing"] or mp["cues"]) and os.environ.get("ELEVENLABS_API_KEY"):
        if yes:
            if sp["missing"]:
                step("story-sfx", SO.make_story, p)
            if mp["cues"]:
                step("music", SO.make_music, p)
        else:
            steps.append({"sound": {"skipped_paid": {"story_sfx": sp["missing"], "music": [c["chapter"] for c in mp["cues"]]},
                                    "note": "re-run with --yes to generate them with ElevenLabs"}})
    step("plan", PL.build, p, preview)
    step("grade", R.grade, p)
    step("render", R.render, p)
    step("mix", MX.run, p)
    step("assemble", R.assemble, p)
    try:
        step("thumbnail", R.thumbnail, p)
    except Exception as e:  # noqa: BLE001 - a thumbnail failure never blocks the film
        steps.append({"thumbnail": f"failed: {e}"})
    q = step("qa", D.qa, p)
    step("package", D.package, p)
    return {"done": True, "master": str(p.master_path), "qa_passed": q["passed"], "problems": q["problems"], "steps": steps,
            "next": "WATCH the master end to end before anyone else sees it; then send it for approval."}


def handle(args) -> int:  # noqa: C901
    c = args.wd_cmd
    if c == "new":
        from ..config import repo_root

        p = Project.create(Path(args.root) if args.root else repo_root() / "projects", args.slug, Path(args.script), Path(args.audio),
                           args.title, args.lang, args.channel)
        _print({"project": str(p.root), **D.ingest_voice(p), "next": f"faceless wild-doc run {args.slug}"})
        return 0
    if c == "setup":
        out = {}
        R.ensure_node()
        out["remotion"] = "ready"
        if args.depth:
            out["depth"] = AS.download_depth_model()
        if args.kit:
            if args.kit == "elevenlabs" and not args.yes:
                _print({"confirm_required": True, **SO.kit_plan("elevenlabs"), "next": "Re-run with --yes."})
                return 0
            out["kit"] = SO.make_kit(args.kit)
        _print(out)
        return 0
    if c == "kit":
        if args.via == "elevenlabs" and not args.yes:
            _print({"confirm_required": True, **SO.kit_plan("elevenlabs"), "next": "Re-run with --yes."})
            return 0
        _print(SO.make_kit(args.via))
        return 0
    p = _proj(args.project)
    if c == "transcribe":
        _print(_transcribe(p, args.provider, args.yes))
    elif c == "align":
        _print(A.run(p, not args.no_split))
    elif c == "draft":
        _print(_draft(p, args.force))
    elif c == "status":
        _print(AS.status(p))
    elif c == "stock-search":
        _print(AS.stock_search(p, args.queries))
    elif c == "stock-fetch":
        _print(AS.stock_fetch(p))
    elif c == "refs-search":
        if len(args.pairs) % 2:
            raise WildDocError('refs-search takes pairs: TAG "query" [TAG "query" ...]')
        _print(AS.refs_search(p, list(zip(args.pairs[::2], args.pairs[1::2]))))
    elif c == "refs-fetch":
        _print(AS.refs_fetch(p))
    elif c == "images":
        _print(_images(p, args.via, args.workers, args.only, args.yes))
    elif c == "plates":
        _print(AS.prep_plates(p))
    elif c == "sound":
        if not args.yes:
            _print({"confirm_required": True, **SO.plan_all(p), "next": "Re-run with --yes to generate with ElevenLabs."})
            return 0
        _print({"story": SO.make_story(p), "music": SO.make_music(p)})
    elif c == "plan":
        _print(PL.build(p, args.allow_missing))
    elif c == "grade":
        _print(R.grade(p))
    elif c == "render":
        _print(R.render(p, args.chunks, args.concurrency))
    elif c == "mix":
        _print(MX.run(p))
    elif c == "assemble":
        _print(R.assemble(p))
    elif c == "thumbnail":
        _print(R.thumbnail(p))
    elif c == "qa":
        r = D.qa(p, args.transcribe)
        _print(r)
        return 0 if r["passed"] else 2
    elif c == "package":
        _print(D.package(p))
    elif c == "voice":
        out = {"voice": D.ingest_voice(p, Path(args.audio))}
        t = _transcribe(p, args.provider, args.yes)
        out["transcribe"] = t
        if not t.get("confirm_required"):
            out["align"] = A.run(p)
            out["next"] = "faceless wild-doc run " + p.slug + "   (re-plans on the new clock; changed chunks re-render)"
        _print(out)
    elif c == "run":
        r = run_all(p, args.yes, args.auto, args.images_via, args.provider, args.preview)
        _print(r)
        return 0 if r.get("done") or r.get("stopped_at") else 2
    return 0
