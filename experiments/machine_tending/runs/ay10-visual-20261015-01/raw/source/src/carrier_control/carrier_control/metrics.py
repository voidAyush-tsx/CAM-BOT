"""Crash-resistant machine-tending CSV summary and JSONL event logger."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Callable, Dict
import uuid


SCHEMA_VERSION = "2.0"
SUMMARY_FIELDS = (
    "schema_version", "experiment_id", "trial_id", "git_commit",
    "parameter_config", "parameter_hash_sha256", "start_timestamp_utc",
    "end_timestamp_utc", "time_source", "cycle_time_s", "status",
    "success", "failure_state", "failure_reason", "carrier_repositions",
    "mode", "workpiece_final_state", "runtime_verified",
    "end_to_end_verified", "notes",
)
EVENT_FIELDS = (
    "schema_version", "experiment_id", "trial_id", "sequence",
    "timestamp_utc", "monotonic_elapsed_s", "state", "target",
    "reachability", "decision", "action", "result", "details",
)


class TrialRecordError(ValueError):
    """Malformed, duplicate, or evidence-overstating experiment record."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parameter_hash(config: Any) -> str:
    encoded = json.dumps(config, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_timestamp(value: str, field: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise TrialRecordError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise TrialRecordError(f"{field} must include a timezone")


def resolve_git_commit(start: Path | str) -> str:
    """Resolve the source commit with a bounded call; UNKNOWN is explicit."""
    location = Path(start).resolve()
    if location.is_file():
        location = location.parent
    try:
        result = subprocess.run(
            ["git", "-C", str(location), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=2,
        )
        commit = result.stdout.strip()
        if len(commit) == 40 and all(char in "0123456789abcdef" for char in commit):
            return commit
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass
    return "UNKNOWN"


def validate_trial_record(record: Dict[str, Any]) -> None:
    missing = [field for field in SUMMARY_FIELDS if field not in record]
    extra = sorted(set(record) - set(SUMMARY_FIELDS))
    if missing or extra:
        raise TrialRecordError(f"record fields invalid; missing={missing}, extra={extra}")
    if record["schema_version"] != SCHEMA_VERSION:
        raise TrialRecordError(f"schema_version must be {SCHEMA_VERSION}")
    required_strings = (
        "experiment_id", "trial_id", "git_commit", "parameter_config",
        "parameter_hash_sha256", "start_timestamp_utc", "end_timestamp_utc",
        "time_source", "status", "mode", "workpiece_final_state",
    )
    for field in required_strings:
        if not isinstance(record[field], str) or not record[field]:
            raise TrialRecordError(f"{field} must be a nonempty string")
    _parse_timestamp(record["start_timestamp_utc"], "start_timestamp_utc")
    _parse_timestamp(record["end_timestamp_utc"], "end_timestamp_utc")
    if (len(record["parameter_hash_sha256"]) != 64 or
            any(char not in "0123456789abcdef"
                for char in record["parameter_hash_sha256"])):
        raise TrialRecordError("parameter_hash_sha256 must be lowercase SHA-256")
    if record["time_source"] != "monotonic_duration+utc_wall_timestamps":
        raise TrialRecordError("unsupported time_source")
    duration = record["cycle_time_s"]
    if (isinstance(duration, bool) or not isinstance(duration, (int, float)) or
            not math.isfinite(duration) or duration < 0):
        raise TrialRecordError("cycle_time_s must be finite and nonnegative")
    if (isinstance(record["carrier_repositions"], bool) or
            not isinstance(record["carrier_repositions"], int) or
            record["carrier_repositions"] < 0):
        raise TrialRecordError("carrier_repositions must be a nonnegative integer")
    if record["status"] not in ("COMPLETE", "FAILED", "INCOMPLETE"):
        raise TrialRecordError("invalid status")
    if not isinstance(record["success"], bool):
        raise TrialRecordError("success must be boolean")
    if record["success"] != (record["status"] == "COMPLETE"):
        raise TrialRecordError("success must match COMPLETE status")
    if not record["success"] and (not record["failure_state"] or
                                  not record["failure_reason"]):
        raise TrialRecordError("failed/incomplete records require failure context")
    if record["mode"] not in ("controller", "visual_simulation"):
        raise TrialRecordError("mode must be controller or visual_simulation")
    if record["mode"] == "visual_simulation" and (
            record["runtime_verified"] or record["end_to_end_verified"]):
        raise TrialRecordError("visual simulation cannot be runtime/end-to-end verified")
    if record["end_to_end_verified"] and not (
            record["mode"] == "controller" and record["success"] and
            record["runtime_verified"]):
        raise TrialRecordError(
            "end-to-end verification requires successful controller runtime evidence"
        )


def validate_event(event: Dict[str, Any]) -> None:
    missing = [field for field in EVENT_FIELDS if field not in event]
    extra = sorted(set(event) - set(EVENT_FIELDS))
    if missing or extra:
        raise TrialRecordError(f"event fields invalid; missing={missing}, extra={extra}")
    if event["schema_version"] != SCHEMA_VERSION:
        raise TrialRecordError("event schema mismatch")
    for field in ("experiment_id", "trial_id", "timestamp_utc", "state",
                  "action", "result"):
        if not isinstance(event[field], str) or not event[field]:
            raise TrialRecordError(f"event {field} must be a nonempty string")
    _parse_timestamp(event["timestamp_utc"], "event timestamp_utc")
    if (not isinstance(event["sequence"], int) or event["sequence"] < 0 or
            isinstance(event["monotonic_elapsed_s"], bool) or
            not isinstance(event["monotonic_elapsed_s"], (int, float)) or
            not math.isfinite(event["monotonic_elapsed_s"]) or
            event["monotonic_elapsed_s"] < 0):
        raise TrialRecordError("event sequence/time invalid")
    if not isinstance(event["details"], dict):
        raise TrialRecordError("event details must be an object")


class ExperimentLogger:
    """One active trial; every line/row is flushed and fsynced before return."""

    def __init__(self, summary_path: Path | str, experiment_id: str,
                 git_commit: str, parameter_config: str, config: Any,
                 wall_clock: Callable[[], str] = utc_now,
                 steady_clock: Callable[[], float] = time.monotonic):
        if not experiment_id or not parameter_config or not git_commit:
            raise TrialRecordError("experiment/config/git identifiers are required")
        self.summary_path = Path(summary_path)
        self.event_path = self.summary_path.with_suffix(".events.jsonl")
        self.experiment_id = experiment_id
        self.git_commit = git_commit
        self.parameter_config = parameter_config
        self.parameter_hash = parameter_hash(config)
        self.wall_clock = wall_clock
        self.steady_clock = steady_clock
        self.active = None

    def begin_trial(self, mode: str, trial_id: str | None = None) -> str:
        if self.active is not None:
            raise TrialRecordError("a trial is already active")
        trial_id = trial_id or f"{self.experiment_id}-{uuid.uuid4()}"
        if self._trial_exists(trial_id) or trial_id in self._event_trial_ids():
            raise TrialRecordError(f"duplicate trial_id {trial_id}")
        self.active = {
            "trial_id": trial_id, "mode": mode,
            "start_timestamp_utc": self.wall_clock(),
            "start_monotonic": self.steady_clock(), "sequence": 0,
        }
        self.log_event(
            state="TRIAL", action="START", result="INCOMPLETE_PENDING",
            details={"git_commit": self.git_commit,
                     "parameter_config": self.parameter_config,
                     "parameter_hash_sha256": self.parameter_hash,
                     "time_source": "monotonic_duration+utc_wall_timestamps"},
        )
        return trial_id

    def log_event(self, *, state: str, target=None, reachability=None,
                  decision=None, action: str, result: str,
                  details: Dict[str, Any] | None = None) -> None:
        if self.active is None:
            raise TrialRecordError("no active trial")
        elapsed = max(0.0, self.steady_clock() - self.active["start_monotonic"])
        event = {
            "schema_version": SCHEMA_VERSION,
            "experiment_id": self.experiment_id,
            "trial_id": self.active["trial_id"],
            "sequence": self.active["sequence"],
            "timestamp_utc": self.wall_clock(),
            "monotonic_elapsed_s": round(elapsed, 9),
            "state": state or "UNKNOWN", "target": target,
            "reachability": reachability, "decision": decision,
            "action": action or "UNKNOWN", "result": result or "UNKNOWN",
            "details": details or {},
        }
        validate_event(event)
        self._append_jsonl(event)
        self.active["sequence"] += 1

    def finalize(self, *, success: bool, failure_state, failure_reason,
                 carrier_repositions: int, workpiece_final_state: str,
                 runtime_verified: bool, end_to_end_verified: bool,
                 notes: str, incomplete: bool = False) -> Dict[str, Any]:
        if self.active is None:
            raise TrialRecordError("no active trial")
        trial_id = self.active["trial_id"]
        if self._trial_exists(trial_id):
            raise TrialRecordError(f"duplicate final record for {trial_id}")
        if incomplete:
            status = "INCOMPLETE"
            success = False
            failure_state = failure_state or "INTERRUPTED"
            failure_reason = failure_reason or "TRIAL_DID_NOT_REACH_TERMINAL_STATE"
        else:
            status = "COMPLETE" if success else "FAILED"
        duration = max(0.0, self.steady_clock() - self.active["start_monotonic"])
        record = {
            "schema_version": SCHEMA_VERSION,
            "experiment_id": self.experiment_id, "trial_id": trial_id,
            "git_commit": self.git_commit,
            "parameter_config": self.parameter_config,
            "parameter_hash_sha256": self.parameter_hash,
            "start_timestamp_utc": self.active["start_timestamp_utc"],
            "end_timestamp_utc": self.wall_clock(),
            "time_source": "monotonic_duration+utc_wall_timestamps",
            "cycle_time_s": round(duration, 9), "status": status,
            "success": bool(success), "failure_state": failure_state,
            "failure_reason": failure_reason,
            "carrier_repositions": carrier_repositions,
            "mode": self.active["mode"],
            "workpiece_final_state": workpiece_final_state,
            "runtime_verified": bool(runtime_verified),
            "end_to_end_verified": bool(end_to_end_verified),
            "notes": notes or "",
        }
        validate_trial_record(record)
        self.log_event(
            state=failure_state or "SUCCESS", action="FINALIZE", result=status,
            details={"success": bool(success), "failure_reason": failure_reason,
                     "carrier_repositions": carrier_repositions,
                     "workpiece_final_state": workpiece_final_state},
        )
        self._append_summary(record)
        self.active = None
        return record

    def finalize_incomplete(self, reason: str, state="INTERRUPTED",
                            workpiece_state="UNKNOWN", notes=""):
        return self.finalize(
            success=False, failure_state=state, failure_reason=reason,
            carrier_repositions=0, workpiece_final_state=workpiece_state,
            runtime_verified=False, end_to_end_verified=False, notes=notes,
            incomplete=True,
        )

    def incomplete_trial_ids(self) -> set[str]:
        started, finalized = set(), set()
        if not self.event_path.exists():
            return started
        with self.event_path.open(encoding="utf-8") as stream:
            for line in stream:
                event = json.loads(line)
                if event.get("action") == "START":
                    started.add(event["trial_id"])
                if event.get("action") == "FINALIZE":
                    finalized.add(event["trial_id"])
        return started - finalized

    def _trial_exists(self, trial_id):
        if not self.summary_path.exists() or self.summary_path.stat().st_size == 0:
            return False
        with self.summary_path.open(newline="", encoding="utf-8") as stream:
            return any(row.get("trial_id") == trial_id for row in csv.DictReader(stream))

    def _event_trial_ids(self):
        if not self.event_path.exists():
            return set()
        with self.event_path.open(encoding="utf-8") as stream:
            return {json.loads(line)["trial_id"] for line in stream if line.strip()}

    def _append_jsonl(self, event):
        self.event_path.parent.mkdir(parents=True, exist_ok=True)
        with self.event_path.open("a", encoding="utf-8") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            stream.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            fcntl.flock(stream, fcntl.LOCK_UN)

    def _append_summary(self, record):
        self.summary_path.parent.mkdir(parents=True, exist_ok=True)
        with self.summary_path.open("a+", newline="", encoding="utf-8") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            stream.seek(0)
            existing = stream.read()
            rows = list(csv.DictReader(existing.splitlines())) if existing else []
            if any(row.get("trial_id") == record["trial_id"] for row in rows):
                raise TrialRecordError(f"duplicate final record for {record['trial_id']}")
            stream.seek(0, os.SEEK_END)
            writer = csv.DictWriter(stream, fieldnames=SUMMARY_FIELDS,
                                    extrasaction="raise")
            if not existing:
                writer.writeheader()
            writer.writerow(record)
            stream.flush()
            os.fsync(stream.fileno())
            fcntl.flock(stream, fcntl.LOCK_UN)
