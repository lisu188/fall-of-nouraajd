#!/usr/bin/env python3
"""Write-lease store that separates queue ownership from scoped source write permission.

Queue claims in the planning XLSX workbooks (see ``scripts/issue_queue.py``) represent
issue ownership only. They do not say whether a worker is actively editing shared source,
so overlapping claims can investigate concurrently yet still collide during writes. This
module adds a separate, JSON-file-backed write-lease layer:

- The store defaults to ``planning/write_leases.json`` (override with ``--store`` or the
  ``GAME_WRITE_LEASE_FILE`` environment variable). It is intentionally separate from the
  XLSX workbooks: no command in this module reads or mutates workbook claims, statuses,
  owners, or Claim IDs. Expiry and recovery are lease-lifecycle-only operations.
- Every mutating command runs under one cross-process sidecar lock file
  (``<store>.lock``, same advisory-lock pattern as ``issue_queue.WorkbookLock``), loads
  the store, applies an all-or-nothing batch, and atomically replaces the store file.
  A failed batch leaves the store byte-for-byte unchanged.
- A lease records controller ID, owner, claim ID, normalized source scope, lifecycle
  state (``ACTIVE``/``RELEASED``/``RECOVERED``), created/renewed/expires timestamps, and
  a recovery reason.
- Scope entries are normalized from four sources with confidence metadata, ordered
  ``pr-changed-files`` > ``dirty-worktree`` > ``worker-declared`` >
  ``workbook-target-files``. Workbook target files are planning-grade only: they are
  recorded, but excluded from conflict checking whenever any higher-confidence source is
  present, so coarse workbook target overlap alone cannot block disjoint writes.
- The effective scope is expanded deterministically over coupled areas: header plus
  implementation pairs (``src/**/X.h`` <-> ``X.cpp``), C++ type-registration sets
  (``src/*/C*TypeRegistration.cpp`` for new engine sources), CMake source registration
  (``CMakeLists.txt`` for new C++ sources), ``res/maps/<map>/`` content bundles
  (script.py/dialog*.json/config.json/map.json travel together), serialization pairs,
  and generated-resource producer/output pairs.
- Conflict rule: two ACTIVE, unexpired leases may not have overlapping expanded write
  scopes. Read-only inspection never requires a lease.

CLI: ``acquire``, ``renew``, ``release``, ``recover``, ``list``, ``validate``.
Exit codes: 0 success, 1 validation errors, 2 usage/store errors, 3 scope conflict.
"""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import sys
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from scripts import issue_queue
except ModuleNotFoundError:  # Support `python3 scripts/write_leases.py`.
    import issue_queue

DEFAULT_STORE = Path("planning/write_leases.json")
ENV_STORE = "GAME_WRITE_LEASE_FILE"
STORE_VERSION = 1

STATE_ACTIVE = "ACTIVE"
STATE_RELEASED = "RELEASED"
STATE_RECOVERED = "RECOVERED"
ALLOWED_STATES = (STATE_ACTIVE, STATE_RELEASED, STATE_RECOVERED)

SOURCE_PR_CHANGED_FILES = "pr-changed-files"
SOURCE_DIRTY_WORKTREE = "dirty-worktree"
SOURCE_WORKER_DECLARED = "worker-declared"
SOURCE_WORKBOOK_TARGET_FILES = "workbook-target-files"
# Ordered from most to least trustworthy evidence of what a worker actually writes.
SCOPE_SOURCE_CONFIDENCE = {
    SOURCE_PR_CHANGED_FILES: 0.95,
    SOURCE_DIRTY_WORKTREE: 0.85,
    SOURCE_WORKER_DECLARED: 0.6,
    SOURCE_WORKBOOK_TARGET_FILES: 0.4,
}

RULE_DIRECT = "direct"
RULE_HEADER_PAIR = "header-implementation-pair"
RULE_TYPE_REGISTRATION = "type-registration"
RULE_CMAKE_REGISTRATION = "cmake-source-registration"
RULE_MAP_BUNDLE = "map-bundle"
RULE_SERIALIZATION_PAIR = "serialization-pair"
RULE_GENERATED_RESOURCE = "generated-resource-pair"

DEFAULT_LEASE_MINUTES = 120

# Longest-prefix mapping from engine source areas to the type-registration translation
# units that must change when a new reflected type is added in that area.
TYPE_REGISTRATION_BY_AREA = (
    ("src/gui/object/", ("src/gui/object/CGuiWidgetTypeRegistration.cpp",)),
    ("src/gui/panel/", ("src/gui/panel/CGuiPanelTypeRegistration.cpp",)),
    ("src/gui/", ("src/gui/CGuiTypeRegistration.cpp", "src/gui/CAnimationTypeRegistration.cpp")),
    ("src/object/", ("src/object/CObjectTypeRegistration.cpp",)),
    ("src/handler/", ("src/handler/CHandlerTypeRegistration.cpp",)),
    ("src/core/", ("src/core/CCoreTypeRegistration.cpp",)),
)

# Files whose header/implementation halves define one serialization surface.
SERIALIZATION_PAIRS = {
    "src/core/CSerialization.h": ("src/core/CSerialization.cpp",),
    "src/core/CSerialization.cpp": ("src/core/CSerialization.h",),
}

# Producer scripts and the committed resources they regenerate (bidirectional).
GENERATED_RESOURCE_PAIRS = {
    "scripts/generate_screenshots.py": ("screenshots/",),
    "screenshots/": ("scripts/generate_screenshots.py",),
}

MAP_BUNDLE_PATTERN = re.compile(r"^(res/maps/[^/]+)(?:/|$)")
CPP_SOURCE_SUFFIXES = (".h", ".hpp", ".cpp")


class WriteLeaseError(issue_queue.QueueError):
    """Raised for invalid write-lease operations."""


class WriteLeaseConflict(WriteLeaseError):
    """Raised when a batch would overlap an ACTIVE, unexpired write scope."""

    def __init__(self, message: str, conflicts: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.conflicts = conflicts


def defaultRepoRoot() -> Path:
    return Path(__file__).resolve().parent.parent


def resolveStorePath(raw_path: str | Path | None) -> Path:
    if raw_path:
        path = Path(raw_path)
    elif os.environ.get(ENV_STORE):
        path = Path(os.environ[ENV_STORE])
    else:
        path = DEFAULT_STORE
    return path.expanduser().resolve()


def normalizeScopePath(raw_path: Any, repo_root: Path | None = None) -> str:
    text = str(raw_path or "").strip().replace("\\", "/")
    if not text:
        raise WriteLeaseError("Scope path must be non-empty")
    directory_hint = text.endswith("/")
    normalized = posixpath.normpath(text)
    if normalized in {".", ".."} or normalized.startswith(("../", "/")) or isWindowsDrivePath(normalized):
        raise WriteLeaseError(f"Scope path must be a relative repository path: {raw_path!r}")
    root = repo_root or defaultRepoRoot()
    if (root / normalized).is_dir():
        directory_hint = True
    return normalized + ("/" if directory_hint else "")


def isWindowsDrivePath(path: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:", path))


def normalizeScope(raw_entries: Iterable[tuple[Any, str]], repo_root: Path | None = None) -> list[dict[str, Any]]:
    """Normalize (path, source) pairs, deduplicating on path with the best source winning."""

    best_by_path: dict[str, dict[str, Any]] = {}
    for raw_path, source in raw_entries:
        if source not in SCOPE_SOURCE_CONFIDENCE:
            raise WriteLeaseError(f"Unknown scope source {source!r}; expected one of {sorted(SCOPE_SOURCE_CONFIDENCE)}")
        path = normalizeScopePath(raw_path, repo_root)
        entry = {"path": path, "source": source, "confidence": SCOPE_SOURCE_CONFIDENCE[source]}
        existing = best_by_path.get(path)
        if existing is None or entry["confidence"] > existing["confidence"]:
            best_by_path[path] = entry
    return sorted(best_by_path.values(), key=lambda entry: entry["path"])


def effectiveScopeEntries(entries: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop planning-grade workbook targets whenever concrete evidence exists."""

    concrete = [entry for entry in entries if entry["source"] != SOURCE_WORKBOOK_TARGET_FILES]
    return list(concrete) if concrete else list(entries)


def typeRegistrationFilesFor(path: str) -> tuple[str, ...]:
    for prefix, registrations in TYPE_REGISTRATION_BY_AREA:
        if path.startswith(prefix):
            return registrations
    return ()


def headerImplementationCounterpart(path: str) -> str | None:
    if not path.startswith(("src/", "native_plugins/")):
        return None
    if path.endswith(".h"):
        return path[: -len(".h")] + ".cpp"
    if path.endswith(".hpp"):
        return path[: -len(".hpp")] + ".cpp"
    if path.endswith(".cpp"):
        return path[: -len(".cpp")] + ".h"
    return None


def expandScope(entries: Sequence[dict[str, Any]], repo_root: Path | None = None) -> list[dict[str, Any]]:
    """Deterministically expand normalized scope entries over coupled write areas.

    Expansion runs to a fixed point; derived entries inherit the source/confidence of
    the entry they were expanded from and record the coupling rule plus origin path.
    """

    root = repo_root or defaultRepoRoot()
    expanded: dict[str, dict[str, Any]] = {}
    worklist: list[dict[str, Any]] = []
    for entry in entries:
        record = dict(entry)
        record.setdefault("rule", RULE_DIRECT)
        record.setdefault("expandedFrom", None)
        if record["path"] not in expanded:
            expanded[record["path"]] = record
            worklist.append(record)

    def derive(origin: dict[str, Any], path: str, rule: str) -> None:
        if path in expanded:
            return
        record = {
            "path": path,
            "source": origin["source"],
            "confidence": origin["confidence"],
            "rule": rule,
            "expandedFrom": origin["path"],
        }
        expanded[path] = record
        worklist.append(record)

    while worklist:
        origin = worklist.pop(0)
        path = origin["path"]

        for pair in SERIALIZATION_PAIRS.get(path, ()):
            derive(origin, pair, RULE_SERIALIZATION_PAIR)

        counterpart = headerImplementationCounterpart(path)
        if counterpart is not None:
            path_exists = (root / path).exists()
            if (root / counterpart).exists() or not path_exists:
                derive(origin, counterpart, RULE_HEADER_PAIR)
            if not path_exists:
                # New engine sources must be registered with the build and, for
                # reflected areas, with the matching C*TypeRegistration.cpp unit.
                derive(origin, "CMakeLists.txt", RULE_CMAKE_REGISTRATION)
                for registration in typeRegistrationFilesFor(path):
                    if registration != path:
                        derive(origin, registration, RULE_TYPE_REGISTRATION)

        bundle = MAP_BUNDLE_PATTERN.match(path)
        if bundle is not None:
            # script.py, dialog*.json, config.json, and map.json form one quest state
            # machine, so a touch anywhere in the map claims the whole bundle.
            derive(origin, bundle.group(1) + "/", RULE_MAP_BUNDLE)

        for generated in GENERATED_RESOURCE_PAIRS.get(path, ()):
            derive(origin, generated, RULE_GENERATED_RESOURCE)

    return sorted(expanded.values(), key=lambda entry: entry["path"])


def pathsOverlap(first: str, second: str) -> bool:
    if first == second:
        return True
    if first.endswith("/") and second.startswith(first):
        return True
    if second.endswith("/") and first.startswith(second):
        return True
    return False


def scopeOverlaps(first_paths: Iterable[str], second_paths: Iterable[str]) -> list[dict[str, str]]:
    overlaps: list[dict[str, str]] = []
    second_list = list(second_paths)
    for first in first_paths:
        for second in second_list:
            if pathsOverlap(first, second):
                overlaps.append({"path": first, "otherPath": second})
    return sorted(overlaps, key=lambda item: (item["path"], item["otherPath"]))


def expandedPaths(lease: dict[str, Any]) -> list[str]:
    return [entry["path"] for entry in lease.get("scope", {}).get("expanded", [])]


def leaseExpired(lease: dict[str, Any], now: Any) -> bool:
    expires = issue_queue.parseUtc(lease.get("expiresAtUtc"))
    return expires is None or expires <= now


def emptyStore() -> dict[str, Any]:
    return {"version": STORE_VERSION, "updatedAtUtc": None, "leases": []}


def loadStore(store_path: Path) -> dict[str, Any]:
    if not store_path.is_file():
        return emptyStore()
    try:
        store = json.loads(store_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WriteLeaseError(f"Cannot read write-lease store {store_path}: {exc}") from exc
    if not isinstance(store, dict) or not isinstance(store.get("leases"), list):
        raise WriteLeaseError(f"Write-lease store {store_path} is malformed: expected an object with a leases list")
    if store.get("version") != STORE_VERSION:
        raise WriteLeaseError(f"Unsupported write-lease store version {store.get('version')!r} in {store_path}")
    return store


def saveStore(store: dict[str, Any], store_path: Path, now: Any) -> None:
    store["updatedAtUtc"] = issue_queue.formatUtc(now)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=f".{store_path.stem}.",
        suffix=".tmp.json",
        dir=store_path.parent,
        delete=False,
    )
    temp_path = Path(temp_file.name)
    try:
        with temp_file as stream:
            json.dump(store, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, store_path)
        if os.name != "nt":
            directory_fd = os.open(store_path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def storeLock(store_path: Path, lock_timeout_seconds: float) -> issue_queue.WorkbookLock:
    """One cross-process lock file per store, mirroring the issue_queue workbook lock."""

    return issue_queue.WorkbookLock(store_path, lock_timeout_seconds)


def leasePayload(lease: dict[str, Any], now: Any) -> dict[str, Any]:
    payload = dict(lease)
    payload["expired"] = lease["state"] == STATE_ACTIVE and leaseExpired(lease, now)
    return payload


def findLease(store: dict[str, Any], lease_id: str) -> dict[str, Any]:
    for lease in store["leases"]:
        if lease.get("leaseId") == lease_id:
            return lease
    raise WriteLeaseError(f"Unknown lease id: {lease_id}")


def blockingConflicts(
    store: dict[str, Any],
    candidate_paths: Sequence[str],
    now: Any,
    ignore_lease_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for lease in store["leases"]:
        if lease.get("state") != STATE_ACTIVE or leaseExpired(lease, now):
            continue
        if ignore_lease_ids and lease.get("leaseId") in ignore_lease_ids:
            continue
        overlaps = scopeOverlaps(candidate_paths, expandedPaths(lease))
        if overlaps:
            conflicts.append(
                {
                    "leaseId": lease.get("leaseId"),
                    "owner": lease.get("owner"),
                    "claimId": lease.get("claimId"),
                    "issueName": lease.get("issueName"),
                    "overlaps": overlaps,
                }
            )
    return conflicts


def buildLeaseRequest(
    controller_id: str,
    owner: str,
    claim_id: str,
    scope_by_source: dict[str, Sequence[str]],
    issue_name: str | None = None,
    duration_minutes: int = DEFAULT_LEASE_MINUTES,
) -> dict[str, Any]:
    return {
        "controllerId": controller_id,
        "owner": owner,
        "claimId": claim_id,
        "issueName": issue_name,
        "durationMinutes": duration_minutes,
        "scope": {source: list(paths) for source, paths in scope_by_source.items() if paths},
    }


def prepareLease(request: dict[str, Any], now: Any, repo_root: Path | None = None) -> dict[str, Any]:
    controller_id = str(request.get("controllerId") or "").strip()
    owner = str(request.get("owner") or "").strip()
    claim_id = str(request.get("claimId") or "").strip()
    if not controller_id or not owner or not claim_id:
        raise WriteLeaseError("Lease requests require controllerId, owner, and claimId")
    duration_minutes = int(request.get("durationMinutes") or DEFAULT_LEASE_MINUTES)
    if duration_minutes < 1:
        raise WriteLeaseError("durationMinutes must be positive")
    raw_scope = request.get("scope") or {}
    raw_entries = [(path, source) for source, paths in raw_scope.items() for path in paths]
    if not raw_entries:
        raise WriteLeaseError("Lease requests require at least one scope path")
    requested = normalizeScope(raw_entries, repo_root)
    effective = effectiveScopeEntries(requested)
    expanded = expandScope(effective, repo_root)
    created = issue_queue.formatUtc(now)
    return {
        "leaseId": uuid.uuid4().hex,
        "controllerId": controller_id,
        "owner": owner,
        "claimId": claim_id,
        "issueName": request.get("issueName"),
        "state": STATE_ACTIVE,
        "createdAtUtc": created,
        "renewedAtUtc": created,
        "expiresAtUtc": issue_queue.formatUtc(now + timedelta(minutes=duration_minutes)),
        "releasedAtUtc": None,
        "recoveredAtUtc": None,
        "recoveryReason": None,
        "scope": {"requested": requested, "effective": effective, "expanded": expanded},
    }


def acquireLeases(
    store_path: Path,
    requests: Sequence[dict[str, Any]],
    now: Any = None,
    lock_timeout_seconds: float = 30.0,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Atomically acquire every requested lease or none of them."""

    if not requests:
        raise WriteLeaseError("acquire requires at least one lease request")
    now = now or issue_queue.utcNow()
    with storeLock(store_path, lock_timeout_seconds):
        store = loadStore(store_path)
        prepared: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        for request in requests:
            lease = prepareLease(request, now, repo_root)
            lease_conflicts = blockingConflicts(store, expandedPaths(lease), now)
            for accepted in prepared:
                overlaps = scopeOverlaps(expandedPaths(lease), expandedPaths(accepted))
                if overlaps:
                    lease_conflicts.append(
                        {
                            "leaseId": accepted["leaseId"],
                            "owner": accepted["owner"],
                            "claimId": accepted["claimId"],
                            "issueName": accepted.get("issueName"),
                            "overlaps": overlaps,
                            "withinBatch": True,
                        }
                    )
            if lease_conflicts:
                conflicts.append(
                    {
                        "request": {key: lease[key] for key in ("owner", "claimId", "issueName")},
                        "blockedBy": lease_conflicts,
                    }
                )
            prepared.append(lease)
        if conflicts:
            raise WriteLeaseConflict("Write scope conflict: acquisition batch rolled back; store unchanged", conflicts)
        store["leases"].extend(prepared)
        saveStore(store, store_path, now)
    return {"store": str(store_path), "acquired": [leasePayload(lease, now) for lease in prepared]}


def checkLeaseIdentity(lease: dict[str, Any], owner: str, claim_id: str) -> None:
    if lease.get("owner") != owner or lease.get("claimId") != claim_id:
        raise WriteLeaseError(
            f"Lease {lease.get('leaseId')} is owned by {lease.get('owner')!r}/{lease.get('claimId')!r}, "
            f"not {owner!r}/{claim_id!r}"
        )


def renewLeases(
    store_path: Path,
    lease_ids: Sequence[str],
    owner: str,
    claim_id: str,
    extend_minutes: int = DEFAULT_LEASE_MINUTES,
    now: Any = None,
    lock_timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Atomically renew every lease in the batch or none of them."""

    if not lease_ids:
        raise WriteLeaseError("renew requires at least one --lease-id")
    if extend_minutes < 1:
        raise WriteLeaseError("--extend-minutes must be positive")
    now = now or issue_queue.utcNow()
    with storeLock(store_path, lock_timeout_seconds):
        store = loadStore(store_path)
        leases = []
        for lease_id in lease_ids:
            lease = findLease(store, lease_id)
            checkLeaseIdentity(lease, owner, claim_id)
            if lease.get("state") != STATE_ACTIVE:
                raise WriteLeaseError(f"Lease {lease_id} is {lease.get('state')}, not {STATE_ACTIVE}")
            if leaseExpired(lease, now):
                raise WriteLeaseError(f"Lease {lease_id} expired at {lease.get('expiresAtUtc')}; re-acquire it")
            leases.append(lease)
        for lease in leases:
            lease["renewedAtUtc"] = issue_queue.formatUtc(now)
            lease["expiresAtUtc"] = issue_queue.formatUtc(now + timedelta(minutes=extend_minutes))
        saveStore(store, store_path, now)
        return {"store": str(store_path), "renewed": [leasePayload(lease, now) for lease in leases]}


def releaseLeases(
    store_path: Path,
    lease_ids: Sequence[str],
    owner: str,
    claim_id: str,
    now: Any = None,
    lock_timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Atomically release every lease in the batch or none of them."""

    if not lease_ids:
        raise WriteLeaseError("release requires at least one --lease-id")
    now = now or issue_queue.utcNow()
    with storeLock(store_path, lock_timeout_seconds):
        store = loadStore(store_path)
        leases = []
        for lease_id in lease_ids:
            lease = findLease(store, lease_id)
            checkLeaseIdentity(lease, owner, claim_id)
            if lease.get("state") != STATE_ACTIVE:
                raise WriteLeaseError(f"Lease {lease_id} is {lease.get('state')}, not {STATE_ACTIVE}")
            leases.append(lease)
        for lease in leases:
            lease["state"] = STATE_RELEASED
            lease["releasedAtUtc"] = issue_queue.formatUtc(now)
        saveStore(store, store_path, now)
        return {"store": str(store_path), "released": [leasePayload(lease, now) for lease in leases]}


def recoverLeases(
    store_path: Path,
    lease_ids: Sequence[str],
    reason: str,
    now: Any = None,
    lock_timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Atomically recover expired ACTIVE leases; canonical XLSX claims are never touched."""

    if not lease_ids:
        raise WriteLeaseError("recover requires at least one --lease-id")
    reason = reason.strip()
    if not reason:
        raise WriteLeaseError("recover requires a non-empty --reason")
    now = now or issue_queue.utcNow()
    with storeLock(store_path, lock_timeout_seconds):
        store = loadStore(store_path)
        leases = []
        for lease_id in lease_ids:
            lease = findLease(store, lease_id)
            if lease.get("state") != STATE_ACTIVE:
                raise WriteLeaseError(f"Lease {lease_id} is {lease.get('state')}, not {STATE_ACTIVE}")
            if not leaseExpired(lease, now):
                raise WriteLeaseError(
                    f"Lease {lease_id} is still valid until {lease.get('expiresAtUtc')}; "
                    "only expired leases can be recovered"
                )
            leases.append(lease)
        for lease in leases:
            lease["state"] = STATE_RECOVERED
            lease["recoveredAtUtc"] = issue_queue.formatUtc(now)
            lease["recoveryReason"] = reason
        saveStore(store, store_path, now)
        return {"store": str(store_path), "recovered": [leasePayload(lease, now) for lease in leases]}


def listLeases(
    store_path: Path,
    states: set[str] | None = None,
    owner: str | None = None,
    claim_id: str | None = None,
    now: Any = None,
) -> dict[str, Any]:
    """Read-only inspection of the store; never requires or takes a lease."""

    now = now or issue_queue.utcNow()
    store = loadStore(store_path)
    leases = []
    for lease in store["leases"]:
        if states and lease.get("state") not in states:
            continue
        if owner and lease.get("owner") != owner:
            continue
        if claim_id and lease.get("claimId") != claim_id:
            continue
        leases.append(leasePayload(lease, now))
    return {"store": str(store_path), "count": len(leases), "leases": leases}


def validateStore(store: dict[str, Any], now: Any = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    now = now or issue_queue.utcNow()
    seen_ids: set[str] = set()
    active_unexpired: list[dict[str, Any]] = []
    for index, lease in enumerate(store.get("leases", [])):
        label = f"Lease {lease.get('leaseId') or f'#{index}'}"
        lease_id = str(lease.get("leaseId") or "")
        if not lease_id:
            errors.append(f"{label}: missing leaseId")
        elif lease_id in seen_ids:
            errors.append(f"{label}: duplicate leaseId")
        else:
            seen_ids.add(lease_id)
        for field in ("controllerId", "owner", "claimId"):
            if not str(lease.get(field) or "").strip():
                errors.append(f"{label}: missing {field}")
        state = lease.get("state")
        if state not in ALLOWED_STATES:
            errors.append(f"{label}: unsupported state {state!r}")
            continue
        created = issue_queue.parseUtc(lease.get("createdAtUtc"))
        expires = issue_queue.parseUtc(lease.get("expiresAtUtc"))
        if created is None:
            errors.append(f"{label}: invalid createdAtUtc")
        if expires is None:
            errors.append(f"{label}: invalid expiresAtUtc")
        if created is not None and expires is not None and expires < created:
            errors.append(f"{label}: expiresAtUtc precedes createdAtUtc")
        if not expandedPaths(lease):
            errors.append(f"{label}: empty expanded scope")
        if state == STATE_RELEASED and issue_queue.parseUtc(lease.get("releasedAtUtc")) is None:
            errors.append(f"{label}: RELEASED requires valid releasedAtUtc")
        if state == STATE_RECOVERED:
            if issue_queue.parseUtc(lease.get("recoveredAtUtc")) is None:
                errors.append(f"{label}: RECOVERED requires valid recoveredAtUtc")
            if not str(lease.get("recoveryReason") or "").strip():
                errors.append(f"{label}: RECOVERED requires recoveryReason")
        if state == STATE_ACTIVE:
            if leaseExpired(lease, now):
                warnings.append(
                    f"{label}: ACTIVE lease expired at {lease.get('expiresAtUtc')}; "
                    "recover it with write_leases.py recover (lease-lifecycle-only; XLSX claims are untouched)"
                )
            else:
                active_unexpired.append(lease)
    for first_index, first in enumerate(active_unexpired):
        for second in active_unexpired[first_index + 1 :]:
            overlaps = scopeOverlaps(expandedPaths(first), expandedPaths(second))
            if overlaps:
                errors.append(
                    f"Leases {first.get('leaseId')} and {second.get('leaseId')} have overlapping ACTIVE "
                    f"write scopes: {overlaps[0]['path']} <-> {overlaps[0]['otherPath']}"
                )
    return errors, warnings


def scopeFromArgs(args: argparse.Namespace) -> dict[str, list[str]]:
    return {
        SOURCE_PR_CHANGED_FILES: list(args.pr_changed_file),
        SOURCE_DIRTY_WORKTREE: list(args.dirty_worktree_file),
        SOURCE_WORKER_DECLARED: list(args.declared_file),
        SOURCE_WORKBOOK_TARGET_FILES: list(args.workbook_target_file),
    }


def requestsFromArgs(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.batch_file:
        batch = json.loads(Path(args.batch_file).read_text(encoding="utf-8"))
        if not isinstance(batch, list):
            raise WriteLeaseError("--batch-file must contain a JSON list of lease requests")
        return batch
    if not args.controller_id or not args.owner or not args.claim_id:
        raise WriteLeaseError("acquire requires --controller-id, --owner, and --claim-id (or --batch-file)")
    return [
        buildLeaseRequest(
            controller_id=args.controller_id,
            owner=args.owner,
            claim_id=args.claim_id,
            scope_by_source=scopeFromArgs(args),
            issue_name=args.issue,
            duration_minutes=args.duration_minutes,
        )
    ]


def printJson(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def addCommonArguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--store", default=None, help=f"Lease store path. Default: ${ENV_STORE} or {DEFAULT_STORE}")
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--repo-root", default=None, help="Repository root used for coupled-scope expansion")


def buildParser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    acquire_parser = subparsers.add_parser("acquire", help="Atomically acquire one or more write leases")
    addCommonArguments(acquire_parser)
    acquire_parser.add_argument("--controller-id")
    acquire_parser.add_argument("--owner")
    acquire_parser.add_argument("--claim-id")
    acquire_parser.add_argument("--issue", help="Workbook issue name this lease supports (metadata only)")
    acquire_parser.add_argument("--duration-minutes", type=int, default=DEFAULT_LEASE_MINUTES)
    acquire_parser.add_argument("--pr-changed-file", action="append", default=[], help="Path changed in the PR")
    acquire_parser.add_argument("--dirty-worktree-file", action="append", default=[], help="Dirty worktree path")
    acquire_parser.add_argument("--declared-file", action="append", default=[], help="Worker-declared intended path")
    acquire_parser.add_argument("--workbook-target-file", action="append", default=[], help="Workbook target path")
    acquire_parser.add_argument("--batch-file", help="JSON file with a list of lease requests (all-or-nothing)")

    renew_parser = subparsers.add_parser("renew", help="Atomically renew active leases")
    addCommonArguments(renew_parser)
    renew_parser.add_argument("--lease-id", action="append", default=[], required=True)
    renew_parser.add_argument("--owner", required=True)
    renew_parser.add_argument("--claim-id", required=True)
    renew_parser.add_argument("--extend-minutes", type=int, default=DEFAULT_LEASE_MINUTES)

    release_parser = subparsers.add_parser("release", help="Atomically release active leases")
    addCommonArguments(release_parser)
    release_parser.add_argument("--lease-id", action="append", default=[], required=True)
    release_parser.add_argument("--owner", required=True)
    release_parser.add_argument("--claim-id", required=True)

    recover_parser = subparsers.add_parser("recover", help="Recover expired leases (never touches XLSX claims)")
    addCommonArguments(recover_parser)
    recover_parser.add_argument("--lease-id", action="append", default=[], required=True)
    recover_parser.add_argument("--reason", required=True)

    list_parser = subparsers.add_parser("list", help="List leases (read-only; no lease required)")
    addCommonArguments(list_parser)
    list_parser.add_argument("--state", action="append", default=[])
    list_parser.add_argument("--owner")
    list_parser.add_argument("--claim-id")

    validate_parser = subparsers.add_parser("validate", help="Validate store schema and the ACTIVE-overlap invariant")
    addCommonArguments(validate_parser)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = buildParser()
    args = parser.parse_args(argv)
    store_path = resolveStorePath(args.store)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else None
    try:
        if args.command == "acquire":
            try:
                printJson(
                    acquireLeases(
                        store_path,
                        requestsFromArgs(args),
                        lock_timeout_seconds=args.lock_timeout_seconds,
                        repo_root=repo_root,
                    )
                )
            except WriteLeaseConflict as exc:
                printJson({"store": str(store_path), "acquired": [], "error": str(exc), "conflicts": exc.conflicts})
                return 3
            return 0
        if args.command == "renew":
            printJson(
                renewLeases(
                    store_path,
                    args.lease_id,
                    owner=args.owner,
                    claim_id=args.claim_id,
                    extend_minutes=args.extend_minutes,
                    lock_timeout_seconds=args.lock_timeout_seconds,
                )
            )
            return 0
        if args.command == "release":
            printJson(
                releaseLeases(
                    store_path,
                    args.lease_id,
                    owner=args.owner,
                    claim_id=args.claim_id,
                    lock_timeout_seconds=args.lock_timeout_seconds,
                )
            )
            return 0
        if args.command == "recover":
            printJson(
                recoverLeases(
                    store_path,
                    args.lease_id,
                    reason=args.reason,
                    lock_timeout_seconds=args.lock_timeout_seconds,
                )
            )
            return 0
        if args.command == "list":
            states = {state.strip().upper() for state in args.state} or None
            printJson(listLeases(store_path, states=states, owner=args.owner, claim_id=args.claim_id))
            return 0
        if args.command == "validate":
            errors, warnings = validateStore(loadStore(store_path))
            printJson({"store": str(store_path), "errors": errors, "warnings": warnings})
            return 1 if errors else 0
        raise WriteLeaseError(f"Unsupported command {args.command}")
    except (WriteLeaseError, issue_queue.QueueError, OSError, ValueError) as exc:
        print(f"write_leases: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
