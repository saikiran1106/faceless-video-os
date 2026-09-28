"""`faceless` - the command line for Faceless Forge.

Every command prints JSON so agents can read it; humans get the same facts.
Paid commands estimate first and refuse to spend without --yes.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .config import load_dotenv, repo_root
from .contracts import ContractError
from .engine import ProductionEngine, StateError
from .media import MediaError
from .providers import ProviderError
from .stages import FORMATS, HOSTS, HUMAN_GATES, STAGE_ARTIFACTS, VOICE_MODES


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _project(ref: str) -> Path:
    """Accept a path or a bare slug under ./projects."""
    path = Path(ref).expanduser()
    if (path / ".faceless" / "run.json").exists():
        return path.resolve()
    candidate = repo_root() / "projects" / ref
    if (candidate / ".faceless" / "run.json").exists():
        return candidate.resolve()
    raise StateError(f"No faceless project at {ref!r} (looked in {path} and {candidate})")


def _engine(ref: str) -> ProductionEngine:
    return ProductionEngine(_project(ref))


def _confirm(args, estimate: dict) -> bool:
    """Paid calls print the estimate and stop unless --yes was given."""
    if getattr(args, "yes", False):
        return True
    _print({"confirm_required": True, **estimate, "next": "Re-run with --yes to spend this. Nothing was charged."})
    return False


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="faceless", description="Faceless Forge: agent-driven faceless video pipeline")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("setup", help="create channel.json/.env from the examples and sync skills")
    sub.add_parser("doctor", help="what this machine can do, and what is one step away")
    d = sub.add_parser("demo", help="free offline end-to-end run (no API keys) to prove the install works")
    d.add_argument("--format", choices=FORMATS, default="short")
    d.add_argument("--engine", choices=["remotion", "ffmpeg"], default="remotion")
    d.add_argument("--no-render", action="store_true")

    s = sub.add_parser("init", help="start a new video project")
    s.add_argument("slug")
    s.add_argument("--title", required=True)
    s.add_argument("--format", choices=FORMATS, required=True)
    s.add_argument("--voice", choices=VOICE_MODES, required=True, help="tts = AI voice from a script; upload = your own recording")
    s.add_argument("--host", choices=HOSTS, required=True, help="who generates images: codex | claude-code | api | manual")
    s.add_argument("--language", default="en", help="ISO code of the narration language, e.g. en, hi, te, es")
    s.add_argument("--budget-usd", type=float, default=0.0, help="approved spend ceiling for paid API calls")
    s.add_argument("--projects-root", type=Path, default=None)

    for name, helptext in (("status", "full run state"), ("next", "what to do now")):
        c = sub.add_parser(name, help=helptext)
        c.add_argument("project")

    for name in ("gate", "complete"):
        c = sub.add_parser(name, help="run the stage gate" if name == "gate" else "gate + advance the stage")
        c.add_argument("project")
        c.add_argument("stage", choices=list(STAGE_ARTIFACTS))

    c = sub.add_parser("approve", help="record the human's approval at a checkpoint")
    c.add_argument("project")
    c.add_argument("gate", choices=list(HUMAN_GATES.values()))
    c.add_argument("--approver", required=True)
    c.add_argument("--note", default="")
    c = sub.add_parser("reject", help="send a checkpoint back with the human's notes")
    c.add_argument("project")
    c.add_argument("gate", choices=list(HUMAN_GATES.values()))
    c.add_argument("--note", required=True)
    c.add_argument("--approver", default="human")
    c = sub.add_parser("reopen", help="go back to an earlier stage (invalidates later ones)")
    c.add_argument("project")
    c.add_argument("stage", choices=list(STAGE_ARTIFACTS))
    c.add_argument("--reason", required=True)
    c = sub.add_parser("lock", help="freeze an artifact by hash")
    c.add_argument("project")
    c.add_argument("name")
    c.add_argument("artifact", type=Path)
    c.add_argument("--reason", default="")
    c = sub.add_parser("unlock")
    c.add_argument("project")
    c.add_argument("name")
    c.add_argument("--reason", required=True)
    c = sub.add_parser("budget", help="change the approved spend ceiling")
    c.add_argument("project")
    c.add_argument("--usd", type=float, required=True)
    c.add_argument("--approver", required=True)
    c = sub.add_parser("cost", help="record spend made outside the CLI (e.g. Codex image credits)")
    c.add_argument("project")
    c.add_argument("--amount-usd", type=float, required=True)
    c.add_argument("--provider", required=True)
    c.add_argument("--operation-id", required=True)
    c.add_argument("--stage", required=True)

    v = sub.add_parser("voice", help="AI voice or your own recording").add_subparsers(dest="voice_cmd", required=True)
    c = v.add_parser("generate", help="synthesize narration from the approved script")
    c.add_argument("project")
    c.add_argument("--provider", default="auto", choices=["auto", "elevenlabs", "openai"])
    c.add_argument("--voice-id", default="")
    c.add_argument("--model", default="")
    c.add_argument("--retake", default="", help="force one paid retake of a single chunk, e.g. C003")
    c.add_argument("--dry-run", action="store_true")
    c.add_argument("--yes", action="store_true")
    c = v.add_parser("ingest", help="use your own recorded narration")
    c.add_argument("project")
    c.add_argument("audio", type=Path)

    c = sub.add_parser("transcribe", help="word-timed transcript (Scribe -> Whisper -> local)")
    c.add_argument("project")
    c.add_argument("--provider", default="auto", choices=["auto", "elevenlabs", "openai", "local"])
    c.add_argument("--yes", action="store_true")

    sc = sub.add_parser("script", help="script helpers").add_subparsers(dest="script_cmd", required=True)
    c = sc.add_parser("from-transcript", help="draft script.json from uploaded narration")
    c.add_argument("project")
    c.add_argument("--force", action="store_true")

    b = sub.add_parser("beats", help="beat timeline").add_subparsers(dest="beats_cmd", required=True)
    c = b.add_parser("build", help="measure beats from word timings")
    c.add_argument("project")
    c.add_argument("--force", action="store_true", help="overwrite an existing (possibly directed) beat manifest")
    c.add_argument("--keep-directions", action="store_true", help="re-time beats after a voice change, keeping directions + keyframes for unchanged lines")

    im = sub.add_parser("images", help="keyframes and reference sheets").add_subparsers(dest="images_cmd", required=True)
    for name, helptext in (("jobs", "compile image jobs"), ("prompts", "write copy-paste prompts (manual host)")):
        c = im.add_parser(name, help=helptext)
        c.add_argument("project")
        c.add_argument("--sheets", action="store_true", help="character/location reference sheets instead of keyframes")
    c = im.add_parser("generate", help="generate via the OpenAI Images API (api host)")
    c.add_argument("project")
    c.add_argument("--sheets", action="store_true")
    c.add_argument("--only", nargs="*")
    c.add_argument("--limit", type=int)
    c.add_argument("--yes", action="store_true")
    c = im.add_parser("record", help="file one image against its job (after LOOKING at it)")
    c.add_argument("project")
    c.add_argument("id", help="keyframe_id, beat_id or SHEET-<id>")
    c.add_argument("file", type=Path)
    c.add_argument("--host", default="")
    c = im.add_parser("ingest", help="record every file named exactly <ID>.png in a folder")
    c.add_argument("project")
    c.add_argument("folder", type=Path)
    c = im.add_parser("apply-sheets", help="add generated sheets to the visual bible references")
    c.add_argument("project")
    c = im.add_parser("manifest", help="build keyframe_manifest.json from the files on disk")
    c.add_argument("project")
    c = im.add_parser("qa", help="record a visual review verdict")
    c.add_argument("project")
    c.add_argument("ids", nargs="+", help="keyframe ids, beat ids, or 'all'")
    verdict = c.add_mutually_exclusive_group(required=True)
    verdict.add_argument("--pass", dest="verdict", action="store_const", const="pass")
    verdict.add_argument("--fail", dest="verdict", action="store_const", const="fail")
    c.add_argument("--note", default="")

    r = sub.add_parser("review", help="visual review aids").add_subparsers(dest="review_cmd", required=True)
    c = r.add_parser("contact-sheet", help="every keyframe beside its narration")
    c.add_argument("project")
    c = r.add_parser("render-sheet", help="frames sampled from the finished render at each beat")
    c.add_argument("project")
    c.add_argument("--platform", default="youtube")

    cp = sub.add_parser("compose", help="props, render, report").add_subparsers(dest="compose_cmd", required=True)
    c = cp.add_parser("props", help="write Remotion props JSON")
    c.add_argument("project")
    c.add_argument("--platform", default="youtube", choices=["youtube", "instagram", "tiktok"])
    c = cp.add_parser("render", help="render the video")
    c.add_argument("project")
    c.add_argument("--platform", default="youtube", choices=["youtube", "instagram", "tiktok"])
    c.add_argument("--engine", default="remotion", choices=["remotion", "ffmpeg"])
    c.add_argument("--keep-props", action="store_true", help="render the existing props file (after hand edits)")
    c = cp.add_parser("report", help="probe renders into render_report.json")
    c.add_argument("project")
    c.add_argument("--reviewed", action="store_true", help="someone watched the render end to end")
    c.add_argument("--notes", default="")

    pk = sub.add_parser("package", help="publishing package").add_subparsers(dest="package_cmd", required=True)
    c = pk.add_parser("draft", help="chapters, SRT and a package skeleton")
    c.add_argument("project")
    c.add_argument("--force", action="store_true")

    sk = sub.add_parser("skills", help="skill mirrors").add_subparsers(dest="skills_cmd", required=True)
    sk.add_parser("sync", help="copy skills/ into .claude/skills and .agents/skills")

    from .browser import cli as browser_cli

    browser_cli.add_parser(sub)
    return p


def sync_skills(root: Path) -> dict:
    source = root / "skills"
    copied = []
    for mirror in (root / ".claude" / "skills", root / ".agents" / "skills"):
        for skill in sorted(d for d in source.iterdir() if d.is_dir()):
            dest = mirror / skill.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(skill, dest)
            copied.append(str(dest.relative_to(root)))
    return {"synced": copied}


def dispatch(args) -> int:  # noqa: C901 - a flat command table reads best here
    cmd = args.command
    if cmd == "setup":
        root = repo_root()
        made = []
        for example, target in (("channel.example.json", "channel.json"), (".env.example", ".env")):
            if not (root / target).exists() and (root / example).exists():
                shutil.copy(root / example, root / target)
                made.append(target)
        (root / "projects").mkdir(exist_ok=True)
        _print({"created": made, **sync_skills(root), "next": "Edit channel.json and .env, then run `faceless doctor`."})
        return 0
    if cmd == "doctor":
        from .doctor import run_doctor

        report = run_doctor()
        _print(report)
        return 0 if report["passed"] else 2
    if cmd == "demo":
        from .demo import run_demo

        _print(run_demo(args.format, not args.no_render, args.engine))
        return 0
    if cmd == "skills":
        _print(sync_skills(repo_root()))
        return 0
    if cmd == "init":
        root = args.projects_root or repo_root() / "projects"
        engine = ProductionEngine.initialize(root, args.slug, args.title, args.format, args.voice, args.host, args.language, args.budget_usd)
        _print({"project": str(engine.project_root), **engine.next_action()})
        return 0
    if cmd == "browser":
        from .browser import cli as browser_cli

        args.project = str(_project(args.project)) if getattr(args, "project", None) else None
        return browser_cli.handle(args)

    engine = _engine(args.project)
    if cmd == "status":
        _print(engine.state())
    elif cmd == "next":
        _print(engine.next_action())
    elif cmd == "gate":
        report = engine.gate(args.stage)
        _print(report)
        return 0 if report["passed"] else 2
    elif cmd == "complete":
        state = engine.complete(args.stage)
        entry = state["stages"][args.stage]
        _print({"stage": args.stage, "status": entry["status"], "findings": entry.get("gate_report", {}).get("findings", []), "next": engine.next_action()})
        return 0 if entry["status"] != "failed" else 2
    elif cmd == "approve":
        engine.approve(args.gate, args.approver, args.note)
        _print(engine.next_action())
    elif cmd == "reject":
        engine.reject(args.gate, args.approver, args.note)
        _print(engine.next_action())
    elif cmd == "reopen":
        engine.reopen(args.stage, args.reason)
        _print(engine.next_action())
    elif cmd == "lock":
        _print(engine.lock(args.name, args.artifact, args.reason)["locks"])
    elif cmd == "unlock":
        _print(engine.unlock(args.name, args.reason)["locks"])
    elif cmd == "budget":
        _print(engine.set_budget(args.usd, args.approver)["budget"])
    elif cmd == "cost":
        _print(engine.record_cost(args.amount_usd, args.provider, args.operation_id, args.stage)["budget"])
    elif cmd == "voice":
        from . import voice

        if args.voice_cmd == "ingest":
            _print(voice.ingest(engine, args.audio))
        else:
            plan = {k: v for k, v in voice.plan_generation(engine, args.provider, args.voice_id, args.model).items() if not k.startswith("_")}
            if args.dry_run or not _confirm(args, plan):
                if args.dry_run:
                    _print(plan)
                return 0
            manifest = voice.generate(engine, args.provider, args.voice_id, args.model, args.retake)
            _print({k: v for k, v in manifest.items() if k != "chunks"} | {"chunks": len(manifest["chunks"])})
    elif cmd == "transcribe":
        from . import transcript

        plan = transcript.plan(engine, args.provider)
        if plan["estimated_usd"] > 0 and not _confirm(args, plan):
            return 0
        _print(transcript.run(engine, args.provider))
    elif cmd == "script":
        from .transcript import script_from_transcript

        _print(script_from_transcript(engine, args.force))
    elif cmd == "beats":
        _print(_build_beats(engine, args.force, args.keep_directions))
    elif cmd == "images":
        from . import imagejobs

        sheets = getattr(args, "sheets", False)
        if args.images_cmd == "jobs":
            _print(imagejobs.compile_jobs(engine, sheets))
        elif args.images_cmd == "prompts":
            _print({"written": str(imagejobs.write_prompts(engine, sheets))})
        elif args.images_cmd == "generate":
            if not _confirm(args, imagejobs.estimate_api(engine, sheets)):
                return 0
            _print(imagejobs.generate_api(engine, sheets, args.only, args.limit))
        elif args.images_cmd == "record":
            _print(imagejobs.record(engine, args.id, args.file, args.host))
        elif args.images_cmd == "ingest":
            _print(imagejobs.ingest_folder(engine, args.folder))
        elif args.images_cmd == "apply-sheets":
            _print(imagejobs.apply_sheets(engine))
        elif args.images_cmd == "manifest":
            _print(imagejobs.build_manifest(engine))
        elif args.images_cmd == "qa":
            _print(imagejobs.set_qa(engine, args.ids, args.verdict, args.note))
    elif cmd == "review":
        from . import review

        path = review.contact_sheet(engine) if args.review_cmd == "contact-sheet" else review.render_sheet(engine, args.platform)
        _print({"written": str(path), "next": "Open the image and compare every frame against its narration line."})
    elif cmd == "compose":
        from . import compose

        if args.compose_cmd == "props":
            _print({"written": str(compose.write_props(engine, args.platform))})
        elif args.compose_cmd == "render":
            out = compose.render_ffmpeg(engine, args.platform) if args.engine == "ffmpeg" else compose.render_remotion(engine, args.platform, args.keep_props)
            _print({"rendered": str(out), "next": f"Watch it, then `faceless compose report {args.project} --reviewed`"})
        else:
            doc = compose.report(engine, args.reviewed, args.notes)
            _print(doc)
    elif cmd == "package":
        from . import package

        _print(package.draft(engine, args.force))
    return 0


def _build_beats(engine: ProductionEngine, force: bool, keep_directions: bool = False) -> dict:
    from .beats import build_beats, carry_directions
    from .config import load_profile
    from .io import atomic_write_json, load_json

    path = engine.artifact_path("beats")
    if path.exists() and not (force or keep_directions):
        raise StateError(f"{path} exists and may already be directed. Use --keep-directions after a voice change, or --force to start over.")
    transcript = load_json(engine.artifact_path("transcript"))
    pacing = load_profile(engine.state()["format"])["beats"]
    beats = build_beats(transcript["words"], transcript["duration_s"], pacing)
    carried = carry_directions(beats, load_json(path)["beats"]) if keep_directions and path.exists() else None
    atomic_write_json(path, {"version": "1.0", "audio_duration_s": transcript["duration_s"], "directed": bool(carried and not carried["new_needing_direction"]), "beats": beats})
    spans = [b["end_s"] - b["start_s"] for b in beats]
    out = {"path": str(path), "beats": len(beats), "avg_s": round(sum(spans) / len(spans), 2), "max_s": round(max(spans), 2), "next": "Direct every beat (visual_objective, shot_scale, camera, character_ids, location_id)."}
    if carried is not None:
        out.update(carried)
        out["next"] = "Direct the new beats, recompile image jobs, and generate keyframes only for them."
    return out


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    try:
        return dispatch(args)
    except (StateError, ContractError, ProviderError, MediaError, ValueError) as exc:
        _print({"error": type(exc).__name__, "message": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
