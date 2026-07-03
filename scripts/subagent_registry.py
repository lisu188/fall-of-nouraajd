#!/usr/bin/env python3
"""Controller-local subagent lifecycle registry with a read-only orphan sweeper.

The committed queue workbook stores durable queue state only. Live agent state
(which subagent occupies which controller slot, in which worktree, running which
validation) lives in this controller-LOCAL registry so an interrupted controller
can restart and still distinguish live, finalized, and orphaned workers.

The registry is a versioned JSON document persisted atomically (temp file plus
``os.replace``) under a sidecar advisory lock, completely separate from the
XLSX. It is live local state and must never be committed to the repository.

Registry file resolution order:

1. ``--registry <path>`` on the command line;
2. the ``GAME_SUBAGENT_REGISTRY_FILE`` environment variable;
3. the default ``<system temp dir>/fall-of-nouraajd/subagent_registry.json``
    (for example ``/tmp/fall-of-nouraajd/subagent_registry.json`` on Linux).

Lifecycle contract:

- ``register`` records an agent BEFORE it consumes a controller slot; duplicate
    active registrations for the same owner or claim ID are rejected.
- ``report`` updates ``lastSeenUtc`` only from a schema-valid, identity-matching
    payload (a verified poll result or a structured worker report). Stale or
    malformed evidence is rejected without touching the registry.
- ``finalize`` is the only way a record stops consuming capacity.
- ``sweep`` is strictly read-only: it reconciles records against worktree
    paths, ``git rev-parse --verify`` branch evidence, and (optionally) read-only
    workbook claim evidence, then prints UNREACHABLE/ORPHANED recommendations. It
    never deletes worktrees, kills processes, mutates the workbook, or rewrites
    the registry file; applying a recommendation requires the explicit ``mark``
    subcommand.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import shlex
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

try:
    from scripts import controller_policy, issue_queue
except ModuleNotFoundError:  # Support `python3 scripts/subagent_registry.py`.
    import controller_policy
    import issue_queue

SCHEMA_VERSION = 1
ENV_REGISTRY_FILE = "GAME_SUBAGENT_REGISTRY_FILE"
DEFAULT_REGISTRY_DIRECTORY = "fall-of-nouraajd"
DEFAULT_REGISTRY_FILENAME = "subagent_registry.json"
# Mechanical policy values derive from the single canonical source
# (scripts/controller_policy.py); do not restate the numbers here.
DEFAULT_STALE_AFTER_MINUTES = issue_queue.DEFAULT_HEARTBEAT_INTERVAL_MINUTES
DEFAULT_RETAIN_FINALIZED = controller_policy.value("finalized_retention")


class RegistryError(RuntimeError):
    """Raised for invalid registry operations or invalid registry content."""


class AgentRole(str, Enum):
    WORKER = "WORKER"
    QA = "QA"
    PROJECT_MANAGER = "PROJECT_MANAGER"
    RECOVERY = "RECOVERY"
    STANDBY = "STANDBY"


class AgentPhase(str, Enum):
    SPAWNED = "SPAWNED"
    SOURCE_INSPECTION = "SOURCE_INSPECTION"
    ROOT_CAUSE_ANALYSIS = "ROOT_CAUSE_ANALYSIS"
    IMPLEMENTATION = "IMPLEMENTATION"
    FOCUSED_VALIDATION = "FOCUSED_VALIDATION"
    FULL_VALIDATION = "FULL_VALIDATION"
    REVIEW = "REVIEW"
    REPORTING = "REPORTING"


class LifecycleStatus(str, Enum):
    REGISTERED = "REGISTERED"
    LIVE = "LIVE"
    UNREACHABLE = "UNREACHABLE"
    ORPHANED = "ORPHANED"
    FINALIZED = "FINALIZED"


class ExpectedExit(str, Enum):
    COMPLETE = "COMPLETE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RELEASED = "RELEASED"


ACTIVE_STATUSES = tuple(status for status in LifecycleStatus if status is not LifecycleStatus.FINALIZED)
MARKABLE_STATUSES = (LifecycleStatus.UNREACHABLE, LifecycleStatus.ORPHANED)
ALLOWED_TRANSITIONS: dict[LifecycleStatus, tuple[LifecycleStatus, ...]] = {
    LifecycleStatus.REGISTERED: (
        LifecycleStatus.LIVE,
        LifecycleStatus.UNREACHABLE,
        LifecycleStatus.ORPHANED,
        LifecycleStatus.FINALIZED,
    ),
    LifecycleStatus.LIVE: (
        LifecycleStatus.LIVE,
        LifecycleStatus.UNREACHABLE,
        LifecycleStatus.ORPHANED,
        LifecycleStatus.FINALIZED,
    ),
    LifecycleStatus.UNREACHABLE: (
        LifecycleStatus.LIVE,
        LifecycleStatus.ORPHANED,
        LifecycleStatus.FINALIZED,
    ),
    LifecycleStatus.ORPHANED: (
        LifecycleStatus.LIVE,
        LifecycleStatus.UNREACHABLE,
        LifecycleStatus.FINALIZED,
    ),
    LifecycleStatus.FINALIZED: (),
}
REPORT_REQUIRED_KEYS = ("owner", "lastSeenUtc")
REPORT_OPTIONAL_KEYS = ("registrationId", "claimId", "phase", "validationCommand", "changedFiles", "note")
REPORT_ALLOWED_KEYS = frozenset(REPORT_REQUIRED_KEYS + REPORT_OPTIONAL_KEYS)


@dataclass
class AgentRecord:
    registrationId: str
    owner: str
    role: str
    phase: str
    status: str
    expectedExit: str
    issue: str
    claimId: str
    worktree: str
    branch: str
    validationCommand: str
    changedFiles: list[str]
    spawnedAtUtc: str
    lastSeenUtc: str
    finalizedAtUtc: str = ""
    exitResult: str = ""
    lastNote: str = ""

    def isActive(self) -> bool:
        return self.status != LifecycleStatus.FINALIZED.value


@dataclass
class Registry:
    schemaVersion: int = SCHEMA_VERSION
    records: list[AgentRecord] = field(default_factory=list)


def utcNow() -> datetime:
    return issue_queue.utcNow()


def formatUtc(value: datetime) -> str:
    return issue_queue.formatUtc(value)


def parseUtc(value: Any) -> datetime | None:
    return issue_queue.parseUtc(value)


def defaultRegistryPath() -> Path:
    return Path(tempfile.gettempdir()) / DEFAULT_REGISTRY_DIRECTORY / DEFAULT_REGISTRY_FILENAME


def resolveRegistryPath(rawPath: str | Path | None) -> Path:
    if rawPath:
        path = Path(rawPath)
    elif os.environ.get(ENV_REGISTRY_FILE):
        path = Path(os.environ[ENV_REGISTRY_FILE])
    else:
        path = defaultRegistryPath()
    return path.expanduser().resolve()


def enumValues(enumClass: type[Enum]) -> tuple[str, ...]:
    return tuple(member.value for member in enumClass)


def validateRecordPayload(record: Any, index: int) -> list[str]:
    prefix = f"records[{index}]"
    if not isinstance(record, dict):
        return [f"{prefix}: expected an object, got {type(record).__name__}"]
    errors: list[str] = []
    fieldNames = tuple(item.name for item in dataclasses.fields(AgentRecord))
    for name in fieldNames:
        if name not in record:
            errors.append(f"{prefix}: missing field {name!r}")
    for name in record:
        if name not in fieldNames:
            errors.append(f"{prefix}: unknown field {name!r}")
    if errors:
        return errors
    for name in fieldNames:
        expected = list if name == "changedFiles" else str
        if not isinstance(record[name], expected):
            errors.append(f"{prefix}: field {name!r} must be {expected.__name__}")
    if errors:
        return errors
    if any(not isinstance(entry, str) for entry in record["changedFiles"]):
        errors.append(f"{prefix}: changedFiles entries must be strings")
    for name, enumClass in (
        ("role", AgentRole),
        ("phase", AgentPhase),
        ("status", LifecycleStatus),
        ("expectedExit", ExpectedExit),
    ):
        if record[name] not in enumValues(enumClass):
            errors.append(f"{prefix}: {name} {record[name]!r} is not one of {sorted(enumValues(enumClass))}")
    if record["exitResult"] and record["exitResult"] not in enumValues(ExpectedExit):
        errors.append(f"{prefix}: exitResult {record['exitResult']!r} is not one of {sorted(enumValues(ExpectedExit))}")
    for name in ("registrationId", "owner"):
        if not record[name].strip():
            errors.append(f"{prefix}: {name} must be non-empty")
    for name in ("spawnedAtUtc", "lastSeenUtc"):
        if parseUtc(record[name]) is None:
            errors.append(f"{prefix}: {name} {record[name]!r} is not a valid UTC timestamp")
    isFinalized = record["status"] == LifecycleStatus.FINALIZED.value
    if isFinalized and parseUtc(record["finalizedAtUtc"]) is None:
        errors.append(f"{prefix}: FINALIZED records require a valid finalizedAtUtc")
    if isFinalized and not record["exitResult"]:
        errors.append(f"{prefix}: FINALIZED records require exitResult")
    if not isFinalized and record["finalizedAtUtc"]:
        errors.append(f"{prefix}: only FINALIZED records may carry finalizedAtUtc")
    return errors


def validateRegistryPayload(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return [f"registry root: expected an object, got {type(payload).__name__}"]
    errors: list[str] = []
    version = payload.get("schemaVersion")
    if version != SCHEMA_VERSION:
        errors.append(f"schemaVersion: expected {SCHEMA_VERSION}, got {version!r}")
    records = payload.get("records")
    if not isinstance(records, list):
        return errors + [f"records: expected a list, got {type(records).__name__}"]
    for name in payload:
        if name not in ("schemaVersion", "records"):
            errors.append(f"registry root: unknown field {name!r}")
    seen_ids: set[str] = set()
    active_owners: set[str] = set()
    active_claims: set[str] = set()
    for index, record in enumerate(records):
        recordErrors = validateRecordPayload(record, index)
        errors.extend(recordErrors)
        if recordErrors:
            continue
        registration_id = record["registrationId"]
        if registration_id in seen_ids:
            errors.append(f"records[{index}]: duplicate registrationId {registration_id!r}")
        seen_ids.add(registration_id)
        if record["status"] == LifecycleStatus.FINALIZED.value:
            continue
        owner = record["owner"]
        if owner in active_owners:
            errors.append(f"records[{index}]: duplicate active registration for owner {owner!r}")
        active_owners.add(owner)
        claim_id = record["claimId"]
        if claim_id:
            if claim_id in active_claims:
                errors.append(f"records[{index}]: duplicate active registration for claim {claim_id!r}")
            active_claims.add(claim_id)
    return errors


def registryToPayload(registry: Registry) -> dict[str, Any]:
    return {
        "schemaVersion": registry.schemaVersion,
        "records": [dataclasses.asdict(record) for record in registry.records],
    }


def registryFromPayload(payload: Any) -> Registry:
    errors = validateRegistryPayload(payload)
    if errors:
        raise RegistryError("Invalid registry document: " + "; ".join(errors))
    records = [AgentRecord(**record) for record in payload["records"]]
    return Registry(schemaVersion=payload["schemaVersion"], records=records)


def serializeRegistry(registry: Registry) -> bytes:
    return (json.dumps(registryToPayload(registry), indent=2, sort_keys=True) + "\n").encode("utf-8")


def loadRegistry(registryPath: Path) -> Registry:
    if not registryPath.is_file():
        return Registry()
    raw_bytes = registryPath.read_bytes()
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RegistryError(f"Registry file {registryPath} is not valid JSON: {exc}") from exc
    return registryFromPayload(payload)


def saveRegistryAtomic(registry: Registry, registryPath: Path) -> None:
    errors = validateRegistryPayload(registryToPayload(registry))
    if errors:
        raise RegistryError("Refusing to persist invalid registry: " + "; ".join(errors))
    serialized = serializeRegistry(registry)
    registryPath.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="wb", dir=str(registryPath.parent), prefix=registryPath.name + ".", suffix=".tmp", delete=False
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, registryPath)
    except OSError:
        if temp_path.exists():
            temp_path.unlink()
        raise


def registryLock(registryPath: Path, lockTimeoutSeconds: float = 30.0) -> issue_queue.WorkbookLock:
    return issue_queue.WorkbookLock(registryPath, lockTimeoutSeconds)


def recordPayload(record: AgentRecord, now: datetime | None = None) -> dict[str, Any]:
    payload = dataclasses.asdict(record)
    reference = now or utcNow()
    payload["lastSeenAgeMinutes"] = issue_queue.ageMinutes(reference, parseUtc(record.lastSeenUtc))
    payload["consumesCapacity"] = record.isActive()
    return payload


def activeRecords(registry: Registry) -> list[AgentRecord]:
    return [record for record in registry.records if record.isActive()]


def findRecord(registry: Registry, registrationId: str | None = None, owner: str | None = None) -> AgentRecord:
    if registrationId:
        matches = [record for record in registry.records if record.registrationId == registrationId]
        if not matches:
            raise RegistryError(f"Unknown registrationId: {registrationId}")
        return matches[0]
    if owner:
        matches = [record for record in activeRecords(registry) if record.owner == owner]
        if not matches:
            raise RegistryError(f"No active registration for owner: {owner}")
        if len(matches) > 1:
            raise RegistryError(f"Owner has multiple active registrations, use --registration-id: {owner}")
        return matches[0]
    raise RegistryError("A record selector is required: pass --registration-id or --owner")


def requireTransition(record: AgentRecord, target: LifecycleStatus) -> None:
    current = LifecycleStatus(record.status)
    if target not in ALLOWED_TRANSITIONS[current]:
        raise RegistryError(
            f"Invalid lifecycle transition {current.value} -> {target.value} "
            f"for {record.owner} ({record.registrationId})"
        )


def registerAgent(
    registryPath: Path,
    owner: str,
    role: str,
    issue: str = "",
    claimId: str = "",
    worktree: str = "",
    branch: str = "",
    validationCommand: str = "",
    phase: str = AgentPhase.SPAWNED.value,
    expectedExit: str = ExpectedExit.COMPLETE.value,
    lockTimeoutSeconds: float = 30.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Register a subagent BEFORE it consumes a controller slot."""

    timestamp = formatUtc(now or utcNow())
    record = AgentRecord(
        registrationId=uuid.uuid4().hex,
        owner=owner.strip(),
        role=role,
        phase=phase,
        status=LifecycleStatus.REGISTERED.value,
        expectedExit=expectedExit,
        issue=issue.strip(),
        claimId=claimId.strip(),
        worktree=worktree.strip(),
        branch=branch.strip(),
        validationCommand=validationCommand.strip(),
        changedFiles=[],
        spawnedAtUtc=timestamp,
        lastSeenUtc=timestamp,
    )
    with registryLock(registryPath, lockTimeoutSeconds):
        registry = loadRegistry(registryPath)
        for existing in activeRecords(registry):
            if existing.owner == record.owner:
                raise RegistryError(
                    f"Duplicate registration: owner {record.owner!r} already has active "
                    f"registration {existing.registrationId} ({existing.status})"
                )
            if record.claimId and existing.claimId == record.claimId:
                raise RegistryError(
                    f"Duplicate registration: claim {record.claimId!r} already registered "
                    f"to {existing.owner} ({existing.registrationId})"
                )
        registry.records.append(record)
        saveRegistryAtomic(registry, registryPath)
    return recordPayload(record, now=now)


def validateReportPayload(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return [f"report: expected an object, got {type(payload).__name__}"]
    errors = [f"report: missing required key {key!r}" for key in REPORT_REQUIRED_KEYS if key not in payload]
    errors += [f"report: unknown key {key!r}" for key in sorted(set(payload) - REPORT_ALLOWED_KEYS)]
    if errors:
        return errors
    for key in REPORT_ALLOWED_KEYS - {"changedFiles"}:
        if key in payload and not isinstance(payload[key], str):
            errors.append(f"report: key {key!r} must be a string")
    if "changedFiles" in payload:
        files = payload["changedFiles"]
        if not isinstance(files, list) or any(not isinstance(entry, str) for entry in files):
            errors.append("report: changedFiles must be a list of strings")
    if not errors and parseUtc(payload["lastSeenUtc"]) is None:
        errors.append(f"report: lastSeenUtc {payload['lastSeenUtc']!r} is not a valid UTC timestamp")
    if not errors and "phase" in payload and payload["phase"] not in enumValues(AgentPhase):
        errors.append(f"report: phase {payload['phase']!r} is not one of {sorted(enumValues(AgentPhase))}")
    return errors


def reportAgent(
    registryPath: Path,
    payload: dict[str, Any],
    registrationId: str | None = None,
    lockTimeoutSeconds: float = 30.0,
) -> dict[str, Any]:
    """Apply a schema-valid poll/report payload; the only path that advances lastSeenUtc."""

    errors = validateReportPayload(payload)
    if errors:
        raise RegistryError("Rejected report payload: " + "; ".join(errors))
    with registryLock(registryPath, lockTimeoutSeconds):
        registry = loadRegistry(registryPath)
        selector = registrationId or payload.get("registrationId")
        record = findRecord(registry, registrationId=selector, owner=payload["owner"])
        if record.owner != payload["owner"]:
            raise RegistryError(f"Report owner {payload['owner']!r} does not match registered owner {record.owner!r}")
        if record.claimId and payload.get("claimId", record.claimId) != record.claimId:
            raise RegistryError(
                f"Report claimId {payload['claimId']!r} does not match registered claim {record.claimId!r}"
            )
        requireTransition(record, LifecycleStatus.LIVE)
        reported_last_seen = parseUtc(payload["lastSeenUtc"])
        current_last_seen = parseUtc(record.lastSeenUtc)
        assert reported_last_seen is not None
        if current_last_seen is not None and reported_last_seen < current_last_seen:
            raise RegistryError(
                f"Stale report evidence: lastSeenUtc {payload['lastSeenUtc']} is older than "
                f"recorded {record.lastSeenUtc} for {record.owner}"
            )
        record.status = LifecycleStatus.LIVE.value
        record.lastSeenUtc = formatUtc(reported_last_seen)
        if "phase" in payload:
            record.phase = payload["phase"]
        if "validationCommand" in payload:
            record.validationCommand = payload["validationCommand"]
        if "changedFiles" in payload:
            record.changedFiles = list(payload["changedFiles"])
        if "note" in payload:
            record.lastNote = payload["note"]
        saveRegistryAtomic(registry, registryPath)
        return recordPayload(record)


def pruneFinalized(registry: Registry, retainFinalized: int) -> list[str]:
    """Deterministically keep the newest ``retainFinalized`` FINALIZED records; return pruned ids."""

    if retainFinalized < 0:
        raise RegistryError("--retain-finalized must be non-negative")
    finalized = [record for record in registry.records if not record.isActive()]
    finalized.sort(key=lambda record: (record.finalizedAtUtc, record.registrationId), reverse=True)
    pruned_ids = {record.registrationId for record in finalized[retainFinalized:]}
    registry.records = [record for record in registry.records if record.registrationId not in pruned_ids]
    return sorted(pruned_ids)


def finalizeAgent(
    registryPath: Path,
    registrationId: str | None = None,
    owner: str | None = None,
    exitResult: str = ExpectedExit.COMPLETE.value,
    note: str = "",
    retainFinalized: int = DEFAULT_RETAIN_FINALIZED,
    lockTimeoutSeconds: float = 30.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Explicit finalization: the record stops consuming controller capacity."""

    if exitResult not in enumValues(ExpectedExit):
        raise RegistryError(f"exitResult {exitResult!r} is not one of {sorted(enumValues(ExpectedExit))}")
    with registryLock(registryPath, lockTimeoutSeconds):
        registry = loadRegistry(registryPath)
        record = findRecord(registry, registrationId=registrationId, owner=owner)
        requireTransition(record, LifecycleStatus.FINALIZED)
        record.status = LifecycleStatus.FINALIZED.value
        record.finalizedAtUtc = formatUtc(now or utcNow())
        record.exitResult = exitResult
        if note:
            record.lastNote = note
        pruned = pruneFinalized(registry, retainFinalized)
        saveRegistryAtomic(registry, registryPath)
        payload = recordPayload(record, now=now)
        payload["prunedRegistrationIds"] = pruned
        return payload


def markAgent(
    registryPath: Path,
    toStatus: str,
    registrationId: str | None = None,
    owner: str | None = None,
    reason: str = "",
    lockTimeoutSeconds: float = 30.0,
) -> dict[str, Any]:
    """Explicitly apply an UNREACHABLE/ORPHANED transition recommended by ``sweep``."""

    if toStatus not in {status.value for status in MARKABLE_STATUSES}:
        raise RegistryError(f"mark supports only {[status.value for status in MARKABLE_STATUSES]}, got {toStatus!r}")
    with registryLock(registryPath, lockTimeoutSeconds):
        registry = loadRegistry(registryPath)
        record = findRecord(registry, registrationId=registrationId, owner=owner)
        requireTransition(record, LifecycleStatus(toStatus))
        record.status = toStatus
        if reason:
            record.lastNote = reason
        saveRegistryAtomic(registry, registryPath)
        return recordPayload(record)


def capacitySummary(registry: Registry, now: datetime | None = None) -> dict[str, Any]:
    reference = now or utcNow()
    by_status = {status.value: 0 for status in LifecycleStatus}
    for record in registry.records:
        by_status[record.status] += 1
    return {
        "totalRecords": len(registry.records),
        "activeCount": len(activeRecords(registry)),
        "finalizedCount": by_status[LifecycleStatus.FINALIZED.value],
        "byStatus": by_status,
        "generatedAtUtc": formatUtc(reference),
    }


def listAgents(registryPath: Path, includeFinalized: bool = True, now: datetime | None = None) -> dict[str, Any]:
    registry = loadRegistry(registryPath)
    records = registry.records if includeFinalized else activeRecords(registry)
    return {
        "registry": str(registryPath),
        "schemaVersion": registry.schemaVersion,
        "summary": capacitySummary(registry, now=now),
        "records": [recordPayload(record, now=now) for record in records],
    }


def branchExists(repoRoot: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repoRoot), "rev-parse", "--verify", "--quiet", branch],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def loadWorkbookClaims(workbookPath: Path) -> dict[str, dict[str, Any]]:
    """Read claim evidence from the workbook via the read-only issue_queue loading APIs."""

    state = issue_queue.loadQueue(workbookPath, writable=False)
    try:
        claims: dict[str, dict[str, Any]] = {}
        for task in state.tasks:
            claim_id = str(task.values.get("Claim ID") or "").strip()
            if claim_id:
                owner = str(task.values.get("Owner") or "").strip()
                claims[claim_id] = {"issue": task.issueName, "owner": owner, "status": task.status}
        return claims
    finally:
        state.workbook.close()


def sweepRecommendation(
    record: AgentRecord,
    checks: dict[str, Any],
    staleAfterMinutes: int,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    recommended = "NONE"
    if checks["worktreeExists"] is False:
        recommended = LifecycleStatus.ORPHANED.value
        reasons.append(f"worktree {record.worktree} is missing")
    elif checks["branchExists"] is False:
        recommended = LifecycleStatus.UNREACHABLE.value
        reasons.append(f"branch {record.branch} is not resolvable via git rev-parse --verify")
    elif checks["lastSeenAgeMinutes"] is not None and checks["lastSeenAgeMinutes"] > staleAfterMinutes:
        recommended = LifecycleStatus.UNREACHABLE.value
        reasons.append(f"lastSeen is {checks['lastSeenAgeMinutes']} minutes old (threshold {staleAfterMinutes})")
    claim_evidence = checks.get("claimEvidence")
    if claim_evidence == "MISSING":
        reasons.append("claim evidence is missing from the workbook; verify before finalizing with RELEASED")
    elif claim_evidence == "OWNER_MISMATCH":
        reasons.append("workbook claim is owned by another agent; the row may have been reclaimed")
    elif claim_evidence == "NOT_IN_PROGRESS":
        reasons.append("workbook claim row is no longer IN_PROGRESS; finalize this registration explicitly")
    if record.status == recommended:
        recommended = "NONE"
    return recommended, reasons


def sweepRegistry(
    registryPath: Path,
    repoRoot: Path,
    workbookPath: Path | None = None,
    workbookClaims: dict[str, dict[str, Any]] | None = None,
    staleAfterMinutes: int = DEFAULT_STALE_AFTER_MINUTES,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Read-only reconciliation sweep. Never mutates the registry, worktrees, processes, or the workbook."""

    reference = now or utcNow()
    registry = loadRegistry(registryPath)
    if workbookClaims is None and workbookPath is not None:
        workbookClaims = loadWorkbookClaims(workbookPath)
    findings: list[dict[str, Any]] = []
    for record in activeRecords(registry):
        checks: dict[str, Any] = {
            "worktreeExists": Path(record.worktree).is_dir() if record.worktree else None,
            "branchExists": branchExists(repoRoot, record.branch) if record.branch else None,
            "lastSeenAgeMinutes": issue_queue.ageMinutes(reference, parseUtc(record.lastSeenUtc)),
            "claimEvidence": None,
        }
        if record.claimId and workbookClaims is not None:
            claim = workbookClaims.get(record.claimId)
            if claim is None:
                checks["claimEvidence"] = "MISSING"
            elif claim.get("owner") != record.owner:
                checks["claimEvidence"] = "OWNER_MISMATCH"
            elif claim.get("status") != issue_queue.STATUS_IN_PROGRESS:
                checks["claimEvidence"] = "NOT_IN_PROGRESS"
            else:
                checks["claimEvidence"] = "MATCH"
        recommended, reasons = sweepRecommendation(record, checks, staleAfterMinutes)
        finding = {
            "registrationId": record.registrationId,
            "owner": record.owner,
            "issue": record.issue,
            "status": record.status,
            "checks": checks,
            "recommendedStatus": recommended,
            "reasons": reasons,
        }
        if recommended != "NONE":
            # Shell-quote every interpolated field. registrationId/branch/worktree
            # are attacker-influenced (a subagent registers them), and reasons embed
            # branch/worktree text; json.dumps only double-quotes, which still lets
            # bash run $(...)/`...` command substitution when an operator pastes the
            # command. shlex.join produces a safe, copy-pasteable argv.
            finding["recommendedCommand"] = shlex.join(
                [
                    "python3",
                    "scripts/subagent_registry.py",
                    "mark",
                    "--registry",
                    str(registryPath),
                    "--registration-id",
                    record.registrationId,
                    "--to",
                    recommended,
                    "--reason",
                    "; ".join(reasons),
                ]
            )
        findings.append(finding)
    return {
        "registry": str(registryPath),
        "repoRoot": str(repoRoot),
        "workbook": str(workbookPath) if workbookPath else None,
        "readOnly": True,
        "staleAfterMinutes": staleAfterMinutes,
        "generatedAtUtc": formatUtc(reference),
        "summary": capacitySummary(registry, now=reference),
        "findings": findings,
        "recommendations": [finding for finding in findings if finding["recommendedStatus"] != "NONE"],
    }


def validateRegistryFile(registryPath: Path) -> dict[str, Any]:
    if not registryPath.is_file():
        return {"registry": str(registryPath), "exists": False, "errors": []}
    try:
        payload = json.loads(registryPath.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"registry": str(registryPath), "exists": True, "errors": [f"not valid JSON: {exc}"]}
    return {"registry": str(registryPath), "exists": True, "errors": validateRegistryPayload(payload)}


def printJson(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def addCommonArguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--registry",
        default=None,
        help=f"Registry file path. Default: ${ENV_REGISTRY_FILE} or {defaultRegistryPath()}",
    )
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)


def addSelectorArguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--registration-id", default=None, help="Exact registration id")
    parser.add_argument("--owner", default=None, help="Active owner, e.g. controller/<controller-id>/subagent-1")


def buildParser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    registerParser = subparsers.add_parser("register", help="Register a subagent before it consumes a slot")
    addCommonArguments(registerParser)
    registerParser.add_argument("--owner", required=True)
    registerParser.add_argument("--role", required=True, choices=sorted(enumValues(AgentRole)))
    registerParser.add_argument("--issue", default="")
    registerParser.add_argument("--claim-id", default="")
    registerParser.add_argument("--worktree", default="")
    registerParser.add_argument("--branch", default="")
    registerParser.add_argument("--validation-command", default="")
    registerParser.add_argument("--phase", default=AgentPhase.SPAWNED.value, choices=sorted(enumValues(AgentPhase)))
    registerParser.add_argument(
        "--expected-exit", default=ExpectedExit.COMPLETE.value, choices=sorted(enumValues(ExpectedExit))
    )

    reportParser = subparsers.add_parser("report", help="Apply a schema-validated poll/report payload")
    addCommonArguments(reportParser)
    reportParser.add_argument("--registration-id", default=None)
    reportParser.add_argument("--payload", default=None, help="Inline JSON report payload")
    reportParser.add_argument("--payload-file", default=None, help="Path to a JSON report payload")

    finalizeParser = subparsers.add_parser("finalize", help="Finalize a registration and release its capacity")
    addCommonArguments(finalizeParser)
    addSelectorArguments(finalizeParser)
    finalizeParser.add_argument(
        "--exit-result", default=ExpectedExit.COMPLETE.value, choices=sorted(enumValues(ExpectedExit))
    )
    finalizeParser.add_argument("--note", default="")
    finalizeParser.add_argument("--retain-finalized", type=int, default=DEFAULT_RETAIN_FINALIZED)

    listParser = subparsers.add_parser("list", help="List registry records and capacity summary")
    addCommonArguments(listParser)
    listParser.add_argument("--active-only", action="store_true", help="Hide FINALIZED records")

    sweepParser = subparsers.add_parser("sweep", help="Read-only reconciliation of records against evidence")
    addCommonArguments(sweepParser)
    sweepParser.add_argument("--repo", default=".", help="Repository root for git branch evidence")
    sweepParser.add_argument("--workbook", default=None, help="Optional workbook path for read-only claim evidence")
    sweepParser.add_argument("--stale-after-minutes", type=int, default=DEFAULT_STALE_AFTER_MINUTES)

    markParser = subparsers.add_parser("mark", help="Explicitly apply a sweep recommendation")
    addCommonArguments(markParser)
    addSelectorArguments(markParser)
    markParser.add_argument("--to", required=True, choices=sorted(status.value for status in MARKABLE_STATUSES))
    markParser.add_argument("--reason", default="")

    validateParser = subparsers.add_parser("validate", help="Validate the registry document schema")
    addCommonArguments(validateParser)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = buildParser()
    args = parser.parse_args(argv)
    registryPath = resolveRegistryPath(args.registry)
    try:
        if args.command == "register":
            printJson(
                registerAgent(
                    registryPath,
                    owner=args.owner,
                    role=args.role,
                    issue=args.issue,
                    claimId=args.claim_id,
                    worktree=args.worktree,
                    branch=args.branch,
                    validationCommand=args.validation_command,
                    phase=args.phase,
                    expectedExit=args.expected_exit,
                    lockTimeoutSeconds=args.lock_timeout_seconds,
                )
            )
            return 0
        if args.command == "report":
            raw = issue_queue.readTextOption(args.payload, args.payload_file, "payload")
            if not raw:
                raise RegistryError("report requires --payload or --payload-file")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise RegistryError(f"report payload is not valid JSON: {exc}") from exc
            printJson(
                reportAgent(
                    registryPath,
                    payload,
                    registrationId=args.registration_id,
                    lockTimeoutSeconds=args.lock_timeout_seconds,
                )
            )
            return 0
        if args.command == "finalize":
            printJson(
                finalizeAgent(
                    registryPath,
                    registrationId=args.registration_id,
                    owner=args.owner,
                    exitResult=args.exit_result,
                    note=args.note,
                    retainFinalized=args.retain_finalized,
                    lockTimeoutSeconds=args.lock_timeout_seconds,
                )
            )
            return 0
        if args.command == "list":
            printJson(listAgents(registryPath, includeFinalized=not args.active_only))
            return 0
        if args.command == "sweep":
            workbookPath = Path(args.workbook).expanduser().resolve() if args.workbook else None
            printJson(
                sweepRegistry(
                    registryPath,
                    repoRoot=Path(args.repo).expanduser().resolve(),
                    workbookPath=workbookPath,
                    staleAfterMinutes=args.stale_after_minutes,
                )
            )
            return 0
        if args.command == "mark":
            printJson(
                markAgent(
                    registryPath,
                    toStatus=args.to,
                    registrationId=args.registration_id,
                    owner=args.owner,
                    reason=args.reason,
                    lockTimeoutSeconds=args.lock_timeout_seconds,
                )
            )
            return 0
        if args.command == "validate":
            payload = validateRegistryFile(registryPath)
            printJson(payload)
            return 1 if payload["errors"] else 0
        raise RegistryError(f"Unsupported command {args.command}")
    except (RegistryError, issue_queue.QueueError, OSError, ValueError) as exc:
        print(f"subagent_registry: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
