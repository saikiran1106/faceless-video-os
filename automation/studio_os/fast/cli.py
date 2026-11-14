"""`studio_os fast ...`: the fast media pipeline."""
from __future__ import annotations

import json
from pathlib import Path


def add_parser(sub):
    p = sub.add_parser("fast", help="fast media pipeline (parallel ChatGPT storyboards, batch Flow clips)")
    fs = p.add_subparsers(dest="fast_cmd", required=True)
    s = fs.add_parser("storyboards", help="parallel ChatGPT storyboards (one image per message, API-read)")
    s.add_argument("--project", required=True)
    s.add_argument("--queue", required=True)
    s.add_argument("--beats", nargs="*")
    s.add_argument("--workers", type=int, default=3)
    s.add_argument("--overwrite", action="store_true")
    s.add_argument("--dry-run", action="store_true", help="attach refs + fill prompt, never send")
    s.add_argument("--fresh-chat", action="store_true",
                   help="new ChatGPT chat after every image (character sheets: stops faces copying earlier images)")
    c = fs.add_parser("clips", help="submit all Flow clips back-to-back, harvest via media API (PAID)")
    c.add_argument("--project", required=True)
    c.add_argument("--beats", nargs="*")
    c.add_argument("--credit-cap", type=int, required=True)
    c.add_argument("--dry-run", action="store_true", help="every guard up to the price check, never generate")
    cp = fs.add_parser("capture", help="free real screen captures: GitHub repos / URLs")
    cp.add_argument("--project", required=True)
    cp.add_argument("--repo", action="append", default=[])
    cp.add_argument("--url", action="append", default=[])
    for name, hlp in (("queue", "derive refs/storyboard queues from shot_plan.json"),
                      ("sheet", "labelled storyboard contact sheet"),
                      ("match", "check each clip starts on its own storyboard"),
                      ("props", "build Remotion props for the TechReel composition"),
                      ("render", "render the TechReel composition")):
        x = fs.add_parser(name, help=hlp)
        x.add_argument("--project", required=True)
        if name == "render":
            x.add_argument("--version", default="v1")
    return p


def handle(args) -> int:
    if args.fast_cmd == "capture":
        from .capture import capture_repo, capture_url
        r = [capture_repo(Path(args.project), x) for x in args.repo] + [capture_url(Path(args.project), u) for u in args.url]
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    if args.fast_cmd in ("queue", "sheet", "match", "props", "render"):
        from . import prep
        fn = {"queue": prep.build_queues, "sheet": prep.contact_sheet, "match": prep.match_clips,
              "props": prep.build_props, "render": prep.render}[args.fast_cmd]
        r = fn(Path(args.project), args.version) if args.fast_cmd == "render" else fn(Path(args.project))
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    if args.fast_cmd == "storyboards":
        from .storyboards import run
        r = run(Path(args.project), Path(args.queue), args.beats, args.workers,
                overwrite=args.overwrite, dry_run=args.dry_run, fresh_chat=args.fresh_chat)
    else:
        from .clips import run
        r = run(Path(args.project), args.beats, args.credit_cap, dry_run=args.dry_run)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0
