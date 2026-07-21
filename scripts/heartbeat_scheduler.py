#!/usr/bin/env python3
"""Deterministic heartbeat planning and atomic multi-claim publication."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

try:
    from scripts import issue_queue
except ModuleNotFoundError:
    import issue_queue

STATE_NOT_DUE = "not_due"
STATE_DUE_SOON = "due_soon"
STATE_DUE = "due"
STATE_OVERDUE = "overdue"
STATE_RECOVERY_REQUIRED = "recovery_required"
DEFAULT_WARNING_MINUTES = 15


@dataclass(frozen=True)
class HeartbeatEvidence:
    reference: str
    observedAtUtc: datetime
    reachable: bool
    live: bool
    issueName: str
    owner: str
    claimId: str


@dataclass(frozen=True)
class HeartbeatRequest:
    issueName: str
    owner: str
    claimId: str
    progress: int
    note: str
    leaseMinutes: int
    evidence: HeartbeatEvidence


def parseNow(value: str | None) -> datetime:
    if not value:
        return issue_queue.utcNow()
    parsed = issue_queue.parseUtc(value)
    if parsed is None:
        raise issue_queue.QueueError(f"Invalid --now timestamp: {value!r}")
    return parsed


def requireMapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise issue_queue.QueueError(f"{label} must be a JSON object")
    return value


def requireString(mapping: dict[str, Any], key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise issue_queue.QueueError(f"{label}.{key} must be a non-empty string")
    return value.strip()


def requireBoolean(mapping: dict[str, Any], key: str, label: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise issue_queue.QueueError(f"{label}.{key} must be a boolean")
    return value


def requireInteger(mapping: dict[str, Any], key: str, label: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise issue_queue.QueueError(f"{label}.{key} must be an integer")
    return value


def parseHeartbeatRequest(value: Any, index: int) -> HeartbeatRequest:
    label = f"entries[{index}]"
    mapping = requireMapping(value, label)
    progress = requireInteger(mapping, "progress", label)
    if not 0 <= progress <= 99:
        raise issue_queue.QueueError(f"{label}.progress must be between 0 and 99")
    leaseMinutes = requireInteger(mapping, "leaseMinutes", label)
    if leaseMinutes < 1:
        raise issue_queue.QueueError(f"{label}.leaseMinutes must be positive")
    evidenceMapping = requireMapping(mapping.get("evidence"), f"{label}.evidence")
    observedText = requireString(evidenceMapping, "observedAtUtc", f"{label}.evidence")
    observedAt = issue_queue.parseUtc(observedText)
    if observedAt is None:
        raise issue_queue.QueueError(f"{label}.evidence.observedAtUtc must be a valid UTC timestamp")
    return HeartbeatRequest(
        issueName=requireString(mapping, "issueName", label),
        owner=requireString(mapping, "owner", label),
        claimId=requireString(mapping, "claimId", label),
        progress=progress,
        note=requireString(mapping, "note", label),
        leaseMinutes=leaseMinutes,
        evidence=HeartbeatEvidence(
            reference=requireString(evidenceMapping, "reference", f"{label}.evidence"),
            observedAtUtc=observedAt,
            reachable=requireBoolean(evidenceMapping, "reachable", f"{label}.evidence"),
            live=requireBoolean(evidenceMapping, "live", f"{label}.evidence"),
            issueName=requireString(evidenceMapping, "issueName", f"{label}.evidence"),
            owner=requireString(evidenceMapping, "owner", f"{label}.evidence"),
            claimId=requireString(evidenceMapping, "claimId", f"{label}.evidence"),
        ),
    )


def parseHeartbeatRequests(payload: Any) -> list[HeartbeatRequest]:
    if isinstance(payload, list):
        rawEntries = payload
    else:
        mapping = requireMapping(payload, "request")
        rawEntries = mapping.get("entries")
    if not isinstance(rawEntries, list) or not rawEntries:
        raise issue_queue.QueueError("request.entries must be a non-empty array")
    return [parseHeartbeatRequest(value, index) for index, value in enumerate(rawEntries)]


def controllerPrefix(owner: str) -> str:
    return owner.rsplit("/", 1)[0] if "/" in owner else owner


def validateBatchIdentity(requests: Sequence[HeartbeatRequest]) -> list[str]:
    errors: list[str] = []
    seenIssues: set[str] = set()
    seenClaims: set[tuple[str, str]] = set()
    prefixes = {controllerPrefix(request.owner) for request in requests}
    if len(prefixes) != 1:
        errors.append("all heartbeat entries must belong to one controller owner prefix")
    for request in requests:
        if request.issueName in seenIssues:
            errors.append(f"duplicate issue in heartbeat batch: {request.issueName}")
        seenIssues.add(request.issueName)
        claimKey = (request.owner, request.claimId)
        if claimKey in seenClaims:
            errors.append(f"duplicate owner/claim in heartbeat batch: {request.owner} {request.claimId}")
        seenClaims.add(claimKey)
    return errors


def heartbeatSchedule(
    task: issue_queue.TaskRecord,
    now: datetime,
    warningMinutes: int = DEFAULT_WARNING_MINUTES,
) -> dict[str, Any]:
    if warningMinutes < 0:
        raise issue_queue.QueueError("--warning-minutes must be non-negative")
    if task.status != issue_queue.STATUS_IN_PROGRESS:
        return {
            "issueName": task.issueName,
            "state": STATE_RECOVERY_REQUIRED,
            "reason": f"status is {task.status}, not IN_PROGRESS",
            "owner": str(task.values.get("Owner") or ""),
            "claimId": str(task.values.get("Claim ID") or ""),
        }
    health = issue_queue.claimTimingHealth(task, now)
    dueAt = health.heartbeatDueAtUtc
    if health.reclaimable:
        state = STATE_RECOVERY_REQUIRED
        reason = health.reclaimReason or "claim is reclaimable"
    elif health.heartbeatOverdue or health.leaseExpired:
        state = STATE_OVERDUE
        reason = health.reclaimReason or "heartbeat or lease is overdue"
    elif dueAt is None:
        state = STATE_RECOVERY_REQUIRED
        reason = "canonical heartbeat deadline is unavailable"
    elif dueAt <= now:
        state = STATE_DUE
        reason = "canonical heartbeat deadline has arrived"
    elif dueAt <= now + timedelta(minutes=warningMinutes):
        state = STATE_DUE_SOON
        reason = f"canonical heartbeat deadline is within {warningMinutes} minutes"
    else:
        state = STATE_NOT_DUE
        reason = "canonical heartbeat deadline is outside the warning window"
    return {
        "issueName": task.issueName,
        "state": state,
        "reason": reason,
        "owner": str(task.values.get("Owner") or ""),
        "claimId": str(task.values.get("Claim ID") or ""),
        **health.payload(),
    }


def scheduleSortKey(record: dict[str, Any]) -> tuple[str, str]:
    return str(record.get("heartbeatDueAtUtc") or "9999-12-31T23:59:59Z"), str(record.get("issueName") or "")


def validateEvidence(
    request: HeartbeatRequest,
    task: issue_queue.TaskRecord,
    now: datetime,
) -> list[str]:
    errors: list[str] = []
    evidence = request.evidence
    health = issue_queue.claimTimingHealth(task, now)
    if not evidence.reachable:
        errors.append("worker poll reports unreachable")
    if not evidence.live:
        errors.append("worker poll does not report a live worker")
    if evidence.issueName != request.issueName:
        errors.append("worker evidence issue name mismatch")
    if evidence.owner != request.owner:
        errors.append("worker evidence owner mismatch")
    if evidence.claimId != request.claimId:
        errors.append("worker evidence claim ID mismatch")
    if evidence.observedAtUtc > now:
        errors.append("worker evidence timestamp is in the future")
    oldestAccepted = now - timedelta(minutes=health.heartbeatIntervalMinutes)
    if evidence.observedAtUtc < oldestAccepted:
        errors.append(
            "worker evidence is stale relative to the canonical heartbeat interval "
            f"({health.heartbeatIntervalMinutes} minutes)"
        )
    return errors


def validateRequestAgainstState(
    state: issue_queue.QueueState,
    request: HeartbeatRequest,
    now: datetime,
    warningMinutes: int,
) -> tuple[issue_queue.TaskRecord | None, dict[str, Any], list[str]]:
    errors: list[str] = []
    try:
        task = issue_queue.requireClaim(state, request.issueName, request.claimId, request.owner)
    except issue_queue.QueueError as exc:
        return None, {"issueName": request.issueName, "state": STATE_RECOVERY_REQUIRED}, [str(exc)]
    schedule = heartbeatSchedule(task, now, warningMinutes)
    if task.status != issue_queue.STATUS_IN_PROGRESS:
        errors.append(f"heartbeat requires IN_PROGRESS, got {task.status}")
    if schedule["state"] == STATE_RECOVERY_REQUIRED:
        errors.append(schedule["reason"])
    errors.extend(validateEvidence(request, task, now))
    return task, schedule, errors


def requestPayload(request: HeartbeatRequest) -> dict[str, Any]:
    return {
        "issueName": request.issueName,
        "owner": request.owner,
        "claimId": request.claimId,
        "progress": request.progress,
        "note": request.note,
        "leaseMinutes": request.leaseMinutes,
        "evidence": {
            "reference": request.evidence.reference,
            "observedAtUtc": issue_queue.formatUtc(request.evidence.observedAtUtc),
            "reachable": request.evidence.reachable,
            "live": request.evidence.live,
            "issueName": request.evidence.issueName,
            "owner": request.evidence.owner,
            "claimId": request.evidence.claimId,
        },
    }


def publicationGuidance(requests: Sequence[HeartbeatRequest]) -> dict[str, Any]:
    issues = sorted(request.issueName for request in requests)
    return {
        "workbookOnly": True,
        "affectedIssues": issues,
        "title": f"[queue] Heartbeat {len(issues)} active claim{'s' if len(issues) != 1 else ''}",
        "body": [
            "Update only the queue workbook in one serialized heartbeat PR.",
            "List every affected issue and the worker-poll evidence reference.",
            "Validate the aggregate queue before squash-merging the workbook-only PR.",
        ],
        "validation": [
            "python3 scripts/workbook_queue.py validate",
            "git diff --check",
        ],
    }


def planHeartbeatBatch(
    workbookPath: Path,
    payload: Any,
    now: datetime | None = None,
    warningMinutes: int = DEFAULT_WARNING_MINUTES,
    ownerPrefix: str | None = None,
) -> dict[str, Any]:
    now = now or issue_queue.utcNow()
    requests = parseHeartbeatRequests(payload)
    identityErrors = validateBatchIdentity(requests)
    state = issue_queue.loadQueue(workbookPath, writable=False)
    try:
        schedules = [
            heartbeatSchedule(task, now, warningMinutes)
            for task in state.tasks
            if task.status == issue_queue.STATUS_IN_PROGRESS
            and (not ownerPrefix or str(task.values.get("Owner") or "").startswith(ownerPrefix))
        ]
        schedules.sort(key=scheduleSortKey)
        proposals: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []
        recovery: list[dict[str, Any]] = []
        for request in requests:
            task, schedule, errors = validateRequestAgainstState(state, request, now, warningMinutes)
            entry = {"request": requestPayload(request), "schedule": schedule}
            if errors:
                recovery.append({**entry, "errors": errors})
            elif schedule["state"] == STATE_NOT_DUE:
                excluded.append({**entry, "reason": "heartbeat is not due"})
            else:
                currentLease = issue_queue.parseUtc(task.values.get("Lease Until UTC")) if task else None
                requestedLease = now + timedelta(minutes=request.leaseMinutes)
                resultingLease = max(currentLease, requestedLease) if currentLease else requestedLease
                proposals.append(
                    {
                        **entry,
                        "resultingUpdatedAtUtc": issue_queue.formatUtc(now),
                        "resultingLeaseUntilUtc": issue_queue.formatUtc(resultingLease),
                    }
                )
        if identityErrors:
            recovery.insert(0, {"errors": identityErrors, "scope": "batch"})
        return {
            "capturedAtUtc": issue_queue.formatUtc(now),
            "warningMinutes": warningMinutes,
            "schedule": schedules,
            "proposals": proposals,
            "excluded": excluded,
            "recovery": recovery,
            "applicable": bool(proposals) and not excluded and not recovery,
            "publicationGuidance": publicationGuidance(requests),
        }
    finally:
        state.workbook.close()


def restoreWorkbookBytes(workbookPath: Path, originalBytes: bytes) -> None:
    workbookPath.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        prefix=f".{workbookPath.stem}.restore.",
        suffix=".tmp.xlsx",
        dir=workbookPath.parent,
        delete=False,
    )
    tempPath = Path(handle.name)
    try:
        handle.write(originalBytes)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        os.replace(tempPath, workbookPath)
        if os.name != "nt":
            directoryFd = os.open(workbookPath.parent, os.O_RDONLY)
            try:
                os.fsync(directoryFd)
            finally:
                os.close(directoryFd)
    finally:
        with contextlib.suppress(Exception):
            handle.close()
        with contextlib.suppress(FileNotFoundError):
            tempPath.unlink()


def applyHeartbeatBatch(
    workbookPath: Path,
    payload: Any,
    now: datetime | None = None,
    warningMinutes: int = DEFAULT_WARNING_MINUTES,
    lockTimeoutSeconds: float = 30.0,
) -> dict[str, Any]:
    now = now or issue_queue.utcNow()
    requests = parseHeartbeatRequests(payload)
    identityErrors = validateBatchIdentity(requests)
    if identityErrors:
        raise issue_queue.QueueError("Heartbeat batch validation failed:\n- " + "\n- ".join(identityErrors))
    with issue_queue.WorkbookLock(workbookPath, lockTimeoutSeconds):
        originalBytes = workbookPath.read_bytes()
        state = issue_queue.loadQueue(workbookPath, writable=True)
        try:
            missing = [header for header in issue_queue.ALL_HEADERS if header not in state.headers]
            if missing:
                raise issue_queue.QueueError("Workbook is missing required columns: " + ", ".join(missing))
            prepared: list[tuple[HeartbeatRequest, issue_queue.TaskRecord, dict[str, Any], datetime]] = []
            errors: list[str] = []
            for request in requests:
                task, schedule, requestErrors = validateRequestAgainstState(state, request, now, warningMinutes)
                if schedule.get("state") == STATE_NOT_DUE:
                    requestErrors.append("heartbeat is not due")
                if requestErrors or task is None:
                    errors.extend(f"{request.issueName}: {error}" for error in requestErrors)
                    continue
                currentLease = issue_queue.parseUtc(task.values.get("Lease Until UTC"))
                requestedLease = now + timedelta(minutes=request.leaseMinutes)
                resultingLease = max(currentLease, requestedLease) if currentLease else requestedLease
                prepared.append((request, task, schedule, resultingLease))
            if errors:
                raise issue_queue.QueueError("Heartbeat batch validation failed:\n- " + "\n- ".join(errors))
            for request, task, _schedule, resultingLease in prepared:
                issue_queue.setValue(state, task.row, "Progress %", request.progress)
                issue_queue.setValue(state, task.row, "Last Note", request.note)
                issue_queue.setValue(state, task.row, "Updated At UTC", issue_queue.formatUtc(now))
                issue_queue.setValue(state, task.row, "Lease Until UTC", issue_queue.formatUtc(resultingLease))
            try:
                issue_queue.atomicSave(state, workbookPath)
            except Exception:
                if not workbookPath.exists() or workbookPath.read_bytes() != originalBytes:
                    restoreWorkbookBytes(workbookPath, originalBytes)
                raise
            state = issue_queue.refreshTasks(state)
            updates: list[dict[str, Any]] = []
            for request, _task, schedule, _resultingLease in prepared:
                updatedTask = issue_queue.taskByName(state, request.issueName)
                updates.append(
                    {
                        "issueName": request.issueName,
                        "owner": request.owner,
                        "claimId": request.claimId,
                        "evidenceReference": request.evidence.reference,
                        "previousSchedule": schedule,
                        "task": issue_queue.taskPayload(updatedTask, state=state, now=now),
                        "resultingTiming": issue_queue.claimTimingHealth(updatedTask, now).payload(),
                    }
                )
            updates.sort(key=lambda item: item["issueName"])
            return {
                "applied": True,
                "capturedAtUtc": issue_queue.formatUtc(now),
                "atomic": True,
                "saveCount": 1,
                "updates": updates,
                "publicationGuidance": publicationGuidance(requests),
            }
        finally:
            state.workbook.close()


def readRequest(path: str) -> Any:
    if path == "-":
        import sys

        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def buildParser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("plan", "apply"):
        commandParser = subparsers.add_parser(command)
        commandParser.add_argument("--workbook", default=str(issue_queue.DEFAULT_WORKBOOK))
        commandParser.add_argument("--request-file", required=True)
        commandParser.add_argument("--now")
        commandParser.add_argument("--warning-minutes", type=int, default=DEFAULT_WARNING_MINUTES)
        commandParser.add_argument("--owner-prefix")
        commandParser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
        if command == "apply":
            commandParser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = buildParser()
    args = parser.parse_args(argv)
    try:
        workbookPath = issue_queue.resolveWorkbookPath(args.workbook)
        payload = readRequest(args.request_file)
        now = parseNow(args.now)
        if args.command == "plan" or args.dry_run:
            result = planHeartbeatBatch(
                workbookPath,
                payload,
                now=now,
                warningMinutes=args.warning_minutes,
                ownerPrefix=args.owner_prefix,
            )
        else:
            result = applyHeartbeatBatch(
                workbookPath,
                payload,
                now=now,
                warningMinutes=args.warning_minutes,
                lockTimeoutSeconds=args.lock_timeout_seconds,
            )
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0
    except (issue_queue.QueueError, OSError, ValueError, json.JSONDecodeError) as exc:
        import sys

        print(f"heartbeat_scheduler: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
