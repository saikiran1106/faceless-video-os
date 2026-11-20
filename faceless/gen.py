"""`faceless gen ...` - generate media with whatever `faceless login` connected.

  faceless gen images --jobs jobs.json --out DIR [--via codex|browser|api] [--workers 2]
      jobs.json: [{"id": "P01", "prompt": "...", "aspect": "16:9", "refs": ["path/ref.png"]}, ...]  -> DIR/<id>.png
      codex   : one `codex exec` per image (Codex built-in image tool, your ChatGPT plan); bound by Codex session id
      browser : ChatGPT in the signed-in profile(s); jobs split across accounts, parallel tabs; bound by conversation API
      api     : OpenAI Images API (OPENAI_API_KEY, paid per image; asks before spending)
  faceless gen clips --project DIR --credit-cap N [--accounts flow-1 flow-2] [--dry-run] [--copy-to DIR]
      Google Flow image-to-video from DIR/05-visuals/shot_plan.json + storyboards, beats split across accounts.

Never resubmits a timed-out job (it may still finish and charge twice): failures are reported, re-run with --only.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from . import logins

REPO = Path(__file__).resolve().parents[1]
AUTOMATION = REPO / "automation"
CODEX_IMAGES = Path.home() / ".codex" / "generated_images"
ASPECT_TEXT = {"16:9": "wide 16:9 landscape (1536x1024 or the widest landscape size available)",
               "9:16": "tall 9:16 portrait (1024x1536 or the tallest portrait size available)",
               "1:1": "square 1:1 (1024x1024)", "4:5": "4:5 portrait"}
_fallback_lock = threading.Lock()


def _say(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", file=sys.stderr, flush=True)


def _brief(job: dict) -> str:
    return ("Use your built-in image generation tool to create exactly ONE image. Do not write code, do not run commands, "
            "do not ask questions. After the image is generated, reply only with the word DONE.\n\n"
            f"FORMAT: {ASPECT_TEXT.get(job.get('aspect', '16:9'), job.get('aspect', '16:9'))}.\n\n{job['prompt']}\n")


def _codex_one(exe: str, job: dict, out: Path, timeout_s: int) -> dict:
    t0 = time.time()
    cmd = [exe, "exec", "--skip-git-repo-check", "--ephemeral", "--sandbox", "read-only", "--json"]
    for r in job.get("refs") or []:
        if Path(r).exists():
            cmd += ["-i", str(Path(r).resolve())]
    cmd.append("-")
    try:
        r = subprocess.run(cmd, input=_brief(job), capture_output=True, text=True, timeout=timeout_s, cwd=str(out.parent))
    except subprocess.TimeoutExpired:
        return {"id": job["id"], "ok": False, "error": f"timeout after {timeout_s}s (not resubmitted)"}
    session = None
    for ln in r.stdout.splitlines():
        try:
            ev = json.loads(ln)
        except ValueError:
            continue
        session = session or ev.get("thread_id") or (ev.get("msg") or {}).get("session_id") or ev.get("session_id")
    pngs = []
    if session and (CODEX_IMAGES / session).exists():
        pngs = sorted((CODEX_IMAGES / session).glob("*.png"), key=lambda p: p.stat().st_mtime)
    if not pngs:
        with _fallback_lock:  # only safe when one job runs at a time; flagged in the record
            pngs = sorted((p for p in CODEX_IMAGES.glob("*/*.png") if p.stat().st_mtime >= t0), key=lambda p: p.stat().st_mtime)
            bound = "newest-after-start (verify by eye)"
    else:
        bound = f"codex session {session}"
    if not pngs:
        return {"id": job["id"], "ok": False, "error": "no image produced", "tail": (r.stdout + r.stderr)[-400:]}
    shutil.copy(pngs[-1], out)
    return {"id": job["id"], "ok": True, "file": str(out), "source": str(pngs[-1]), "bound_by": bound,
            "images_in_session": len(pngs), "seconds": round(time.time() - t0),
            "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}


def images(jobs: list[dict], out_dir: Path, via: str | None = None, workers: int = 2, accounts: list[str] | None = None,
           yes: bool = False, timeout_s: int = 600) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = [j for j in jobs if not (out_dir / f"{j['id']}.png").exists()]
    cfg = logins.load()
    via = via or cfg.get("images", {}).get("via")
    if not via:
        raise SystemExit("No image generator connected. Run `faceless login images` first.")
    if not todo:
        return {"via": via, "done": 0, "note": "every job already has an image"}
    manifest_p = out_dir / "gen_manifest.json"
    manifest = json.loads(manifest_p.read_text()) if manifest_p.exists() else []
    if via == "codex":
        st = logins.codex_status()
        if not (st["installed"] and st["signed_in"]):
            raise SystemExit("Codex CLI not ready. Run `faceless login images --via codex`.")
        _say(f"{len(todo)} image(s) via Codex CLI, {workers} at a time")

        def one(j):
            r = _codex_one(st["bin"], j, out_dir / f"{j['id']}.png", timeout_s)
            _say(f"{j['id']}: {'ok' if r['ok'] else 'FAILED ' + r['error']}")
            return r

        with ThreadPoolExecutor(max(1, workers)) as ex:
            res = list(ex.map(one, todo))
    elif via == "browser":
        res = _browser_images(todo, out_dir, cfg, accounts, workers)
    elif via == "api":
        from .providers.images import OpenAIImages

        api = OpenAIImages()
        est = api.estimate_usd(len(todo))
        if not yes:
            return {"confirm_required": True, "provider": "openai-images", "images": len(todo), "estimated_usd": round(est, 2),
                    "next": "Re-run with --yes to spend this. Nothing was charged."}
        res = []
        for j in todo:
            try:
                api.generate(j["prompt"], j.get("aspect", "16:9"), out_dir / f"{j['id']}.png", j.get("refs"))
                res.append({"id": j["id"], "ok": True, "file": str(out_dir / f"{j['id']}.png"), "bound_by": "api response"})
            except Exception as e:  # noqa: BLE001
                res.append({"id": j["id"], "ok": False, "error": str(e)[:200]})
    else:
        raise SystemExit(f"unknown --via {via!r}")
    stamp = datetime.now().isoformat(timespec="seconds")
    manifest += [dict(r, via=via, at=stamp, prompt_sha=hashlib.sha1(next(j["prompt"] for j in todo if j["id"] == r["id"]).encode()).hexdigest()[:10])
                 for r in res if r.get("ok")]
    manifest_p.write_text(json.dumps(manifest, indent=1))
    ok = [r["id"] for r in res if r.get("ok")]
    return {"via": via, "done": len(ok), "failed": [r for r in res if not r.get("ok")], "out": str(out_dir),
            "next": "LOOK at every image next to its prompt before using it; regenerate a bad one by deleting it and re-running."}


def _browser_images(todo: list[dict], out_dir: Path, cfg: dict, accounts: list[str] | None, tabs: int) -> list[dict]:
    profs = [p for p in cfg.get("images", {}).get("profiles", []) if p.get("signed_in") and (not accounts or p["name"] in accounts)]
    if not profs:
        raise SystemExit("No signed-in ChatGPT browser profile. Run `faceless login images --via browser`.")
    shards = {p["name"]: [] for p in profs}
    for k, j in enumerate(todo):
        shards[profs[k % len(profs)]["name"]].append(j)
    procs = []
    for p in profs:
        part = shards[p["name"]]
        if not part:
            continue
        q = out_dir / f".queue_{p['name']}.json"
        q.write_text(json.dumps({"jobs": [{"beat_id": j["id"], "prompt": f"FORMAT: {ASPECT_TEXT.get(j.get('aspect', '16:9'))}.\n{j['prompt']}",
                                           "output_path": f"{j['id']}.png", "reference_paths": [str(Path(r).resolve()) for r in j.get("refs") or []]}
                                          for j in part]}))
        env = dict(os.environ, FACELESS_BROWSER_PROFILE=p["dir"], PYTHONPATH=str(AUTOMATION))
        code = ("import json,sys; from pathlib import Path; from studio_os.fast.storyboards import run; "
                f"print(json.dumps(run(project=Path({str(out_dir)!r}), queue=Path({str(q)!r}), workers={max(1, tabs)})))")
        _say(f"{p['name']}: {len(part)} image(s), {tabs} tab(s)")
        procs.append((p["name"], part, subprocess.Popen([sys.executable, "-c", code], cwd=AUTOMATION, env=env, stdout=subprocess.PIPE, text=True)))
    res = []
    for name, part, pr in procs:
        out, _ = pr.communicate()
        for j in part:
            f = out_dir / f"{j['id']}.png"
            res.append({"id": j["id"], "ok": f.exists(), "file": str(f), "bound_by": f"ChatGPT conversation API ({name})"}
                       if f.exists() else {"id": j["id"], "ok": False, "error": f"not produced by {name} (see its log above)"})
    return res


# ---------------------------------------------------------------- Flow clips across accounts
def clips(project: Path, credit_cap: int, accounts: list[str] | None = None, beats: list[str] | None = None, dry_run: bool = False,
          copy_to: Path | None = None) -> dict:
    project = Path(project).resolve()
    plan = json.loads((project / "05-visuals/shot_plan.json").read_text())
    ids = beats or [b["id"] for b in plan["beats"]]
    cfg = logins.load()
    profs = [p for p in cfg.get("flow", {}).get("profiles", []) if p.get("signed_in") and (not accounts or p["name"] in accounts)]
    if not profs:
        raise SystemExit("No signed-in Flow profile. Run `faceless login flow --accounts N`.")
    if any(not p.get("project_url") for p in profs):
        raise SystemExit("Every Flow profile needs a project URL: open one in its window (`faceless login flow --only NAME`) "
                         "or `faceless login flow --project-url NAME URL`.")
    shards = {p["name"]: ids[k::len(profs)] for k, p in enumerate(profs)}
    cap_each = max(1, credit_cap // len(profs))
    procs = []
    for p in profs:
        part = shards[p["name"]]
        if not part:
            continue
        # each account works in its own folder (own ledger), sharing the frames: no two processes write one ledger
        wd = project / "06-video" / "accounts" / p["name"]
        (wd / "05-visuals").mkdir(parents=True, exist_ok=True)
        for item in ("shot_plan.json", "storyboards"):
            link = wd / "05-visuals" / item
            if not link.exists():
                link.symlink_to(project / "05-visuals" / item)
        env = dict(os.environ, FACELESS_FLOW_PROFILE=p["dir"], FACELESS_FLOW_PROJECT_URL=p["project_url"], PYTHONPATH=str(AUTOMATION))
        cmd = [sys.executable, "-m", "studio_os.cli", "fast", "clips", "--project", str(wd), "--credit-cap", str(cap_each), "--beats", *part]
        if dry_run:
            cmd.append("--dry-run")
        _say(f"{p['name']}: {len(part)} clip(s), credit cap {cap_each}{' (dry run)' if dry_run else ''}")
        procs.append((p["name"], wd, subprocess.Popen(cmd, cwd=AUTOMATION, env=env)))
    summary = {}
    dest = project / "06-video" / "clips"
    dest.mkdir(parents=True, exist_ok=True)
    for name, wd, pr in procs:
        rc = pr.wait()
        got = []
        for f in sorted((wd / "06-video" / "clips").glob("*.mp4")):
            target = dest / f.name
            if not target.exists():
                shutil.copy(f, target)
            got.append(f.name)
            if copy_to:
                Path(copy_to).mkdir(parents=True, exist_ok=True)
                shutil.copy(f, Path(copy_to) / f.name)
        summary[name] = {"exit": rc, "clips": got, "ledger": str(wd / "06-video" / "clips" / "flow_ledger.json")}
    return {"accounts": summary, "clips_dir": str(dest), "dry_run": dry_run}


def add_parser(sub) -> None:
    p = sub.add_parser("gen", help="generate images (Codex/ChatGPT/API) and Flow clips with the connected logins")
    gs = p.add_subparsers(dest="gen_cmd", required=True)
    i = gs.add_parser("images", help="one image per job")
    i.add_argument("--jobs", required=True, help='JSON list: [{"id","prompt","aspect","refs"}]')
    i.add_argument("--out", required=True)
    i.add_argument("--via", choices=["codex", "browser", "api"])
    i.add_argument("--workers", type=int, default=2, help="codex: parallel runs; browser: tabs per account")
    i.add_argument("--accounts", nargs="*", help="browser: only these ChatGPT profiles")
    i.add_argument("--only", nargs="*", help="only these job ids")
    i.add_argument("--yes", action="store_true", help="api: approve the estimated spend")
    c = gs.add_parser("clips", help="Google Flow clips, beats split across signed-in accounts (PAID credits)")
    c.add_argument("--project", required=True)
    c.add_argument("--credit-cap", type=int, required=True, help="total owner-approved credits (split evenly per account)")
    c.add_argument("--accounts", nargs="*")
    c.add_argument("--beats", nargs="*")
    c.add_argument("--dry-run", action="store_true", help="every guard up to the price check, never generate")
    c.add_argument("--copy-to", help="also copy the clips here (e.g. a wild-doc project's 06-assets/clips)")


def handle(args) -> int:
    if args.gen_cmd == "images":
        jobs = json.loads(Path(args.jobs).read_text())
        if args.only:
            jobs = [j for j in jobs if j["id"] in set(args.only)]
        r = images(jobs, Path(args.out), args.via, args.workers, args.accounts, args.yes)
    else:
        r = clips(Path(args.project), args.credit_cap, args.accounts, args.beats, args.dry_run, Path(args.copy_to) if args.copy_to else None)
    print(json.dumps(r, indent=1, ensure_ascii=False))
    return 0 if not r.get("failed") else 2
