"""JSON-batch ChatGPT image generation: N separate images from ONE message (verified format:
7/7 distinct full-size 1672x941 images, in the requested order, ~80 s for all 7).

Batch file (built per project):
  {"style": str, "never": str,
   "jobs":    [{"keyframe_id", "prompt", "reference_paths", "output_path", ...}],
   "batches": [{"batch_id", "reference_paths", "keyframe_ids"}]}

Each batch = one fresh chat in the configured ChatGPT project, its reference set attached, one JSON message.
Images are read from the conversation API. When one reply node carries exactly N images that order is used;
otherwise distinct images are taken in creation order. Position is PROVISIONAL binding: every frame still goes
through pixel QA against its own narration before it is accepted (keyframe-beat binding law).

  PYTHONPATH=. venv/bin/python -m studio_os.fast.json_batch --project P --batches P/.faceless/keyframe_batches.json \
      [--only B001 B002] [--workers 2] [--timeout 900]
"""
from __future__ import annotations

import argparse
import hashlib
import random
import json
import re
import time
from datetime import datetime
from pathlib import Path

from studio_os.browser.config import BrowserConfig
from studio_os.browser.imagegen import ChatGPTImageAdapter

from . import chatgpt_api as API
from .storyboards import Tab


def _log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def build_message(batch: dict, jobs: dict, style: str, never: str, note: str = "", aspect: str = "16:9") -> str:
    refs = [Path(r).stem for r in batch["reference_paths"]]
    n = len(batch["keyframe_ids"])
    msg = {
        "task": (f"Generate {n} SEPARATE images, one image per entry in 'images', in exactly this order. Each image is "
                 f"its own full-size {aspect} output.  Do NOT combine them into a grid, collage, contact sheet or split-screen "
                 "(unless an entry itself asks for a storyboard sheet). Every image is ONE single full-frame photograph of ONE entry: never put two entries into one image, never stack or split panels. Do NOT repeat an image. Generate them one after "
                 f"another until all {n} are done."),
        "attached_references": (f"The attached images are: {', '.join(refs)}. The character sheets define each "
                                "character's EXACT face, body, costume, ornaments, tilak and weapon - match them exactly in "
                                "every image where that character appears. The location plate defines the place."),
        **({"continuity": note} if note else {}),
        "style": style,
        "never": never,
        "images": [{"id": i + 1, "shot": k, "prompt": jobs[k]["prompt"]} for i, k in enumerate(batch["keyframe_ids"])],
    }
    return json.dumps(msg, ensure_ascii=False, indent=1)


def collect(conv: dict, head: str, after_t: float, n: int) -> list[dict]:
    imgs = [x for x in API.replies_to(conv, head, after_t) if x["status"] in (None, "finished_successfully")]
    by_node: dict = {}
    for x in imgs:
        by_node.setdefault(x["node"], []).append(x)
    full = [v for v in by_node.values() if len(v) == n]
    if full:
        return full[0]
    seen, out = set(), []
    for x in imgs:
        if x["ptr"] not in seen:
            seen.add(x["ptr"])
            out.append(x)
    return out


def run(project: Path, batches_file: Path, only: list[str] | None, workers: int, timeout_s: int,
        repo: Path) -> dict:
    data = json.loads(batches_file.read_text())
    jobs = {j["keyframe_id"]: j for j in data["jobs"]}
    todo = []
    for b in data["batches"]:                 # re-request only the frames still missing (partial batches resume)
        missing = [k for k in b["keyframe_ids"] if not (project / jobs[k]["output_path"]).exists()]
        if missing and (not only or b["batch_id"] in only):
            todo.append({**b, "keyframe_ids": missing})
    receipts_p = project / "06-keyframes" / "batch_receipts.json"
    receipts = json.loads(receipts_p.read_text()) if receipts_p.exists() else []
    cfg = BrowserConfig().ensure_dirs()
    cfg.headless = False
    gizmo = (re.search(r"/g/(g-p-[0-9a-f]+)", cfg.project_url) or [None, None])[1]
    _log(f"{len(todo)} batches, {sum(len(b['keyframe_ids']) for b in todo)} images, {workers} tabs")
    done, failed = 0, []
    with ChatGPTImageAdapter(cfg) as main:
        ctx = main._ctx
        tabs = [Tab(cfg, main.page)] + [Tab(cfg, ctx.new_page()) for _ in range(max(0, min(workers, len(todo)) - 1))]
        state = {i: None for i in range(len(tabs))}
        while todo or any(state.values()):
            for i, tab in enumerate(tabs):
                cur = state[i]
                if cur is None and todo:
                    b = todo.pop(0)
                    msg = build_message(b, jobs, data["style"], data["never"], data.get("continuity_note", ""),
                                        data.get("aspect", "16:9"))
                    try:
                        tab.open_conversation(None)
                        tab.upload_references([str(repo / r) for r in b["reference_paths"]])
                        t0 = time.time()
                        tab.submit_prompt(msg)
                        state[i] = {"b": b, "msg": msg, "t0": t0, "conv": None}
                        _log(f"tab{i} submitted {b['batch_id']} ({len(b['keyframe_ids'])} images)")
                    except Exception as e:                 # noqa: BLE001
                        failed.append({"batch": b["batch_id"], "error": f"submit: {e}"[:300]})
                        _log(f"tab{i} submit FAILED {b['batch_id']}: {e}")
                    continue
                if cur is None:
                    continue
                # GENTLE WAIT (2026-10-02): fast polling of the conversation API got the account rate-limited (429),
                # and the DOM stop-button is NOT a done-signal for images (they render in the background). So:
                # read the conversation at most once every 75 s, starting 60 s after submit.
                elapsed = time.time() - cur["t0"]
                first_read = min(240, 40 + 30 * len(cur["b"]["keyframe_ids"]))   # images take ~30-50 s each
                if elapsed < first_read or time.time() < cur.get("next_read", 0):
                    continue
                cur["next_read"] = time.time() + 90 + random.uniform(0, 20)
                if not cur["conv"] or cur["conv"].startswith("local-"):
                    cur["conv"] = API.conv_id_from_url(tab.page.url)
                    if not cur["conv"] or cur["conv"].startswith("local-"):
                        cur["conv"] = API.resolve_conv_id(tab.page, cur["conv"], gizmo, cur["t0"])
                if not cur["conv"]:
                    continue
                conv = API.conversation(tab.page, cur["conv"])
                if conv.get("status") != 200:
                    cur["fails"] = cur.get("fails", 0) + 1
                    wait = min(600, (conv.get("retry_after") or 90) * (2 ** (cur["fails"] - 1)))
                    _log(f"tab{i} conversation read {conv.get('status')} - backing off {wait:.0f} s")
                    cur["next_read"] = time.time() + wait
                    continue
                cur["fails"] = 0
                n = len(cur["b"]["keyframe_ids"])
                imgs = collect(conv, cur["msg"], cur["t0"], n)
                said = " ".join(x["text"] for x in conv.get("nodes", {}).values()
                                if x.get("role") == "assistant" and x.get("text") and (x.get("t") or 0) >= cur["t0"] - 5)
                refused = any(w in said.lower() for w in ("guardrail", "violate", "policy", "can't help", "cannot create"))
                if len(imgs) != cur.get("last_count"):
                    cur["last_count"], cur["stable_since"] = len(imgs), time.time()
                stalled = time.time() - cur["stable_since"] > 300 and not tab.busy()
                if len(imgs) >= n or refused or stalled or elapsed > timeout_s:
                    rec = {"batch": cur["b"]["batch_id"], "conversation": cur["conv"], "expected": n,
                           "returned": len(imgs), "seconds": round(time.time() - cur["t0"]), "frames": [],
                           "binding": "provisional by reply order; must pass pixel QA against own narration",
                           "at": datetime.now().isoformat(timespec="seconds")}
                    for k, img in zip(cur["b"]["keyframe_ids"], imgs):
                        body, _ = API.download(tab.page, img["ptr"], cur["conv"])
                        out = project / jobs[k]["output_path"]
                        out.parent.mkdir(parents=True, exist_ok=True)
                        out.write_bytes(body)
                        rec["frames"].append({"keyframe_id": k, "file": str(out.relative_to(project)),
                                              "sha256": hashlib.sha256(body).hexdigest(), "w": img["w"], "h": img["h"],
                                              "asset": img["ptr"], "node": img["node"]})
                    receipts.append(rec)
                    receipts_p.parent.mkdir(parents=True, exist_ok=True)
                    receipts_p.write_text(json.dumps(receipts, indent=1))
                    if len(imgs) < n:
                        said = [x["text"] for x in conv.get("nodes", {}).values()
                                if x.get("role") == "assistant" and x.get("text") and (x.get("t") or 0) >= cur["t0"] - 5]
                        failed.append({"batch": rec["batch"], "error": f"returned {len(imgs)}/{n}",
                                       "conversation": cur["conv"], "assistant_text": (said[-1] if said else "")[:300],
                                       "keyframe_ids": cur["b"]["keyframe_ids"],
                                       "got": [f["keyframe_id"] for f in rec["frames"]]})
                    done += len(rec["frames"])
                    _log(f"tab{i} {'DONE' if len(imgs) >= n else 'PARTIAL'} {rec['batch']} {len(imgs)}/{n} "
                         f"in {rec['seconds']}s")
                    state[i] = None
            main.page.wait_for_timeout(15000)
    return {"images": done, "failed": failed}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--batches", required=True)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()
    print(json.dumps(run(Path(a.project), Path(a.batches), a.only, a.workers, a.timeout, Path.cwd()), indent=1))


if __name__ == "__main__":
    main()
