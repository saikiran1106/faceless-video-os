"""Queue orchestration, resume/recovery and sanitized diagnostics."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import ADAPTER_VERSION, BrowserConfig
from . import jobstore as JS
from .batch import (MIN_PLAUSIBLE_S_PER_IMAGE, BatchMismatch,
                    ImplausiblySoon, batch_references,
                    build_batch_prompt, plan_batches, verify_batch)
from .imagegen import AuthRequired, ChatGPTImageAdapter
from .selectors import SelectorDrift

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


REDACT = re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|Bearer\s+\S+|session[-_]?token\S*|__Secure\S*|csrf\S*)", re.I)


def sanitize(text: str, limit: int = 1200) -> str:
    return REDACT.sub("[REDACTED]", (text or ""))[:limit]


class Diagnostics:
    def __init__(self, cfg: BrowserConfig):
        self.dir = cfg.diagnostics_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def capture(self, page, job_id: str, failure_class: str, detail: str,
                attempts: Optional[list] = None, adapter=None) -> dict:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base = self.dir / f"{ts}_{job_id}_{failure_class}"
        rec = {"timestamp": ts, "job_id": job_id, "failure_class": failure_class,
               "detail": sanitize(detail), "selector_attempts": attempts or [],
               "adapter_version": ADAPTER_VERSION}
        try:
            rec["url"] = page.url
            png = base.with_suffix(".png")
            page.screenshot(path=str(png), full_page=False)
            rec["screenshot"] = str(png)
            # small sanitized DOM excerpt - structure only, never storage/cookies
            dom = page.evaluate(
                "() => { const f=document.querySelector('form'); "
                "return f ? f.outerHTML.slice(0,1500) : document.body.innerHTML.slice(0,1500); }")
            rec["dom_excerpt"] = sanitize(dom, 1500)
        except Exception as e:                    # noqa: BLE001
            rec["capture_error"] = str(e)[:150]
        if adapter is not None and failure_class not in JS.NON_TECHNICAL:
            t = adapter.dump_trace(f"{ts}_{job_id}_{failure_class}")
            if t:
                rec["trace"] = t
        JS.atomic_write_json(base.with_suffix(".json"), rec)
        rec["report"] = str(base.with_suffix(".json"))
        return rec


class _Unreached(Exception):
    """Never raised; keeps the legacy per-slot writer out of the flow."""


class DuplicateSubmission(RuntimeError):
    """Raised instead of silently resubmitting an already-in-flight job."""


class QueueRunner:
    # 9:16 vertical is the series contract; overridable per run.
    DEFAULT_RATIO = 9 / 16

    def __init__(self, project: Path, queue_path: Path, cfg: BrowserConfig,
                 expect_ratio: Optional[float] = None):
        self.project = Path(project)
        self.queue_path = Path(queue_path)
        self.expect_ratio = self.DEFAULT_RATIO if expect_ratio is None else expect_ratio
        # The wording in the batch header must match what the validator enforces,
        # otherwise we ask for one shape and reject the other.
        self.aspect_label = ("16:9 landscape" if self.expect_ratio > 1.25
                             else "9:16 vertical" if self.expect_ratio < 0.8
                             else "square")
        self.cfg = cfg
        self.store = JS.JobStore(self.project / ".faceless" / "browser_jobs.json")
        self.receipts = self.project / "06-keyframes" / "receipts"
        self.receipts.mkdir(parents=True, exist_ok=True)
        self.staging = self.project / "06-keyframes" / "_staging"

    def load_queue(self) -> list[dict]:
        d = json.loads(self.queue_path.read_text(encoding="utf-8"))
        return d["jobs"] if isinstance(d, dict) and "jobs" in d else d

    def seed(self) -> int:
        return self.store.seed(self.load_queue(), self.project.name)

    # -------------------------------------------------------------- staging --
    def stage_batch(self, bi: int, jobs: list, images: list, ad) -> list:
        """Write a batch's images to a staging area, unbound to any beat.

        Nothing is written to a keyframe's output_path here. A staged image
        carries only where it came from - which batch, which slot, which beats
        that batch asked for - so the binding pass can assign it by what it
        actually depicts.
        """
        out = []
        self.staging.mkdir(parents=True, exist_ok=True)
        for pos, img in enumerate(images, 1):
            dest = self.staging / f"batch{bi:02d}_slot{pos:02d}.png"
            meta = ad.save_captured(img, dest, expect_ratio=self.expect_ratio)
            rec = {"batch": bi, "slot": pos, "path": str(dest),
                   "candidate_beats": [j["beat_id"] for j in jobs],
                   "candidate_keyframes": [j["keyframe_id"] for j in jobs],
                   "bound_to": None, **meta}
            out.append(rec)
        index = self.staging / "staged_index.json"
        existing = json.loads(index.read_text()) if index.exists() else {"images": []}
        existing["images"] = [i for i in existing["images"] if i["batch"] != bi] + out
        JS.atomic_write_json(index, existing)
        # Only advance as many jobs as there are images. A short batch used to
        # mark every job in it qa_pending, which claimed frames that were never
        # generated - 50 jobs reported done against 35 real images.
        for j in jobs[:len(images)]:
            self.store.transition(j["job_id"], JS.GENERATED)
            self.store.transition(j["job_id"], JS.DOWNLOADED, batch_index=bi)
            self.store.transition(j["job_id"], JS.DECODE_VERIFIED)
            self.store.transition(j["job_id"], JS.QA_PENDING,
                                  completed_at=datetime.now(timezone.utc).isoformat())
        for j in jobs[len(images):]:
            self.store.transition(j["job_id"], JS.FAILED_RETRYABLE,
                                  failure_class="batch_short",
                                  failure_detail=f"batch {bi} returned "
                                                 f"{len(images)}/{len(jobs)} images")
        return out

    # ------------------------------------------------------------- batches --
    def run_batched(self, size: int = 8, limit: Optional[int] = None,
                    only: Optional[list] = None) -> dict:
        """Generate in batches of `size`, taking bytes off the network.

        Per frame this replaces (attach + submit + poll DOM + fetch) with a
        share of one message, so the fixed overhead is paid once per batch
        instead of once per frame.
        """
        self.seed()
        # A frame that already has an image must never be re-generated. Both
        # PASSED and QA_PENDING mean "an image exists" - qa_pending is awaiting
        # a reviewer's binding decision, not awaiting generation. Treating only
        # TERMINAL as done re-queued 30 already-generated beats.
        done = JS.TERMINAL | {JS.QA_PENDING}
        queue = [j for j in self.load_queue()
                 if self.store.get(j["job_id"])["state"] not in done]
        if only:
            want = set(only)
            queue = [j for j in queue
                     if j["beat_id"] in want or j["keyframe_id"] in want]
        if limit is not None:
            queue = queue[:limit]
        batches = plan_batches(queue, size)
        summary = {"batches": len(batches), "frames": len(queue), "passed": 0,
                   "failed": 0, "blocked": None, "batch_reports": []}

        with ChatGPTImageAdapter(self.cfg) as ad:
            diag = Diagnostics(self.cfg)
            try:
                conv = ad.open_conversation(self.store.doc.get("conversation_url"))
                self.store.set_conversation(conv)
            except AuthRequired:
                summary["blocked"] = JS.AUTH_REQUIRED
                return summary

            # The ChatGPT Project page carries other episodes' artwork; none of
            # it is ours. Sweep it into the ignore set before the first batch.
            summary["drained_on_open"] = ad.capture.drain()

            existing_batches = set()
            index_file = self.staging / "staged_index.json"
            if index_file.exists():
                try:
                    existing_batches = {i["batch"] for i in json.loads(index_file.read_text()).get("images", []) if "batch" in i}
                except Exception:
                    pass
            start_bi = (max(existing_batches) + 1) if existing_batches else 1

            for bi_offset, jobs in enumerate(batches):
                bi = start_bi + bi_offset
                rep = self._one_batch(ad, diag, bi, jobs, summary)
                summary["batch_reports"].append(rep)
                if summary["blocked"]:
                    break
                # ChatGPT does not reliably honour a large batch: a 5-item
                # request came back with 4 images. When that happens we cannot
                # tell WHICH item was dropped, so order is untrustworthy and
                # nothing from that batch is filed. Fall back to one message
                # per frame for those frames - slower, but each image is then
                # unambiguously bound to its beat.
                if rep.get("status") in ("batch_mismatch", "batch_too_soon"):
                    rep["fallback"] = "per_frame"
                    recovered = 0
                    for j in jobs:
                        self.store.doc["jobs"][j["job_id"]]["state"] = JS.QUEUED
                        self.store.flush()
                        ad.capture.drain()
                        if self._one(ad, diag, j["job_id"], j) is True:
                            recovered += 1
                            summary["passed"] += 1
                            summary["failed"] -= 1
                    rep["recovered_per_frame"] = recovered
        return summary

    def _one_batch(self, ad, diag, bi: int, jobs: list, summary: dict) -> dict:
        ids = [j["keyframe_id"] for j in jobs]
        rep = {"batch": bi, "keyframes": ids, "status": "pending"}
        t0 = time.time()
        try:
            refs = batch_references(jobs)
            # our own uploads come back over the same endpoint; exclude by hash
            ad.capture.ignore_files(refs)
            for j in jobs:
                self.store.transition(j["job_id"], JS.UPLOADING, attempt=
                                      self.store.get(j["job_id"])["attempt"] + 1,
                                      conversation_url=self.store.doc["conversation_url"])
            names = ad.upload_references(refs)
            # ChatGPT re-encodes an upload before serving its preview, so the
            # echoed bytes do NOT hash to the local file and the by-hash ignore
            # misses them. Draining AFTER the attachments have rendered sweeps
            # those previews into the ignore set by their actual bytes.
            rep["drained_previews"] = ad.capture.drain()
            for j in jobs:
                self.store.transition(j["job_id"], JS.REFS_VERIFIED,
                                      attached_names=names,
                                      reference_hashes={r: JS.sha256_file(Path(r))
                                                        for r in (j.get("reference_paths") or [])})

            marker = ad.submit_prompt(build_batch_prompt(jobs, self.aspect_label))
            # Baseline AFTER the send: only responses that arrive from here on
            # can be this submission's output.
            since = time.time()
            if ad.is_conversation_url(ad.page.url):
                self.store.set_conversation(ad.page.url)
            for j in jobs:
                self.store.transition(j["job_id"], JS.SUBMITTED,
                                      assistant_turn_marker=marker,
                                      conversation_url=self.store.doc.get("conversation_url"),
                                      submitted_at=datetime.now(timezone.utc).isoformat())
                self.store.transition(j["job_id"], JS.GENERATING)

            timeout = max(self.cfg.generation_timeout_s, 150 * len(jobs))
            images = ad.wait_for_results(len(jobs), marker, timeout_s=timeout)
            rep["returned"] = len(images)
            rep["wait_s"] = round(time.time() - since, 1)

            # ChatGPT returns batch images OUT OF ORDER (verified: a 3-item
            # batch put item 3's picture in slot 1), and sometimes returns
            # fewer than asked. Position is therefore NOT identity. We stage
            # every image that came back and let a content-binding pass decide
            # which beat each one serves; beats left unbound are requeued.
            refused = getattr(ad, "last_turn_state", None)
            if not images and refused:
                raise RuntimeError(f"batch refused by the model ({refused})")
            staged = self.stage_batch(bi, jobs, images, ad)
            rep["staged"] = len(staged)
            rep["expected"] = len(jobs)
            rep.update(status="staged", total_s=round(time.time() - t0, 1),
                       per_frame_s=round((time.time() - t0) / max(1, len(staged)), 1))
            summary["passed"] += len(staged)
            return rep

        except _Unreached:
            for j, img in zip(jobs, images):
                meta = ad.save_captured(img, self.project / j["output_path"],
                                        expect_ratio=self.expect_ratio)
                self.store.transition(j["job_id"], JS.GENERATED)
                self.store.transition(j["job_id"], JS.DOWNLOADED, **meta)
                self.store.transition(j["job_id"], JS.DECODE_VERIFIED)
                self.store.transition(j["job_id"], JS.QA_PENDING,
                                      batch_index=bi, batch_position=jobs.index(j) + 1,
                                      completed_at=datetime.now(timezone.utc).isoformat())
                self.write_receipt(self.store.get(j["job_id"]))
                summary["passed"] += 1
            rep.update(status="ok", total_s=round(time.time() - t0, 1),
                       per_frame_s=round((time.time() - t0) / len(jobs), 1))
            return rep

        except (BatchMismatch, ImplausiblySoon) as e:
            # Never file a guess: without one distinct image per item we cannot
            # trust the ORDER either, so the whole batch is rewound.
            cls = ("batch_too_soon" if isinstance(e, ImplausiblySoon)
                   else "batch_mismatch")
            d = diag.capture(ad.page, f"batch{bi}", cls, str(e), adapter=ad)
            for j in jobs:
                self.store.transition(j["job_id"], JS.FAILED_RETRYABLE,
                                      failure_class=cls,
                                      failure_detail=d.get("report"))
            summary["failed"] += len(jobs)
            rep.update(status=cls, detail=str(e))
            return rep
        except AuthRequired as e:
            for j in jobs:
                self.store.transition(j["job_id"], JS.FAILED_RETRYABLE,
                                      failure_class=JS.AUTH_REQUIRED,
                                      failure_detail=str(e)[:200])
            summary["blocked"] = JS.AUTH_REQUIRED
            rep.update(status="auth_required")
            return rep
        except Exception as e:                    # noqa: BLE001
            cls = JS.classify(str(e))
            d = diag.capture(ad.page, f"batch{bi}", cls, str(e), adapter=ad)
            # Only fail what actually left the queue. A job still QUEUED was never
            # attempted in this batch, and QUEUED -> FAILED_RETRYABLE is not a legal
            # transition, so blanket-failing the batch raised InvalidTransition and
            # masked the real error. Leave untouched jobs queued for the next pass.
            failed = 0
            for j in jobs:
                if self.store.get(j["job_id"])["state"] == JS.QUEUED:
                    continue
                self.store.transition(j["job_id"], JS.FAILED_RETRYABLE,
                                      failure_class=cls, failure_detail=d.get("report"))
                failed += 1
            summary["failed"] += failed
            rep.update(status="error", detail=str(e)[:200])
            return rep

    # ------------------------------------------------------ conversation --
    def reset_for_new_conversation(self) -> int:
        """Forget the stored chat and rewind every unfinished job.

        A turn marker is only meaningful inside the conversation that produced
        it, so carrying one into a new chat would scope the wait to the wrong
        turn. Jobs that already HAVE an image are not touched.

        qa_pending counts as having an image: it means the picture exists and is
        waiting on a reviewer, not on a generator. Rewinding it used to send 17
        already-reviewed frames back to the queue, which would have spent the
        daily image limit regenerating pictures that were already on disk.
        """
        self.store.doc["conversation_url"] = None
        rewound = 0
        for rec in self.store.doc["jobs"].values():
            if rec["state"] in (JS.PASSED, JS.FAILED_TERMINAL, JS.QA_PENDING):
                continue
            rec.update(state=JS.QUEUED, attempt=0, assistant_turn_marker=None,
                       conversation_url=None, failure_class=None, failure_detail=None)
            rec["history"].append({"at": _now(), "state": JS.QUEUED,
                                   "reason": "new conversation requested"})
            rewound += 1
        self.store.flush()
        return rewound

    # -------------------------------------------------------------- guards
    def _submit_guard(self, job_id: str, prompt_sha: str) -> None:
        """Refuse to submit a job that is already in flight in this conversation.

        Recovering the existing result is `resume`'s job. Returning "passed"
        here instead would mark a keyframe complete that was never written to
        disk; resubmitting would spend a second generation for one beat.
        """
        if self.store.already_submitted(job_id, prompt_sha,
                                        self.store.doc.get("conversation_url")):
            raise DuplicateSubmission(
                f"{job_id} was already submitted in this conversation; "
                "run `studio_os browser resume` to recover its result")

    # ------------------------------------------------------------- receipts
    def write_receipt(self, rec: dict) -> Path:
        p = self.receipts / f"{rec['keyframe_id']}.receipt.json"
        JS.atomic_write_json(p, {**rec, "written_at": datetime.now(timezone.utc).isoformat()})
        return p

    # ---------------------------------------------------------------- run --
    def run(self, limit: Optional[int] = None, resume: bool = True,
            only: Optional[list] = None) -> dict:
        self.seed()
        want = set(only or [])
        # --only must restrict the sequential path too; it used to be honoured
        # by run_batched alone, so a "top up B04-B13" run regenerated every
        # other unfinished beat as well.
        queue = {j["job_id"]: j for j in self.load_queue()
                 if not want or j["beat_id"] in want or j["keyframe_id"] in want}
        summary = {"processed": 0, "passed": 0, "failed": 0, "skipped": 0, "blocked": None}

        with ChatGPTImageAdapter(self.cfg) as ad:
            diag = Diagnostics(self.cfg)
            try:
                conv = self.store.doc.get("conversation_url")
                conv = ad.open_conversation(conv)
                self.store.set_conversation(conv)
            except AuthRequired:
                summary["blocked"] = JS.AUTH_REQUIRED
                return summary

            for job_id, qjob in queue.items():
                rec = self.store.get(job_id)
                # QA_PENDING means an image exists and is awaiting a binding
                # decision - it is NOT awaiting generation. Treating only the
                # terminal states as done made a three-frame top-up re-process
                # all 62 jobs and reset 60 finished ones.
                if rec["state"] in (JS.PASSED, JS.FAILED_TERMINAL, JS.QA_PENDING):
                    summary["skipped"] += 1
                    continue
                if limit is not None and summary["processed"] >= limit:
                    break

                # ---- resume: an in-flight job may already have a result -----
                # A submitted job whose wait timed out is the important case:
                # the generation very likely COMPLETED and only our detection
                # missed it. Resubmitting would spend a second generation for
                # one beat, so we always look for the existing result first.
                recoverable = rec["state"] in (JS.SUBMITTED, JS.GENERATING) or (
                    rec["state"] == JS.FAILED_RETRYABLE
                    and rec.get("assistant_turn_marker") is not None
                    and rec.get("failure_class") in (JS.GENERATION_TIMEOUT,
                                                     JS.SELECTOR_DRIFT,
                                                     JS.DOWNLOAD_FAILURE))
                if resume and recoverable:
                    img, turn, status = ad.wait_for_image(
                        rec.get("assistant_turn_marker") or 0,
                        exclude_alts=set(rec.get("attached_names") or []))
                    if img is not None and status == "ok":
                        try:
                            meta = ad.download_image(
                                img, self.project / rec["output_path"], turn=turn,
                                expect_ratio=self.expect_ratio)
                            if self.store.get(job_id)["state"] == JS.FAILED_RETRYABLE:
                                self.store.transition(job_id, JS.UPLOADING,
                                                      recovery="existing result found")
                                self.store.transition(job_id, JS.REFS_VERIFIED)
                                self.store.transition(job_id, JS.SUBMITTED)
                                self.store.transition(job_id, JS.GENERATING)
                            self.store.transition(job_id, JS.GENERATED)
                            self.store.transition(job_id, JS.DOWNLOADED, **meta)
                            self.store.transition(job_id, JS.DECODE_VERIFIED)
                            self.store.transition(job_id, JS.QA_PENDING,
                                                  completed_at=datetime.now(timezone.utc).isoformat())
                            self.write_receipt(self.store.get(job_id))
                            summary["processed"] += 1
                            continue
                        except Exception as e:    # noqa: BLE001
                            # Recovery failed; fall through to a fresh attempt,
                            # but record why so it is not silent.
                            rec["recovery_error"] = str(e)[:200]
                            self.store.flush()

                summary["processed"] += 1
                ok = self._one(ad, diag, job_id, qjob)
                if ok is True:
                    summary["passed"] += 1
                elif ok in (JS.AUTH_REQUIRED, JS.CAPTCHA_REQUIRED):
                    summary["blocked"] = ok
                    break
                else:
                    summary["failed"] += 1
        return summary

    def _one(self, ad, diag, job_id: str, qjob: dict):
        rec = self.store.get(job_id)
        attempt = rec["attempt"] + 1
        if attempt > self.cfg.max_creative_attempts:
            self.store.transition(job_id, JS.FAILED_TERMINAL,
                                  failure_class="max_attempts",
                                  failure_detail=f"exceeded {self.cfg.max_creative_attempts} attempts")
            return False
        out = self.project / qjob["output_path"]
        if out.exists() and rec["state"] == JS.PASSED:
            # Belt and braces: a passed frame is never overwritten without a
            # recorded reason. The caller reaches here only after an explicit
            # reset, which writes `overwrite_reason` onto the record.
            if not rec.get("overwrite_reason"):
                return True

        t = {}
        t0 = time.time()
        try:
            # 1. references ------------------------------------------------
            self.store.transition(job_id, JS.UPLOADING, attempt=attempt,
                                  conversation_url=self.store.doc["conversation_url"])
            refs = qjob.get("reference_paths") or []
            hashes = {r: JS.sha256_file(Path(r)) for r in refs}
            names = ad.upload_references(refs) if refs else []
            # ChatGPT re-encodes an upload before serving its preview, so the
            # echoed bytes do NOT hash to the local file and the by-hash ignore
            # misses them. Draining AFTER the attachments have rendered sweeps
            # those previews into the ignore set by their actual bytes.
            t["drained_previews"] = ad.capture.drain() if refs else 0
            t["upload_s"] = round(time.time() - t0, 1)
            self.store.transition(job_id, JS.REFS_VERIFIED, reference_hashes=hashes,
                                  attached_names=names, timings=dict(t))

            # 2. idempotency guard ----------------------------------------
            self._submit_guard(job_id, qjob["prompt_sha256"])

            # 3. submit exactly once --------------------------------------
            marker = ad.submit_prompt(qjob["prompt"])
            since = time.time()   # only responses from here on are our result
            # The first submission inside the ChatGPT Project creates the
            # conversation; persist its URL so every later job, and any resume,
            # lands in the same chat rather than starting a fresh one.
            if ad.is_conversation_url(ad.page.url):
                if self.store.doc.get("conversation_url") != ad.page.url:
                    self.store.set_conversation(ad.page.url)
            self.store.transition(job_id, JS.SUBMITTED,
                                  assistant_turn_marker=marker,
                                  conversation_url=self.store.doc.get("conversation_url"),
                                  submitted_at=datetime.now(timezone.utc).isoformat())

            t["submit_s"] = round(time.time() - t0 - t["upload_s"], 1)

            # 4. wait for OUR image -----------------------------------------
            # Taken off the network rather than scraped out of the DOM: the
            # markup for turns and results moved twice during this build, while
            # the response stream did not.
            self.store.transition(job_id, JS.GENERATING, timings=dict(t))
            tg = time.time()
            got = ad.wait_for_results(1, marker, timeout_s=self.cfg.generation_timeout_s)
            t["generate_s"] = round(time.time() - tg, 1)
            if not got:
                d = diag.capture(ad.page, job_id, JS.GENERATION_TIMEOUT,
                                 f"no new image after submission (marker {marker})",
                                 adapter=ad)
                self.store.transition(job_id, JS.FAILED_RETRYABLE,
                                      failure_class=JS.GENERATION_TIMEOUT,
                                      failure_detail=d.get("report"))
                return False

            # 5. file + verify ----------------------------------------------
            self.store.transition(job_id, JS.GENERATED)
            td = time.time()
            meta = ad.save_captured(got[-1], self.project / qjob["output_path"],
                                    expect_ratio=self.expect_ratio)
            t["download_s"] = round(time.time() - td, 1)
            t["total_s"] = round(time.time() - t0, 1)
            self.store.transition(job_id, JS.DOWNLOADED, timings=dict(t), **meta)
            self.store.transition(job_id, JS.DECODE_VERIFIED)
            self.store.transition(job_id, JS.QA_PENDING,
                                  completed_at=datetime.now(timezone.utc).isoformat())
            self.write_receipt(self.store.get(job_id))
            return True

        except AuthRequired as e:
            self.store.transition(job_id, JS.FAILED_RETRYABLE,
                                  failure_class=JS.AUTH_REQUIRED, failure_detail=str(e)[:200])
            return JS.AUTH_REQUIRED
        except SelectorDrift as e:
            d = diag.capture(ad.page, job_id, JS.SELECTOR_DRIFT, str(e), e.attempts,
                             adapter=ad)
            self.store.transition(job_id, JS.FAILED_RETRYABLE,
                                  failure_class=JS.SELECTOR_DRIFT, failure_detail=d.get("report"))
            return False
        except Exception as e:                    # noqa: BLE001
            cls = JS.classify(str(e))
            d = diag.capture(ad.page, job_id, cls, str(e), adapter=ad)
            self.store.transition(job_id, JS.FAILED_RETRYABLE,
                                  failure_class=cls, failure_detail=d.get("report"))
            return cls if cls in JS.HUMAN_REQUIRED else False
