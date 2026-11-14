"""Parallel ChatGPT storyboard generation.

W tabs in one persistent profile, each with its own conversation inside the configured ChatGPT
project. A job = one image in one message (identity is exact). Submission goes through the real
composer (the adapter's tested upload/submit code); completion and download go through ChatGPT's
conversation API, so there are no DOM-count timeouts and no position guessing.
"""
from __future__ import annotations

import hashlib
import re
import json
import time
from datetime import datetime
from pathlib import Path

from studio_os.browser.config import BrowserConfig
from studio_os.browser.imagegen import ChatGPTImageAdapter

from . import chatgpt_api as API


CONV_POST = re.compile(r"/backend-api/(f/)?conversation(\?|$)")
ASSET = re.compile(r"sediment://|file-service://|asset_pointer|image_gen")


class Tab(ChatGPTImageAdapter):
    """The adapter's upload/submit methods bound to an extra page of an already-open context.

    It also listens to ChatGPT's own network traffic: the end of a conversation stream (a reply has
    finished) and websocket frames that mention an image asset. Either one is a 'kick' that makes the
    runner read the conversation API at once instead of waiting for the UI or a poll timer."""

    def __init__(self, cfg: BrowserConfig, page):
        super().__init__(cfg)
        self.page = page
        self.page.set_default_timeout(cfg.nav_timeout_s * 1000)
        self.kicks: list[tuple[float, str]] = []
        page.on("requestfinished", self._on_finished)
        page.on("websocket", self._on_ws)

    def _on_finished(self, req) -> None:
        if req.method == "POST" and CONV_POST.search(req.url):
            self.kicks.append((time.time(), "stream_end"))

    def _on_ws(self, ws) -> None:
        def frame(payload):
            text = payload if isinstance(payload, str) else ""
            if ASSET.search(text):
                self.kicks.append((time.time(), "ws_asset"))
        ws.on("framereceived", frame)

    def kicked_since(self, t: float) -> str | None:
        hits = [k for ts, k in self.kicks if ts > t]
        return hits[-1] if hits else None


def _log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def run(project: Path, queue: Path, beats: list[str] | None = None, workers: int = 3,
        per_image_timeout_s: int = 420, overwrite: bool = False, repo: Path | None = None,
        dry_run: bool = False, fresh_chat: bool = False) -> dict:
    repo = repo or Path.cwd()
    project = Path(project)
    jobs = json.loads(Path(queue).read_text())["jobs"]
    if beats:
        jobs = [j for j in jobs if j["beat_id"] in set(beats)]
    if not overwrite:
        jobs = [j for j in jobs if not (project / j["output_path"]).exists()]
    manifest_p = project / "05-visuals/storyboards/fast_manifest.json"
    manifest = json.loads(manifest_p.read_text()) if manifest_p.exists() else {"images": []}
    pending = list(jobs)
    results, failures = [], []
    cfg = BrowserConfig().ensure_dirs()
    cfg.headless = False
    t_run = time.time()
    _log(f"{len(pending)} storyboard jobs, {workers} tabs")
    if not pending:
        return {"done": 0, "failed": 0, "seconds": 0}
    with ChatGPTImageAdapter(cfg) as main:
        ctx = main._ctx
        tabs = [Tab(cfg, main.page)] + [Tab(cfg, ctx.new_page()) for _ in range(min(workers, len(pending)) - 1)]
        for t in tabs:
            t.open_conversation(None)                     # project landing page -> fresh chat per tab
        state = {i: None for i in range(len(tabs))}       # tab -> in-flight job
        while pending or any(state.values()):
            for i, tab in enumerate(tabs):
                cur = state[i]
                if cur is None and pending:
                    job = pending.pop(0)
                    refs = [str(repo / r) for r in job.get("reference_paths") or []]
                    try:
                        if refs:
                            tab.upload_references(refs)
                        t0 = time.time()
                        if dry_run:                       # everything but the send click
                            comp = tab.page.locator("#prompt-textarea, [contenteditable=true]").first
                            comp.fill(job["prompt"])
                            ok = " ".join(comp.inner_text().split())[:80] == " ".join(job["prompt"].split())[:80]
                            results.append({"beat": job["beat_id"], "dry_run": True, "tab": i,
                                            "refs_attached": len(refs), "prompt_landed": ok})
                            _log(f"tab{i} DRY {job['beat_id']} refs={len(refs)} prompt_ok={ok}")
                            comp.fill("")
                            tab.clear_attachments()
                            continue
                        tab.submit_prompt(job["prompt"])
                        state[i] = {"job": job, "t0": t0, "conv": None}
                        _log(f"tab{i} submitted {job['beat_id']}")
                    except Exception as e:                      # noqa: BLE001
                        if not job.get("_retried"):
                            job["_retried"] = True
                            pending.append(job)
                            _log(f"tab{i} submit failed {job['beat_id']}, will retry in a fresh chat: {e}"[:220])
                        else:
                            failures.append({"beat": job["beat_id"], "error": f"submit: {e}"[:300]})
                            _log(f"tab{i} submit FAILED {job['beat_id']}: {e}"[:220])
                        try:
                            tab.open_conversation(None)
                        except Exception as e2:                 # noqa: BLE001
                            _log(f"tab{i} could not open a fresh chat: {e2}"[:200])
                    continue
                if cur is None:
                    continue
                # event first: a finished stream or an image frame on the wire means read the API now
                kick = tab.kicked_since(cur.get("last_read", cur["t0"]))
                if not kick:
                    # fallback: network-quiet while ChatGPT is generating (polling caused 429s), then poll every 15 s
                    if tab.busy() and time.time() - cur["t0"] < per_image_timeout_s:
                        continue
                    if time.time() < cur.get("next_read", cur["t0"] + 15):
                        continue
                cur["next_read"] = time.time() + 15
                cur["last_read"] = time.time()
                if not cur["conv"] or cur["conv"].startswith("local-"):
                    gizmo = (re.search(r"/g/(g-p-[0-9a-f]+)", cfg.project_url) or [None, None])[1]
                    cur["conv"] = API.resolve_conv_id(tab.page, API.conv_id_from_url(tab.page.url), gizmo, cur["t0"])
                if not cur["conv"]:
                    continue
                conv = API.conversation(tab.page, cur["conv"])
                head, t_head = cur.get("head", cur["job"]["prompt"]), cur.get("t_head", cur["t0"])
                imgs = [x for x in API.replies_to(conv, head, t_head)
                        if x["status"] in (None, "finished_successfully")]
                done = imgs and not tab.busy()
                texts = [] if imgs else API.text_replies_to(conv, head, t_head)   # API status, not the UI stop button
                if texts and not done:
                    # words but no image yet: an interim "creating it now" line also looks like this, so only act
                    # when the text-only state is still there 40 s later with no image tool step
                    seen = cur.setdefault("text_seen", time.time())
                    if time.time() - seen < 40:
                        cur["next_read"] = seen + 41
                        continue
                    _log(f"tab{i} TEXT REPLY {cur['job']['beat_id']}: {' '.join(texts[-1].split())[:220]}")
                    if not cur.get("nudged"):
                        nudge = ("Generate the image now, exactly as described in my previous message. "
                                 "Use the attached references only as described. One single image.")
                        try:
                            tab.submit_prompt(nudge)
                            cur.update(nudged=True, head=nudge, t_head=time.time(), next_read=time.time() + 15)
                            cur.pop("text_seen", None)
                            _log(f"tab{i} nudged {cur['job']['beat_id']} to generate")
                        except Exception as e:                   # noqa: BLE001  never let a nudge kill the run
                            _log(f"tab{i} nudge failed {cur['job']['beat_id']}: {e}"[:200])
                            cur.update(nudged=True, next_read=time.time() + 15)
                    else:
                        failures.append({"beat": cur["job"]["beat_id"], "error": "text reply: " + texts[-1][:300],
                                         "conversation": cur["conv"]})
                        _log(f"tab{i} FAILED {cur['job']['beat_id']} (text reply after nudge)")
                        state[i] = None
                        tab.open_conversation(None)
                    continue
                if done:
                    img = imgs[-1]
                    body, ctype = API.download(tab.page, img["ptr"], cur["conv"])
                    out = project / cur["job"]["output_path"]
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(body)
                    rec = {"beat": cur["job"]["beat_id"], "file": str(out.relative_to(project)),
                           "sha256": hashlib.sha256(body).hexdigest(), "conversation": cur["conv"],
                           "message": img["node"], "asset": img["ptr"], "w": img["w"], "h": img["h"],
                           "images_in_reply": len(imgs), "seconds": round(time.time() - cur["t0"]),
                           "bound_by": "reply-to-message (ChatGPT conversation API)",
                           "at": datetime.now().isoformat(timespec="seconds")}
                    results.append(rec)
                    manifest["images"].append(rec)
                    manifest_p.parent.mkdir(parents=True, exist_ok=True)
                    manifest_p.write_text(json.dumps(manifest, indent=1))
                    _log(f"tab{i} DONE {rec['beat']} in {rec['seconds']}s")
                    state[i] = None
                    if fresh_chat:                # earlier images in the chat pull new faces toward them
                        tab.open_conversation(None)
                elif time.time() - cur["t0"] > per_image_timeout_s:
                    failures.append({"beat": cur["job"]["beat_id"], "error": "timeout (not resubmitted)",
                                     "conversation": cur["conv"]})
                    _log(f"tab{i} TIMEOUT {cur['job']['beat_id']} (left in conversation {cur['conv']})")
                    state[i] = None
            main.page.wait_for_timeout(1500)   # cheap local loop; network reads happen only on kicks or the 15 s fallback
    return {"done": len(results), "failed": failures, "seconds": round(time.time() - t_run),
            "manifest": str(manifest_p)}
