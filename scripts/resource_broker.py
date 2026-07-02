#!/usr/bin/env python3
"""Shared local-resource broker for concurrent queue controllers.

``scripts/controller_resource_audit.py`` observes disk, Git, and worktree state, but scarce
local resources (heavy build/test/coverage jobs, Xvfb displays, TCP ports, build-directory
ownership, memory budgets, MCP server slots) also need coordination between concurrent
controllers. This module keeps observation and reservation strictly separate:

- Probes are portable and read-only. Each probe reports one of ``available``,
    ``unavailable``, ``unknown``, or ``unsupported`` and never raises on unsupported
    platforms; probing mutates nothing.
- Reservations are typed records in a JSON store (default
    ``planning/resource_reservations.json``; override with ``--store`` or the
    ``GAME_RESOURCE_RESERVATION_FILE`` environment variable) following the same
    sidecar-lock + temp-file + ``os.replace`` batch idioms as ``scripts/write_leases.py``.
    A record carries resource type, normalized key, controller ID, owner, claim ID,
    purpose, created/renewed/expires timestamps, and lifecycle state
    (``ACTIVE``/``RELEASED``/``RECOVERED``).
- ``reserve``/``renew``/``release``/``recover`` are all-or-nothing batches under one
    cross-process lock; a failed batch leaves the store byte-for-byte unchanged.
- Exclusive resources (same type and key) are hard conflicts; independent resources stay
    concurrent. ``memory`` reservations are advisory (shared) unless a verified exclusive
    budget is explicitly requested with ``--exclusive``.
- Expired reservations never block acquisition and are reported, not purged. ``recover``
    marks expired ``ACTIVE`` records as ``RECOVERED`` only; it never deletes records,
    never kills processes, and never removes worktrees.

CLI: ``probe``, ``reserve``, ``renew``, ``release``, ``recover``, ``list`` (also exposed
as subcommands of ``scripts/controller_resource_audit.py``).
Exit codes: 0 success, 2 usage/store errors, 3 reservation conflict.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable, Sequence

try:
    from scripts import issue_queue
except ModuleNotFoundError:  # Support `python3 scripts/resource_broker.py`.
    import issue_queue

DEFAULT_STORE = Path("planning/resource_reservations.json")
ENV_STORE = "GAME_RESOURCE_RESERVATION_FILE"
STORE_VERSION = 1

STATE_ACTIVE = "ACTIVE"
STATE_RELEASED = "RELEASED"
STATE_RECOVERED = "RECOVERED"
ALLOWED_STATES = (STATE_ACTIVE, STATE_RELEASED, STATE_RECOVERED)

STATUS_AVAILABLE = "available"
STATUS_UNAVAILABLE = "unavailable"
STATUS_UNKNOWN = "unknown"
STATUS_UNSUPPORTED = "unsupported"

RESOURCE_MEMORY = "memory"
RESOURCE_HEAVY_JOB = "heavy-job"
RESOURCE_XVFB_DISPLAY = "xvfb-display"
RESOURCE_TCP_PORT = "tcp-port"
RESOURCE_BUILD_DIR = "build-dir"
RESOURCE_MCP_SERVER = "mcp-server"
# Resource type -> whether a reservation on the same key is exclusive by default.
# Memory is advisory (shared) unless a verified exclusive budget is explicitly requested.
RESOURCE_TYPES = {
    RESOURCE_MEMORY: False,
    RESOURCE_HEAVY_JOB: True,
    RESOURCE_XVFB_DISPLAY: True,
    RESOURCE_TCP_PORT: True,
    RESOURCE_BUILD_DIR: True,
    RESOURCE_MCP_SERVER: True,
}

DEFAULT_RESERVATION_MINUTES = 120
DEFAULT_MIN_AVAILABLE_MEMORY_MIB = 2048.0
DEFAULT_PROBE_TCP_PORTS = (8765,)  # mcp.py default HTTP port.
DEFAULT_BUILD_DIRS = ("cmake-build-release", "cmake-build-debug")

# Command-line substrings that identify running heavy build/test/coverage jobs.
HEAVY_JOB_PATTERNS = (
    "cmake --build",
    "ctest",
    "run_coverage.sh",
    "gcovr",
    "cc1plus",
    "ninja",
    "make -j",
    "xvfb-run",
    "Xvfb",
    " test.py",
)


class ResourceBrokerError(RuntimeError):
    """Raised for invalid resource-broker operations."""


class ResourceConflict(ResourceBrokerError):
    """Raised when a reservation batch would conflict with an ACTIVE, unexpired reservation."""

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


def normalizeReservationKey(resource: str, raw_key: Any) -> str:
    text = str(raw_key or "").strip()
    if not text:
        raise ResourceBrokerError(f"Reservation key for {resource!r} must be non-empty")
    if resource == RESOURCE_TCP_PORT:
        try:
            port = int(text)
        except ValueError as exc:
            raise ResourceBrokerError(f"tcp-port key must be an integer, got {raw_key!r}") from exc
        if not 1 <= port <= 65535:
            raise ResourceBrokerError(f"tcp-port key must be in 1..65535, got {port}")
        return str(port)
    if resource == RESOURCE_XVFB_DISPLAY:
        digits = text.lstrip(":")
        if not digits.isdigit():
            raise ResourceBrokerError(f"xvfb-display key must look like :99, got {raw_key!r}")
        return f":{int(digits)}"
    if resource == RESOURCE_BUILD_DIR:
        return text.replace("\\", "/").rstrip("/")
    return text


def probePayload(resource: str, status: str, detail: str, key: str | None = None, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"resource": resource, "key": key, "status": status, "detail": detail}
    payload.update(extra)
    return payload


def guardedProbe(resource: str, probe: Callable[[], dict[str, Any]], key: str | None = None) -> dict[str, Any]:
    """Run one probe; a probe must never propagate an exception, only report a status."""

    try:
        return probe()
    except Exception as exc:  # noqa: BLE001 - probes are defensive by contract.
        return probePayload(resource, STATUS_UNKNOWN, f"probe raised {type(exc).__name__}: {exc}", key=key)


def probeMemory(
    min_available_mib: float = DEFAULT_MIN_AVAILABLE_MEMORY_MIB,
    meminfo_path: Path = Path("/proc/meminfo"),
) -> dict[str, Any]:
    """Advisory memory-pressure probe from /proc/meminfo; unsupported where it does not exist."""

    if not meminfo_path.is_file():
        return probePayload(
            RESOURCE_MEMORY, STATUS_UNSUPPORTED, f"{meminfo_path} is not available on this platform", advisory=True
        )
    fields: dict[str, int] = {}
    for line in meminfo_path.read_text(encoding="utf-8", errors="replace").splitlines():
        name, _, value = line.partition(":")
        parts = value.split()
        if parts and parts[0].isdigit():
            fields[name.strip()] = int(parts[0])
    total_kib = fields.get("MemTotal")
    available_kib = fields.get("MemAvailable")
    if total_kib is None or available_kib is None:
        return probePayload(
            RESOURCE_MEMORY, STATUS_UNKNOWN, f"{meminfo_path} lacks MemTotal/MemAvailable", advisory=True
        )
    available_mib = available_kib / 1024.0
    status = STATUS_AVAILABLE if available_mib >= min_available_mib else STATUS_UNAVAILABLE
    return probePayload(
        RESOURCE_MEMORY,
        status,
        f"{available_mib:.0f} MiB available of {total_kib / 1024.0:.0f} MiB "
        f"(advisory floor {min_available_mib:.0f} MiB)",
        advisory=True,
        availableMib=round(available_mib, 1),
        totalMib=round(total_kib / 1024.0, 1),
        minAvailableMib=min_available_mib,
    )


def probeHeavyJobs(
    proc_root: Path = Path("/proc"),
    patterns: Sequence[str] = HEAVY_JOB_PATTERNS,
) -> dict[str, Any]:
    """Detect running build/test/coverage processes read-only; unsupported without /proc."""

    if not proc_root.is_dir():
        return probePayload(RESOURCE_HEAVY_JOB, STATUS_UNSUPPORTED, f"{proc_root} is not available on this platform")
    matches: list[dict[str, Any]] = []
    self_pid = os.getpid()
    for entry in proc_root.iterdir():
        if not entry.name.isdigit() or int(entry.name) == self_pid:
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").strip()
        except OSError:
            continue
        if command and any(pattern in command for pattern in patterns):
            matches.append({"pid": int(entry.name), "command": command[:200]})
    matches.sort(key=lambda item: item["pid"])
    status = STATUS_UNAVAILABLE if matches else STATUS_AVAILABLE
    return probePayload(
        RESOURCE_HEAVY_JOB,
        status,
        f"{len(matches)} running heavy build/test/coverage process(es)",
        runningJobs=matches,
    )


def probeXvfbDisplays(
    display: str | None = None,
    x11_socket_dir: Path = Path("/tmp/.X11-unix"),
    lock_dir: Path = Path("/tmp"),
) -> dict[str, Any]:
    """Report X displays in use from sockets and lock files; unsupported off POSIX."""

    key = normalizeReservationKey(RESOURCE_XVFB_DISPLAY, display) if display is not None else None
    if os.name != "posix":
        return probePayload(RESOURCE_XVFB_DISPLAY, STATUS_UNSUPPORTED, "X display probing requires POSIX", key=key)
    used: set[int] = set()
    if x11_socket_dir.is_dir():
        for entry in x11_socket_dir.iterdir():
            if entry.name.startswith("X") and entry.name[1:].isdigit():
                used.add(int(entry.name[1:]))
    if lock_dir.is_dir():
        for entry in lock_dir.glob(".X*-lock"):
            digits = entry.name[len(".X") : -len("-lock")]
            if digits.isdigit():
                used.add(int(digits))
    used_displays = [f":{number}" for number in sorted(used)]
    if key is not None:
        status = STATUS_UNAVAILABLE if key in used_displays else STATUS_AVAILABLE
        return probePayload(
            RESOURCE_XVFB_DISPLAY,
            status,
            f"display {key} usage from sockets/locks",
            key=key,
            usedDisplays=used_displays,
        )
    return probePayload(
        RESOURCE_XVFB_DISPLAY, STATUS_AVAILABLE, f"{len(used_displays)} display(s) in use", usedDisplays=used_displays
    )


def probeTcpPort(port: int | str, host: str = "127.0.0.1") -> dict[str, Any]:
    """Report whether a TCP port can currently be bound; read-only beyond a transient bind."""

    key = normalizeReservationKey(RESOURCE_TCP_PORT, port)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe_socket:
            probe_socket.bind((host, int(key)))
    except OSError as exc:
        return probePayload(RESOURCE_TCP_PORT, STATUS_UNAVAILABLE, f"cannot bind {host}:{key}: {exc}", key=key)
    return probePayload(RESOURCE_TCP_PORT, STATUS_AVAILABLE, f"{host}:{key} is bindable", key=key)


def probeBuildDirOwnership(
    repo_root: Path,
    build_dirs: Sequence[str] = DEFAULT_BUILD_DIRS,
    active_reservations: Sequence[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Report build-directory existence plus reservation ownership; never touches the directories."""

    probes: list[dict[str, Any]] = []
    for build_dir in build_dirs:
        key = normalizeReservationKey(RESOURCE_BUILD_DIR, build_dir)
        holders = [
            reservation
            for reservation in active_reservations
            if reservation.get("resource") == RESOURCE_BUILD_DIR and reservation.get("key") == key
        ]
        exists = (repo_root / key).is_dir()
        if holders:
            owner = holders[0].get("owner")
            probes.append(
                probePayload(
                    RESOURCE_BUILD_DIR,
                    STATUS_UNAVAILABLE,
                    f"{key} is reserved by {owner}",
                    key=key,
                    exists=exists,
                    reservedBy=[holder.get("owner") for holder in holders],
                )
            )
        else:
            probes.append(
                probePayload(
                    RESOURCE_BUILD_DIR, STATUS_AVAILABLE, f"{key} has no active reservation", key=key, exists=exists
                )
            )
    return probes


def probeMcpServer(
    active_reservations: Sequence[dict[str, Any]] = (),
    port: int = DEFAULT_PROBE_TCP_PORTS[0],
    host: str = "127.0.0.1",
) -> dict[str, Any]:
    """Report MCP server slot state from reservations plus the default port binding."""

    key = f"{host}:{port}"
    holders = [reservation for reservation in active_reservations if reservation.get("resource") == RESOURCE_MCP_SERVER]
    if holders:
        return probePayload(
            RESOURCE_MCP_SERVER,
            STATUS_UNAVAILABLE,
            f"MCP server slot reserved by {holders[0].get('owner')}",
            key=key,
            reservedBy=[holder.get("owner") for holder in holders],
        )
    port_probe = probeTcpPort(port, host=host)
    if port_probe["status"] == STATUS_UNAVAILABLE:
        return probePayload(
            RESOURCE_MCP_SERVER, STATUS_UNAVAILABLE, f"default MCP port {key} is already bound", key=key
        )
    if port_probe["status"] != STATUS_AVAILABLE:
        return probePayload(RESOURCE_MCP_SERVER, port_probe["status"], port_probe["detail"], key=key)
    return probePayload(
        RESOURCE_MCP_SERVER, STATUS_AVAILABLE, f"no reservation and default MCP port {key} is bindable", key=key
    )


def emptyStore() -> dict[str, Any]:
    return {"version": STORE_VERSION, "updatedAtUtc": None, "reservations": []}


def loadStore(store_path: Path) -> dict[str, Any]:
    if not store_path.is_file():
        return emptyStore()
    try:
        store = json.loads(store_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResourceBrokerError(f"Cannot read reservation store {store_path}: {exc}") from exc
    if not isinstance(store, dict) or not isinstance(store.get("reservations"), list):
        raise ResourceBrokerError(f"Reservation store {store_path} is malformed: expected a reservations list")
    if store.get("version") != STORE_VERSION:
        raise ResourceBrokerError(f"Unsupported reservation store version {store.get('version')!r} in {store_path}")
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
    """One cross-process sidecar lock per store, mirroring the write-lease/workbook lock."""

    return issue_queue.WorkbookLock(store_path, lock_timeout_seconds)


def reservationExpired(reservation: dict[str, Any], now: Any) -> bool:
    expires = issue_queue.parseUtc(reservation.get("expiresAtUtc"))
    return expires is None or expires <= now


def reservationPayload(reservation: dict[str, Any], now: Any) -> dict[str, Any]:
    payload = dict(reservation)
    payload["expired"] = reservation.get("state") == STATE_ACTIVE and reservationExpired(reservation, now)
    return payload


def activeReservations(store: dict[str, Any], now: Any) -> list[dict[str, Any]]:
    return [
        reservation
        for reservation in store["reservations"]
        if reservation.get("state") == STATE_ACTIVE and not reservationExpired(reservation, now)
    ]


def expiredActiveReservations(store: dict[str, Any], now: Any) -> list[dict[str, Any]]:
    return [
        reservation
        for reservation in store["reservations"]
        if reservation.get("state") == STATE_ACTIVE and reservationExpired(reservation, now)
    ]


def findReservation(store: dict[str, Any], reservation_id: str) -> dict[str, Any]:
    for reservation in store["reservations"]:
        if reservation.get("reservationId") == reservation_id:
            return reservation
    raise ResourceBrokerError(f"Unknown reservation id: {reservation_id}")


def checkReservationIdentity(reservation: dict[str, Any], owner: str) -> None:
    if reservation.get("owner") != owner:
        raise ResourceBrokerError(
            f"Reservation {reservation.get('reservationId')} is owned by {reservation.get('owner')!r}, not {owner!r}"
        )


def buildReservationRequest(
    resource: str,
    key: str,
    controller_id: str,
    owner: str,
    claim_id: str | None = None,
    purpose: str | None = None,
    duration_minutes: int = DEFAULT_RESERVATION_MINUTES,
    exclusive: bool | None = None,
) -> dict[str, Any]:
    return {
        "resource": resource,
        "key": key,
        "controllerId": controller_id,
        "owner": owner,
        "claimId": claim_id,
        "purpose": purpose,
        "durationMinutes": duration_minutes,
        "exclusive": exclusive,
    }


def prepareReservation(request: dict[str, Any], now: Any) -> dict[str, Any]:
    resource = str(request.get("resource") or "").strip().lower()
    if resource not in RESOURCE_TYPES:
        raise ResourceBrokerError(f"Unknown resource type {resource!r}; expected one of {sorted(RESOURCE_TYPES)}")
    key = normalizeReservationKey(resource, request.get("key"))
    controller_id = str(request.get("controllerId") or "").strip()
    owner = str(request.get("owner") or "").strip()
    if not controller_id or not owner:
        raise ResourceBrokerError("Reservation requests require controllerId and owner")
    duration_minutes = int(request.get("durationMinutes") or DEFAULT_RESERVATION_MINUTES)
    if duration_minutes < 1:
        raise ResourceBrokerError("durationMinutes must be positive")
    exclusive = request.get("exclusive")
    if exclusive is None:
        exclusive = RESOURCE_TYPES[resource]
    created = issue_queue.formatUtc(now)
    return {
        "reservationId": uuid.uuid4().hex,
        "resource": resource,
        "key": key,
        "exclusive": bool(exclusive),
        "controllerId": controller_id,
        "owner": owner,
        "claimId": request.get("claimId"),
        "purpose": request.get("purpose"),
        "state": STATE_ACTIVE,
        "createdAtUtc": created,
        "renewedAtUtc": created,
        "expiresAtUtc": issue_queue.formatUtc(now + timedelta(minutes=duration_minutes)),
        "releasedAtUtc": None,
        "recoveredAtUtc": None,
        "recoveryReason": None,
    }


def conflictBetween(candidate: dict[str, Any], existing: dict[str, Any]) -> bool:
    if candidate["resource"] != existing.get("resource") or candidate["key"] != existing.get("key"):
        return False
    return bool(candidate.get("exclusive")) or bool(existing.get("exclusive"))


def blockingConflicts(candidate: dict[str, Any], holders: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for holder in holders:
        if conflictBetween(candidate, holder):
            conflicts.append(
                {
                    "reservationId": holder.get("reservationId"),
                    "resource": holder.get("resource"),
                    "key": holder.get("key"),
                    "owner": holder.get("owner"),
                    "claimId": holder.get("claimId"),
                    "expiresAtUtc": holder.get("expiresAtUtc"),
                }
            )
    return conflicts


def acquireReservations(
    store_path: Path,
    requests: Sequence[dict[str, Any]],
    now: Any = None,
    lock_timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Atomically acquire every requested reservation or none of them.

    Expired ACTIVE reservations never block acquisition; they are reported in the result
    so a controller can run explicit, non-destructive recovery.
    """

    if not requests:
        raise ResourceBrokerError("reserve requires at least one reservation request")
    now = now or issue_queue.utcNow()
    with storeLock(store_path, lock_timeout_seconds):
        store = loadStore(store_path)
        holders = activeReservations(store, now)
        expired = expiredActiveReservations(store, now)
        prepared: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        for request in requests:
            reservation = prepareReservation(request, now)
            blocked_by = blockingConflicts(reservation, holders)
            for accepted in prepared:
                if conflictBetween(reservation, accepted):
                    blocked_by.append(
                        {
                            "reservationId": accepted["reservationId"],
                            "resource": accepted["resource"],
                            "key": accepted["key"],
                            "owner": accepted["owner"],
                            "claimId": accepted.get("claimId"),
                            "withinBatch": True,
                        }
                    )
            if blocked_by:
                conflicts.append(
                    {
                        "request": {key: reservation[key] for key in ("resource", "key", "owner", "claimId")},
                        "blockedBy": blocked_by,
                    }
                )
            prepared.append(reservation)
        if conflicts:
            raise ResourceConflict("Resource conflict: reservation batch rolled back; store unchanged", conflicts)
        store["reservations"].extend(prepared)
        saveStore(store, store_path, now)
    return {
        "store": str(store_path),
        "acquired": [reservationPayload(reservation, now) for reservation in prepared],
        "expiredActive": [reservationPayload(reservation, now) for reservation in expired],
    }


def renewReservations(
    store_path: Path,
    reservation_ids: Sequence[str],
    owner: str,
    extend_minutes: int = DEFAULT_RESERVATION_MINUTES,
    now: Any = None,
    lock_timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Atomically renew every reservation in the batch or none of them."""

    if not reservation_ids:
        raise ResourceBrokerError("renew requires at least one --reservation-id")
    if extend_minutes < 1:
        raise ResourceBrokerError("--extend-minutes must be positive")
    now = now or issue_queue.utcNow()
    with storeLock(store_path, lock_timeout_seconds):
        store = loadStore(store_path)
        reservations = []
        for reservation_id in reservation_ids:
            reservation = findReservation(store, reservation_id)
            checkReservationIdentity(reservation, owner)
            if reservation.get("state") != STATE_ACTIVE:
                raise ResourceBrokerError(f"Reservation {reservation_id} is {reservation.get('state')}, not ACTIVE")
            if reservationExpired(reservation, now):
                raise ResourceBrokerError(
                    f"Reservation {reservation_id} expired at {reservation.get('expiresAtUtc')}; re-acquire it"
                )
            reservations.append(reservation)
        for reservation in reservations:
            reservation["renewedAtUtc"] = issue_queue.formatUtc(now)
            reservation["expiresAtUtc"] = issue_queue.formatUtc(now + timedelta(minutes=extend_minutes))
        saveStore(store, store_path, now)
        return {
            "store": str(store_path),
            "renewed": [reservationPayload(reservation, now) for reservation in reservations],
        }


def releaseReservations(
    store_path: Path,
    reservation_ids: Sequence[str],
    owner: str,
    now: Any = None,
    lock_timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Atomically release every reservation in the batch or none of them."""

    if not reservation_ids:
        raise ResourceBrokerError("release requires at least one --reservation-id")
    now = now or issue_queue.utcNow()
    with storeLock(store_path, lock_timeout_seconds):
        store = loadStore(store_path)
        reservations = []
        for reservation_id in reservation_ids:
            reservation = findReservation(store, reservation_id)
            checkReservationIdentity(reservation, owner)
            if reservation.get("state") != STATE_ACTIVE:
                raise ResourceBrokerError(f"Reservation {reservation_id} is {reservation.get('state')}, not ACTIVE")
            reservations.append(reservation)
        for reservation in reservations:
            reservation["state"] = STATE_RELEASED
            reservation["releasedAtUtc"] = issue_queue.formatUtc(now)
        saveStore(store, store_path, now)
        return {
            "store": str(store_path),
            "released": [reservationPayload(reservation, now) for reservation in reservations],
        }


def recoverReservations(
    store_path: Path,
    reservation_ids: Sequence[str],
    reason: str,
    now: Any = None,
    lock_timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Recover expired ACTIVE reservations by marking them RECOVERED.

    Recovery is record-lifecycle-only: it never deletes records, never kills processes,
    and never removes worktrees or directories.
    """

    if not reservation_ids:
        raise ResourceBrokerError("recover requires at least one --reservation-id")
    reason = reason.strip()
    if not reason:
        raise ResourceBrokerError("recover requires a non-empty --reason")
    now = now or issue_queue.utcNow()
    with storeLock(store_path, lock_timeout_seconds):
        store = loadStore(store_path)
        reservations = []
        for reservation_id in reservation_ids:
            reservation = findReservation(store, reservation_id)
            if reservation.get("state") != STATE_ACTIVE:
                raise ResourceBrokerError(f"Reservation {reservation_id} is {reservation.get('state')}, not ACTIVE")
            if not reservationExpired(reservation, now):
                raise ResourceBrokerError(
                    f"Reservation {reservation_id} is still valid until {reservation.get('expiresAtUtc')}; "
                    "only expired reservations can be recovered"
                )
            reservations.append(reservation)
        for reservation in reservations:
            reservation["state"] = STATE_RECOVERED
            reservation["recoveredAtUtc"] = issue_queue.formatUtc(now)
            reservation["recoveryReason"] = reason
        saveStore(store, store_path, now)
        return {
            "store": str(store_path),
            "recovered": [reservationPayload(reservation, now) for reservation in reservations],
        }


def listReservations(
    store_path: Path,
    states: set[str] | None = None,
    resource: str | None = None,
    owner: str | None = None,
    now: Any = None,
) -> dict[str, Any]:
    """Read-only inspection of the store; never requires or takes a reservation."""

    now = now or issue_queue.utcNow()
    store = loadStore(store_path)
    reservations = []
    for reservation in store["reservations"]:
        if states and reservation.get("state") not in states:
            continue
        if resource and reservation.get("resource") != resource:
            continue
        if owner and reservation.get("owner") != owner:
            continue
        reservations.append(reservationPayload(reservation, now))
    return {"store": str(store_path), "count": len(reservations), "reservations": reservations}


def reservationSummary(store_path: Path, now: Any) -> dict[str, Any]:
    try:
        store = loadStore(store_path)
    except ResourceBrokerError as exc:
        return {"store": str(store_path), "error": str(exc), "total": None, "active": None, "expiredActive": None}
    expired = expiredActiveReservations(store, now)
    return {
        "store": str(store_path),
        "total": len(store["reservations"]),
        "active": len(activeReservations(store, now)),
        "expiredActive": len(expired),
        "expiredRecords": [reservationPayload(reservation, now) for reservation in expired],
    }


def observeResources(
    repo_root: Path,
    store_path: str | Path | None = None,
    now: Any = None,
    tcp_ports: Sequence[int | str] = DEFAULT_PROBE_TCP_PORTS,
    displays: Sequence[str] = (),
    build_dirs: Sequence[str] = DEFAULT_BUILD_DIRS,
    min_available_memory_mib: float = DEFAULT_MIN_AVAILABLE_MEMORY_MIB,
) -> dict[str, Any]:
    """Run every read-only probe plus a reservation-store summary; never raises."""

    now = now or issue_queue.utcNow()
    if store_path is None and not os.environ.get(ENV_STORE):
        resolved_store = (repo_root / DEFAULT_STORE).resolve()
    else:
        resolved_store = resolveStorePath(store_path)
    reservations = reservationSummary(resolved_store, now)
    holders: list[dict[str, Any]] = []
    if not reservations.get("error"):
        try:
            holders = activeReservations(loadStore(resolved_store), now)
        except ResourceBrokerError:
            holders = []
    probes: list[dict[str, Any]] = [
        guardedProbe(RESOURCE_MEMORY, lambda: probeMemory(min_available_mib=min_available_memory_mib)),
        guardedProbe(RESOURCE_HEAVY_JOB, probeHeavyJobs),
    ]
    if displays:
        for display in displays:
            probes.append(
                guardedProbe(RESOURCE_XVFB_DISPLAY, lambda display=display: probeXvfbDisplays(display=display))
            )
    else:
        probes.append(guardedProbe(RESOURCE_XVFB_DISPLAY, probeXvfbDisplays))
    for port in tcp_ports:
        probes.append(guardedProbe(RESOURCE_TCP_PORT, lambda port=port: probeTcpPort(port), key=str(port)))
    try:
        probes.extend(probeBuildDirOwnership(repo_root, build_dirs, holders))
    except Exception as exc:  # noqa: BLE001 - observation must never raise.
        probes.append(probePayload(RESOURCE_BUILD_DIR, STATUS_UNKNOWN, f"probe raised {exc}"))
    probes.append(guardedProbe(RESOURCE_MCP_SERVER, lambda: probeMcpServer(holders)))
    return {"probes": probes, "reservations": reservations}


def printJson(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def parseResourceSpec(spec: str) -> tuple[str, str]:
    resource, separator, key = spec.partition("=")
    if not separator or not resource.strip() or not key.strip():
        raise ResourceBrokerError(f"--resource must look like type=key (for example tcp-port=8765), got {spec!r}")
    return resource.strip().lower(), key.strip()


def requestsFromArgs(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.batch_file:
        batch = json.loads(Path(args.batch_file).read_text(encoding="utf-8"))
        if not isinstance(batch, list):
            raise ResourceBrokerError("--batch-file must contain a JSON list of reservation requests")
        return batch
    if not args.resource:
        raise ResourceBrokerError("reserve requires at least one --resource type=key (or --batch-file)")
    if not args.controller_id or not args.owner:
        raise ResourceBrokerError("reserve requires --controller-id and --owner (or --batch-file)")
    requests = []
    for spec in args.resource:
        resource, key = parseResourceSpec(spec)
        requests.append(
            buildReservationRequest(
                resource=resource,
                key=key,
                controller_id=args.controller_id,
                owner=args.owner,
                claim_id=args.claim_id,
                purpose=args.purpose,
                duration_minutes=args.duration_minutes,
                exclusive=True if args.exclusive else None,
            )
        )
    return requests


def addCommonArguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--store", default=None, help=f"Reservation store path. Default: ${ENV_STORE} or {DEFAULT_STORE}"
    )
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)


def buildParser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    probe_parser = subparsers.add_parser("probe", help="Read-only probes for scarce local resources")
    addCommonArguments(probe_parser)
    probe_parser.add_argument("--repo-root", default=".", help="Repository root used for build-directory probes")
    probe_parser.add_argument("--tcp-port", action="append", default=[], help="TCP port to probe. May be repeated.")
    probe_parser.add_argument("--xvfb-display", action="append", default=[], help="X display (:99) to probe.")
    probe_parser.add_argument("--build-dir", action="append", default=[], help="Build directory name to probe.")
    probe_parser.add_argument("--min-available-memory-mib", type=float, default=DEFAULT_MIN_AVAILABLE_MEMORY_MIB)

    reserve_parser = subparsers.add_parser("reserve", help="Atomically acquire typed resource reservations")
    addCommonArguments(reserve_parser)
    reserve_parser.add_argument("--controller-id")
    reserve_parser.add_argument("--owner")
    reserve_parser.add_argument("--claim-id")
    reserve_parser.add_argument("--purpose", help="Human-readable purpose (metadata only)")
    reserve_parser.add_argument("--duration-minutes", type=int, default=DEFAULT_RESERVATION_MINUTES)
    reserve_parser.add_argument(
        "--resource",
        action="append",
        default=[],
        help="Resource to reserve as type=key (for example tcp-port=8765 or xvfb-display=:99). May be repeated.",
    )
    reserve_parser.add_argument(
        "--exclusive",
        action="store_true",
        help="Force exclusive semantics even for shared/advisory types such as memory budgets.",
    )
    reserve_parser.add_argument("--batch-file", help="JSON file with a list of reservation requests (all-or-nothing)")

    renew_parser = subparsers.add_parser("renew", help="Atomically renew active reservations")
    addCommonArguments(renew_parser)
    renew_parser.add_argument("--reservation-id", action="append", default=[], required=True)
    renew_parser.add_argument("--owner", required=True)
    renew_parser.add_argument("--extend-minutes", type=int, default=DEFAULT_RESERVATION_MINUTES)

    release_parser = subparsers.add_parser("release", help="Atomically release active reservations")
    addCommonArguments(release_parser)
    release_parser.add_argument("--reservation-id", action="append", default=[], required=True)
    release_parser.add_argument("--owner", required=True)

    recover_parser = subparsers.add_parser(
        "recover", help="Mark expired reservations RECOVERED (never deletes records or kills processes)"
    )
    addCommonArguments(recover_parser)
    recover_parser.add_argument("--reservation-id", action="append", default=[], required=True)
    recover_parser.add_argument("--reason", required=True)

    list_parser = subparsers.add_parser("list", help="List reservations (read-only; no reservation required)")
    addCommonArguments(list_parser)
    list_parser.add_argument("--state", action="append", default=[])
    list_parser.add_argument("--resource")
    list_parser.add_argument("--owner")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = buildParser()
    args = parser.parse_args(argv)
    store_path = resolveStorePath(args.store)
    try:
        if args.command == "probe":
            printJson(
                observeResources(
                    Path(args.repo_root).resolve(),
                    store_path=args.store,
                    tcp_ports=tuple(args.tcp_port) or DEFAULT_PROBE_TCP_PORTS,
                    displays=tuple(args.xvfb_display),
                    build_dirs=tuple(args.build_dir) or DEFAULT_BUILD_DIRS,
                    min_available_memory_mib=args.min_available_memory_mib,
                )
            )
            return 0
        if args.command == "reserve":
            try:
                printJson(
                    acquireReservations(
                        store_path,
                        requestsFromArgs(args),
                        lock_timeout_seconds=args.lock_timeout_seconds,
                    )
                )
            except ResourceConflict as exc:
                printJson({"store": str(store_path), "acquired": [], "error": str(exc), "conflicts": exc.conflicts})
                return 3
            return 0
        if args.command == "renew":
            printJson(
                renewReservations(
                    store_path,
                    args.reservation_id,
                    owner=args.owner,
                    extend_minutes=args.extend_minutes,
                    lock_timeout_seconds=args.lock_timeout_seconds,
                )
            )
            return 0
        if args.command == "release":
            printJson(
                releaseReservations(
                    store_path,
                    args.reservation_id,
                    owner=args.owner,
                    lock_timeout_seconds=args.lock_timeout_seconds,
                )
            )
            return 0
        if args.command == "recover":
            printJson(
                recoverReservations(
                    store_path,
                    args.reservation_id,
                    reason=args.reason,
                    lock_timeout_seconds=args.lock_timeout_seconds,
                )
            )
            return 0
        if args.command == "list":
            states = {state.strip().upper() for state in args.state} or None
            printJson(listReservations(store_path, states=states, resource=args.resource, owner=args.owner))
            return 0
        raise ResourceBrokerError(f"Unsupported command {args.command}")
    except (ResourceBrokerError, issue_queue.QueueError, OSError, ValueError) as exc:
        print(f"resource_broker: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
