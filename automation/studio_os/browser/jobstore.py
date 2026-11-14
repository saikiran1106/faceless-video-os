"""Durable, atomic job-state store, failure taxonomy and receipt writing."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .config import ADAPTER_VERSION

# ---------------------------------------------------------------- states ----
QUEUED = "queued"
UPLOADING = "uploading_references"
REFS_VERIFIED = "references_verified"
SUBMITTED = "prompt_submitted"
GENERATING = "generating"
GENERATED = "generated"
DOWNLOADED = "downloaded"
DECODE_VERIFIED = "decode_verified"
QA_PENDING = "qa_pending"
PASSED = "passed"
FAILED_RETRYABLE = "failed_retryable"
FAILED_TERMINAL = "failed_terminal"

TRANSITIONS: Dict[str, set] = {
    QUEUED:          {UPLOADING, FAILED_TERMINAL},
    UPLOADING:       {REFS_VERIFIED, FAILED_RETRYABLE, FAILED_TERMINAL},
    REFS_VERIFIED:   {SUBMITTED, FAILED_RETRYABLE, FAILED_TERMINAL},
    SUBMITTED:       {GENERATING, GENERATED, FAILED_RETRYABLE, FAILED_TERMINAL},
    GENERATING:      {GENERATED, FAILED_RETRYABLE, FAILED_TERMINAL},
    GENERATED:       {DOWNLOADED, FAILED_RETRYABLE, FAILED_TERMINAL},
    DOWNLOADED:      {DECODE_VERIFIED, FAILED_RETRYABLE, FAILED_TERMINAL},
    DECODE_VERIFIED: {QA_PENDING, FAILED_RETRYABLE, FAILED_TERMINAL},
    QA_PENDING:      {PASSED, FAILED_RETRYABLE, FAILED_TERMINAL},
    PASSED:          set(),                       # terminal success
    # a retryable failure rewinds to the START of the job, never mid-flight
    FAILED_RETRYABLE: {QUEUED, UPLOADING, FAILED_TERMINAL},
    FAILED_TERMINAL: set(),
}

TERMINAL = {PASSED, FAILED_TERMINAL}

# -------------------------------------------------------------- failures ----
AUTH_REQUIRED = "authentication_required"
CAPTCHA_REQUIRED = "captcha_or_mfa_required"
CHATGPT_UNAVAILABLE = "chatgpt_unavailable"
SELECTOR_DRIFT = "selector_drift"
COMPOSER_UNAVAILABLE = "composer_unavailable"
UPLOAD_FAILURE = "upload_failure"
GENERATION_REFUSAL = "generation_refusal"
RATE_LIMIT = "rate_limit"
GENERATION_TIMEOUT = "generation_timeout"
DOWNLOAD_FAILURE = "download_failure"
DECODE_FAILURE = "decode_failure"
WRONG_DIMENSIONS = "wrong_dimensions"
SEMANTIC_QA_FAILURE = "semantic_qa_failure"
BROWSER_CRASH = "browser_crash"

# failures that must NEVER be auto-retried (need a human or are creative)
HUMAN_REQUIRED = {AUTH_REQUIRED, CAPTCHA_REQUIRED}
NON_TECHNICAL = {GENERATION_REFUSAL, SEMANTIC_QA_FAILURE}


def classify(exc_or_text: str) -> str:
    t = (exc_or_text or "").lower()
    if "captcha" in t or "verify you are human" in t or "two-factor" in t or "mfa" in t:
        return CAPTCHA_REQUIRED
    if "log in" in t or "sign in" in t or "session expired" in t or "unauthorized" in t:
        return AUTH_REQUIRED
    if "rate limit" in t or "hit your limit" in t or "too many requests" in t:
        return RATE_LIMIT
    if "no strategy matched" in t or "selectordrift" in t:
        return SELECTOR_DRIFT
    if "can't help" in t or "cannot create" in t or "violat" in t or "unable to generate" in t:
        return GENERATION_REFUSAL
    if "timeout" in t or "timed out" in t:
        return GENERATION_TIMEOUT
    if "download" in t:
        return DOWNLOAD_FAILURE
    if "decode" in t or "cannot identify image" in t:
        return DECODE_FAILURE
    if "crash" in t or "target closed" in t or "browser has been closed" in t:
        return BROWSER_CRASH
    if "net::" in t or "503" in t or "502" in t:
        return CHATGPT_UNAVAILABLE
    return SELECTOR_DRIFT


def backoff_seconds(attempt: int, failure: str) -> int:
    """Bounded exponential backoff. Human-required failures never auto-retry."""
    if failure in HUMAN_REQUIRED or failure in NON_TECHNICAL:
        return -1
    if failure == RATE_LIMIT:
        return min(900, 120 * (2 ** max(0, attempt - 1)))
    return min(120, 15 * (2 ** max(0, attempt - 1)))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write_json(path: Path, data) -> None:
    """Write via temp file + os.replace so a crash can never leave a partial state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


class InvalidTransition(RuntimeError):
    pass


class JobStore:
    """One JSON document per project holding every job's durable record."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.doc = {"version": "1.0", "adapter_version": ADAPTER_VERSION,
                    "conversation_url": None, "jobs": {}}
        if self.path.exists():
            self.doc = json.loads(self.path.read_text(encoding="utf-8"))
            self.doc.setdefault("jobs", {})

    # ------------------------------------------------------------ seeding --
    def seed(self, queue_jobs: Iterable[dict], project_id: str) -> int:
        added = 0
        for j in queue_jobs:
            jid = j["job_id"]
            if jid in self.doc["jobs"]:
                continue
            self.doc["jobs"][jid] = {
                "job_id": jid, "project_id": project_id,
                "beat_id": j["beat_id"], "keyframe_id": j["keyframe_id"],
                "prompt_sha256": j["prompt_sha256"],
                "reference_paths": j.get("reference_paths") or [],
                "reference_hashes": {},
                "output_path": j["output_path"],
                "conversation_url": None,
                "state": QUEUED, "attempt": 0,
                "submitted_at": None, "completed_at": None,
                "output_sha256": None, "dimensions": None, "format": None,
                "adapter_version": ADAPTER_VERSION,
                "failure_class": None, "failure_detail": None,
                "assistant_turn_marker": None,
                "pixels_reviewed": False,
                "history": [],
            }
            added += 1
        self.flush()
        return added

    # ---------------------------------------------------------- mutations --
    def get(self, job_id: str) -> dict:
        return self.doc["jobs"][job_id]

    def transition(self, job_id: str, new_state: str, **fields) -> dict:
        rec = self.doc["jobs"][job_id]
        cur = rec["state"]
        if new_state != cur and new_state not in TRANSITIONS.get(cur, set()):
            raise InvalidTransition(f"{job_id}: {cur} -> {new_state} is not allowed")
        rec["state"] = new_state
        rec.update(fields)
        rec["history"].append({"at": _now(), "state": new_state,
                               **({"failure_class": fields["failure_class"]}
                                  if fields.get("failure_class") else {})})
        self.flush()
        return rec

    def flush(self) -> None:
        atomic_write_json(self.path, self.doc)

    def set_conversation(self, url: str) -> None:
        self.doc["conversation_url"] = url
        self.flush()

    # ------------------------------------------------------------ queries --
    def pending(self) -> List[dict]:
        return [r for r in self.doc["jobs"].values() if r["state"] not in TERMINAL]

    def by_state(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for r in self.doc["jobs"].values():
            out[r["state"]] = out.get(r["state"], 0) + 1
        return out

    def already_submitted(self, job_id: str, prompt_sha: str, conversation_url: str) -> bool:
        """Idempotency guard: identical job+prompt+conversation already in flight
        or completed must never be submitted a second time."""
        rec = self.doc["jobs"].get(job_id)
        if not rec:
            return False
        return (rec["prompt_sha256"] == prompt_sha
                and rec.get("conversation_url") == conversation_url
                and rec["state"] in {SUBMITTED, GENERATING, GENERATED, DOWNLOADED,
                                     DECODE_VERIFIED, QA_PENDING, PASSED})
