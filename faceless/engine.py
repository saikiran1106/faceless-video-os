"""Durable, resumable production state for one video project.

State lives in `<project>/.faceless/run.json` and every transition is appended to
`<project>/.faceless/events.jsonl`, so any agent (Claude Code, Codex, a human)
can resume from exactly where the last one stopped.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .contracts import validate
from .io import append_jsonl, atomic_write_json, load_json, sha256_file, utc_now
from .stages import FORMATS, HOSTS, HUMAN_GATES, STAGE_ARTIFACTS, STAGE_DIRS, STAGE_SCHEMAS, STAGE_SKILLS, order_for


class StateError(RuntimeError):
    pass


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise ValueError("Project slug cannot be empty")
    return slug


class ProductionEngine:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.control_dir = self.project_root / ".faceless"
        self.state_path = self.control_dir / "run.json"
        self.events_path = self.control_dir / "events.jsonl"

    # ---------------------------------------------------------------- setup
    @classmethod
    def initialize(
        cls,
        projects_root: Path,
        project_id: str,
        title: str,
        content_format: str,
        voice_mode: str,
        host: str,
        language: str = "en",
        budget_usd: float = 0.0,
    ) -> "ProductionEngine":
        if content_format not in FORMATS:
            raise ValueError(f"Unsupported format {content_format!r}; expected one of {FORMATS}")
        if host not in HOSTS:
            raise ValueError(f"Unsupported host {host!r}; expected one of {HOSTS}")
        order = order_for(voice_mode)
        engine = cls(Path(projects_root) / slugify(project_id))
        if engine.state_path.exists():
            raise StateError(f"Project already initialized: {engine.project_root}")
        for directory in STAGE_DIRS.values():
            (engine.project_root / directory).mkdir(parents=True, exist_ok=True)
        state = {
            "version": "1.0",
            "project_id": engine.project_root.name,
            "title": title,
            "format": content_format,
            "voice_mode": voice_mode,
            "host": host,
            "language": language,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "budget": {"approved_usd": float(budget_usd), "spent_usd": 0.0},
            "stage_order": list(order),
            "current_stage": order[0],
            "stages": {stage: {"status": "pending", "artifact": STAGE_ARTIFACTS[stage], "attempts": 0} for stage in order},
            "approvals": {gate: {"status": "pending"} for gate in HUMAN_GATES.values()},
            "locks": {},
            "provider_operations": {},
        }
        engine._write_state(state)
        engine._event("project_initialized", {"format": content_format, "voice_mode": voice_mode, "host": host})
        return engine

    def state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            raise StateError(f"Not a faceless project (no .faceless/run.json): {self.project_root}")
        return load_json(self.state_path)

    def artifact_path(self, stage: str) -> Path:
        return self.project_root / STAGE_ARTIFACTS[stage]

    # ---------------------------------------------------------------- gates
    def gate(self, stage: str) -> dict[str, Any]:
        """Validate the stage artifact and run its deterministic QA gate.

        The report is bound to the artifact's hash, so editing the artifact
        afterwards invalidates it.
        """
        from .gates import run_gate  # local import: gates imports engine helpers

        state = self.state()
        if stage not in state["stage_order"]:
            raise StateError(f"Unknown stage {stage!r} for this project")
        path = self.artifact_path(stage)
        if not path.exists():
            raise StateError(f"Missing artifact for {stage}: {path}")
        payload = load_json(path)
        validate(STAGE_SCHEMAS[stage], payload)
        result = run_gate(stage, payload, self.project_root, state)
        report = {"stage": stage, "artifact_sha256": sha256_file(path), "checked_at": utc_now(), **result.to_dict()}
        atomic_write_json(self.project_root / STAGE_DIRS[stage] / "gate_report.json", report)
        return report

    # ---------------------------------------------------------- transitions
    def complete(self, stage: str) -> dict[str, Any]:
        state = self.state()
        self._require_current(state, stage)
        entry = state["stages"][stage]
        if entry["status"] == "awaiting_human":
            raise StateError(f"{stage} is waiting for human approval: {entry.get('approval_gate')}")
        report = self.gate(stage)
        state = self.state()  # gate() does not mutate run.json, but re-read for safety
        entry = state["stages"][stage]
        entry["attempts"] = entry.get("attempts", 0) + 1
        if not report["passed"]:
            entry.update({"status": "failed", "gate_report": report, "failed_at": utc_now()})
            self._write_state(state)
            self._event("stage_failed", {"stage": stage, "critical": [f for f in report["findings"] if f["severity"] == "critical"]})
            return state
        entry.update({"status": "completed", "gate_report": report, "artifact_sha256": report["artifact_sha256"], "completed_at": utc_now()})
        if stage in HUMAN_GATES:
            entry["status"] = "awaiting_human"
            entry["approval_gate"] = HUMAN_GATES[stage]
        else:
            self._advance(state, stage)
        self._write_state(state)
        self._event("stage_completed", {"stage": stage, "status": entry["status"], "artifact_sha256": report["artifact_sha256"]})
        return state

    def approve(self, gate: str, approver: str, note: str = "") -> dict[str, Any]:
        state = self.state()
        if gate not in state["approvals"]:
            raise StateError(f"Unknown approval gate {gate!r}; expected one of {sorted(state['approvals'])}")
        waiting = next((name for name, entry in state["stages"].items() if entry.get("approval_gate") == gate and entry["status"] == "awaiting_human"), None)
        if not waiting:
            raise StateError(f"No stage is waiting for {gate}")
        stage_entry = state["stages"][waiting]
        if sha256_file(self.artifact_path(waiting)) != stage_entry.get("artifact_sha256"):
            raise StateError(f"{waiting} artifact changed after its gate passed; run `faceless complete` again before approving")
        state["approvals"][gate] = {"status": "approved", "approved_at": utc_now(), "approver": approver, "note": note}
        stage_entry["status"] = "completed"
        self._advance(state, waiting)
        self._write_state(state)
        self._event("human_approval", {"stage": waiting, "gate": gate, "approver": approver, "note": note})
        return state

    def reject(self, gate: str, approver: str, note: str) -> dict[str, Any]:
        """Send an awaiting stage back for rework with the human's reason recorded."""
        if not note.strip():
            raise StateError("A rejection needs a note saying what to change")
        state = self.state()
        waiting = next((name for name, entry in state["stages"].items() if entry.get("approval_gate") == gate and entry["status"] == "awaiting_human"), None)
        if not waiting:
            raise StateError(f"No stage is waiting for {gate}")
        state["stages"][waiting].update({"status": "failed", "rejected_at": utc_now(), "rejection_note": note})
        self._write_state(state)
        self._event("human_rejection", {"stage": waiting, "gate": gate, "approver": approver, "note": note})
        return state

    def reopen(self, stage: str, reason: str) -> dict[str, Any]:
        """Move the pipeline back to an earlier stage; everything after it must be redone."""
        if not reason.strip():
            raise StateError("Reopening a stage needs a recorded reason")
        state = self.state()
        order = state["stage_order"]
        if stage not in order:
            raise StateError(f"Unknown stage {stage!r}")
        affected = order[order.index(stage):]
        locked = [name for name, lock in state["locks"].items() if any(lock["path"] == STAGE_ARTIFACTS[s] for s in affected)]
        if locked:
            raise StateError(f"Locked artifacts would be invalidated: {locked}. Unlock them deliberately first.")
        for name in affected:
            entry = state["stages"][name]
            entry["status"] = "pending"
            for key in ("artifact_sha256", "gate_report", "completed_at", "approval_gate", "failed_at"):
                entry.pop(key, None)
            gate = HUMAN_GATES.get(name)
            if gate:
                state["approvals"][gate] = {"status": "pending"}
        state["current_stage"] = stage
        self._write_state(state)
        self._event("stage_reopened", {"stage": stage, "reason": reason, "invalidated": list(affected)})
        return state

    def lock(self, name: str, artifact_path: Path, reason: str = "") -> dict[str, Any]:
        state = self.state()
        resolved = Path(artifact_path).resolve()
        if not resolved.exists() or self.project_root not in resolved.parents:
            raise StateError("Locks require an existing file inside the project")
        digest = sha256_file(resolved)
        prior = state["locks"].get(name)
        if prior and prior["sha256"] != digest and not reason.strip():
            raise StateError("Changing a locked artifact requires --reason")
        state["locks"][name] = {"path": str(resolved.relative_to(self.project_root)), "sha256": digest, "locked_at": utc_now(), "reason": reason}
        self._write_state(state)
        self._event("artifact_locked", {"name": name, **state["locks"][name]})
        return state

    def unlock(self, name: str, reason: str) -> dict[str, Any]:
        if not reason.strip():
            raise StateError("Unlocking needs a recorded reason")
        state = self.state()
        removed = state["locks"].pop(name, None)
        if removed is None:
            raise StateError(f"No lock named {name!r}")
        self._write_state(state)
        self._event("artifact_unlocked", {"name": name, "reason": reason})
        return state

    def record_cost(self, amount_usd: float, provider: str, operation_id: str, stage: str) -> dict[str, Any]:
        """Record a paid provider call. Idempotent per operation_id; enforces the budget."""
        if amount_usd < 0 or not operation_id:
            raise ValueError("Cost must be non-negative and operation_id is required")
        state = self.state()
        seen = state.setdefault("provider_operations", {})
        if operation_id in seen:
            return state
        projected = state["budget"]["spent_usd"] + amount_usd
        if projected > state["budget"]["approved_usd"] + 1e-9:
            raise StateError(
                f"Budget exceeded: {projected:.2f} > approved {state['budget']['approved_usd']:.2f} USD. "
                "Ask the human to raise it with `faceless budget`."
            )
        seen[operation_id] = {"provider": provider, "stage": stage, "amount_usd": amount_usd, "recorded_at": utc_now()}
        state["budget"]["spent_usd"] = round(projected, 6)
        self._write_state(state)
        self._event("cost_recorded", {"operation_id": operation_id, "provider": provider, "stage": stage, "amount_usd": amount_usd})
        return state

    def can_spend(self, amount_usd: float) -> bool:
        budget = self.state()["budget"]
        return budget["spent_usd"] + amount_usd <= budget["approved_usd"] + 1e-9

    def set_budget(self, approved_usd: float, approver: str) -> dict[str, Any]:
        state = self.state()
        state["budget"]["approved_usd"] = float(approved_usd)
        self._write_state(state)
        self._event("budget_changed", {"approved_usd": approved_usd, "approver": approver})
        return state

    # ---------------------------------------------------------------- next
    def next_action(self) -> dict[str, Any]:
        """A plain answer to 'what do I do now?' for humans and agents."""
        state = self.state()
        stage = state["current_stage"]
        if stage is None:
            return {"done": True, "message": "All stages complete. Upload the render and use 09-package/publishing_package.json."}
        entry = state["stages"][stage]
        project = str(self.project_root)
        out: dict[str, Any] = {
            "done": False,
            "stage": stage,
            "status": entry["status"],
            "skill": STAGE_SKILLS[stage],
            "artifact": STAGE_ARTIFACTS[stage],
        }
        if entry["status"] == "awaiting_human":
            gate = entry["approval_gate"]
            out["message"] = f"Waiting for the human at {gate}. Show them the artifact, then record their decision."
            out["commands"] = [f"faceless approve {project} {gate} --approver <name>", f"faceless reject {project} {gate} --note \"what to change\""]
            return out
        out["commands"] = _STAGE_HINTS.get((stage, state["voice_mode"]), _STAGE_HINTS.get((stage, "*"), []))
        out["commands"] = [cmd.format(p=project) for cmd in out["commands"]] + [f"faceless complete {project} {stage}"]
        if entry["status"] == "failed":
            report = entry.get("gate_report") or {}
            out["message"] = entry.get("rejection_note") or "The gate failed; fix the critical findings and complete again."
            out["critical_findings"] = [f for f in report.get("findings", []) if f.get("severity") == "critical"]
        else:
            out["message"] = f"Read skills/{STAGE_SKILLS[stage]}/SKILL.md, produce {STAGE_ARTIFACTS[stage]}, then complete the stage."
        return out

    # ------------------------------------------------------------- helpers
    def _advance(self, state: dict[str, Any], stage: str) -> None:
        order = state["stage_order"]
        index = order.index(stage)
        state["current_stage"] = order[index + 1] if index + 1 < len(order) else None

    def _require_current(self, state: dict[str, Any], stage: str) -> None:
        if stage not in state["stage_order"]:
            raise StateError(f"Unknown stage {stage!r}")
        if state["current_stage"] != stage:
            raise StateError(f"The current stage is {state['current_stage']!r}, not {stage!r}. Use `faceless reopen` to go back.")

    def _write_state(self, state: dict[str, Any]) -> None:
        state["updated_at"] = utc_now()
        atomic_write_json(self.state_path, state)

    def _event(self, event_type: str, data: dict[str, Any]) -> None:
        append_jsonl(self.events_path, {"event_type": event_type, "timestamp": utc_now(), "data": data})


_STAGE_HINTS: dict[tuple[str, str], list[str]] = {
    ("brief", "*"): ["Write {p}/01-brief/brief.json (see examples/ for a template)"],
    ("script", "tts"): ["Write {p}/02-script/script.json"],
    ("script", "upload"): ["faceless script from-transcript {p}", "Then fill hook/payoff/sections in {p}/02-script/script.json"],
    ("voice", "tts"): ["faceless voice generate {p} --dry-run", "faceless voice generate {p} --yes"],
    ("voice", "upload"): ["faceless voice ingest {p} /path/to/your_narration.mp3"],
    ("transcript", "*"): ["faceless transcribe {p}"],
    ("visual_bible", "*"): ["Write {p}/05-visual-bible/visual_bible.json", "faceless images sheets {p}  (optional reference sheets)"],
    ("beats", "*"): ["faceless beats build {p}", "Direct every beat: fill visual_objective, shot_scale, camera, character_ids, location_id"],
    ("keyframes", "*"): ["faceless images jobs {p}", "Generate per your host (see skills/faceless-visuals)", "faceless images manifest {p}", "faceless review contact-sheet {p}"],
    ("compose", "*"): ["faceless compose render {p} --platform youtube", "faceless compose report {p}"],
    ("package", "*"): ["faceless package draft {p}", "Fill titles/description/tags (vidIQ MCP if connected)"],
}
