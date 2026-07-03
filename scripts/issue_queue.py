#!/usr/bin/env python3
"""Atomic local task queue backed by the committed issue-proposal XLSX workbook.

The workbook is the canonical queue. Every mutating command acquires a separate
cross-process lock file, loads the workbook, validates the requested claim, and
replaces the workbook atomically after a successful save.

This tool intentionally does not perform git, branch, commit, push, or pull
request operations. It is suitable for one or more controller Codex agents
coordinating local subagents, provided each controller uses a unique owner
prefix for its workers.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import posixpath
import contextlib
import json
import os
import re
import socket
import sys
import tempfile
import time
import uuid
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from scripts import controller_policy
except ModuleNotFoundError:  # Support `python3 scripts/issue_queue.py`.
    import controller_policy

DEFAULT_WORKBOOK = Path("planning/fall_of_nouraajd_issue_proposals.xlsx")
ISSUE_SHEET = "Issue Proposals"

STATUS_NOT_STARTED = "NOT_STARTED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_BLOCKED = "BLOCKED"
STATUS_DONE = "DONE"
STATUS_FAILED = "FAILED"
STATUS_CANCELLED = "CANCELLED"
ALLOWED_STATUSES = {
    STATUS_NOT_STARTED,
    STATUS_IN_PROGRESS,
    STATUS_BLOCKED,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_CANCELLED,
}
LEGACY_STATUS_MAP = {
    "": STATUS_NOT_STARTED,
    "NOT STARTED": STATUS_NOT_STARTED,
    "NOT_STARTED": STATUS_NOT_STARTED,
    "IN PROGRESS": STATUS_IN_PROGRESS,
    "IN_PROGRESS": STATUS_IN_PROGRESS,
    "BLOCKED": STATUS_BLOCKED,
    "DONE": STATUS_DONE,
    "FAILED": STATUS_FAILED,
    "CANCELLED": STATUS_CANCELLED,
    "CANCELED": STATUS_CANCELLED,
}

REQUIRED_HEADERS = (
    "Issue Name",
    "Epic #",
    "Epic Title",
    "Story #",
    "Story Title",
    "Substory #",
    "Substory Title",
    "Priority",
    "Issue Type",
    "Component",
    "Dependencies",
    "Target Files / Modules",
    "Technical Code-Level Description",
    "Acceptance Criteria",
    "Validation / Tests",
    "Source URLs",
    "Status",
    "Owner",
    "Sprint",
)
WORKFLOW_HEADERS = (
    "Claim ID",
    "Claimed At UTC",
    "Updated At UTC",
    "Lease Until UTC",
    "Completed At UTC",
    "Progress %",
    "Last Note",
    "Result Summary",
    "Validation Results",
    "Attempt",
)
ALL_HEADERS = REQUIRED_HEADERS + WORKFLOW_HEADERS
ISSUE_NAME_PATTERN = re.compile(r"^\[EPIC_\d{2}\]\[STORY_\d{2}\]\[SUBSTORY_\d{2}\].+")
ISSUE_NAME_TOKENS = re.compile(r"^\[(EPIC_\d{2})\]\[(STORY_\d{2})\]\[(SUBSTORY_\d{2})\](.+)$")
# Priority ordering derives from the canonical priority enum in controller_policy.
VALID_PRIORITIES = controller_policy.QUEUE_PRIORITIES
PRIORITY_ORDER = {priority: index for index, priority in enumerate(VALID_PRIORITIES)}
# Shared CI merge-gate and controller-governance files. A row whose declared
# target files modify these rewrites the validation authority that gates every
# concurrent PR, so no single autonomous controller can safely validate the
# fleet-wide blast radius mid-run. Surfaced as advisory shortlist metadata (not
# an automatic eligibility filter) so a controller/PM can route such rows to a
# supervised lane instead of auto-claiming them.
CONTROL_PLANE_PATHS = (
    ".github/workflows/build.yml",
    "AGENTS.md",
    "scripts/ci_change_classifier.py",
    "scripts/poll_pr_checks.py",
)
# Mechanical policy values derive from the single canonical source
# (scripts/controller_policy.py); do not restate the numbers here.
DEFAULT_RECLAIM_AGE_MINUTES = controller_policy.value("reclaim_age_minutes")
DEFAULT_HEARTBEAT_INTERVAL_MINUTES = controller_policy.heartbeat_interval_minutes()
DEFAULT_CONTROLLER_ACTIVE_ISSUE_FLOOR = controller_policy.value("controller_active_issue_floor")
DEFAULT_CONTROLLER_ACTIVE_ISSUE_LIMIT = controller_policy.value("controller_active_issue_limit")
DEFAULT_LEASE_MINUTES = controller_policy.value("default_lease_minutes")
DEFAULT_FLEET_ACTIVE_WORKER_FLOOR = controller_policy.value("fleet_active_worker_floor")
TARGET_FILE_OVERLAP_POLICY = controller_policy.value("target_file_overlap_policy")


class QueueError(RuntimeError):
    """Raised for invalid queue operations."""


@dataclass(frozen=True)
class TaskRecord:
    row: int
    values: dict[str, Any]

    @property
    def issueName(self) -> str:
        return str(self.values.get("Issue Name") or "")

    @property
    def status(self) -> str:
        return normalizeStatus(self.values.get("Status"))

    @property
    def priority(self) -> str:
        return str(self.values.get("Priority") or "").strip().upper()

    @property
    def dependencies(self) -> list[str]:
        return parseDependencies(self.values.get("Dependencies"))

    @property
    def targetFiles(self) -> set[str]:
        return parseTargetFiles(self.values.get("Target Files / Modules"))


@dataclass(frozen=True)
class ClaimTimingHealth:
    lastHeartbeatAtUtc: datetime | None
    heartbeatAgeMinutes: int | None
    heartbeatDueAtUtc: datetime | None
    heartbeatDueInMinutes: int | None
    heartbeatOverdueAtUtc: datetime | None
    heartbeatOverdue: bool
    leaseUntilUtc: datetime | None
    leaseExpired: bool
    leaseRemainingMinutes: int | None
    leaseExpiredMinutes: int | None
    reclaimableAtUtc: datetime
    reclaimable: bool
    claimHealth: str
    reclaimReason: str | None
    staleThresholdMinutes: int
    heartbeatIntervalMinutes: int

    @property
    def healthy(self) -> bool:
        return self.claimHealth == "healthy"

    @property
    def suspect(self) -> bool:
        return not self.healthy and not self.reclaimable

    def payload(self) -> dict[str, Any]:
        return {
            "lastHeartbeatAtUtc": formatUtc(self.lastHeartbeatAtUtc) if self.lastHeartbeatAtUtc else None,
            "heartbeatAgeMinutes": self.heartbeatAgeMinutes,
            "heartbeatDueAtUtc": formatUtc(self.heartbeatDueAtUtc) if self.heartbeatDueAtUtc else None,
            "heartbeatDueInMinutes": self.heartbeatDueInMinutes,
            "heartbeatOverdueAtUtc": formatUtc(self.heartbeatOverdueAtUtc) if self.heartbeatOverdueAtUtc else None,
            "heartbeatOverdue": self.heartbeatOverdue,
            "heartbeatIntervalMinutes": self.heartbeatIntervalMinutes,
            "leaseUntilUtc": formatUtc(self.leaseUntilUtc) if self.leaseUntilUtc else None,
            "leaseExpired": self.leaseExpired,
            "leaseRemainingMinutes": self.leaseRemainingMinutes,
            "leaseExpiredMinutes": self.leaseExpiredMinutes,
            "reclaimableAtUtc": formatUtc(self.reclaimableAtUtc),
            "reclaimable": self.reclaimable,
            "claimHealth": self.claimHealth,
            "reclaimReason": self.reclaimReason,
            "staleThresholdMinutes": self.staleThresholdMinutes,
            # Backward-compatible aliases for older controller payload readers.
            "updatedAtUtc": formatUtc(self.lastHeartbeatAtUtc) if self.lastHeartbeatAtUtc else None,
            "updatedAgeMinutes": self.heartbeatAgeMinutes,
            "staleReason": self.reclaimReason,
        }


@dataclass(frozen=True)
class QueueState:
    workbook: "XlsxDocument"
    sheet: "XlsxDocument"
    headers: dict[str, int]
    tasks: list[TaskRecord]


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
XML_NS = "http://www.w3.org/XML/1998/namespace"
CELL_REF_PATTERN = re.compile(r"^([A-Z]+)(\d+)$")


def xmlName(localName: str) -> str:
    return f"{{{MAIN_NS}}}{localName}"


def columnIndexToName(index: int) -> str:
    if index < 1:
        raise QueueError(f"Column index must be positive, got {index}")
    letters: list[str] = []
    while index:
        index, remainder = divmod(index - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


def columnNameToIndex(name: str) -> int:
    result = 0
    for character in name.upper():
        if not "A" <= character <= "Z":
            raise QueueError(f"Invalid column name: {name}")
        result = result * 26 + ord(character) - ord("A") + 1
    return result


def splitCellReference(reference: str) -> tuple[int, int]:
    match = CELL_REF_PATTERN.match(reference)
    if not match:
        raise QueueError(f"Invalid cell reference: {reference}")
    return int(match.group(2)), columnNameToIndex(match.group(1))


def parseXml(data: bytes) -> ET.Element:
    # Preserve every namespace found in the worksheet, including extension
    # namespaces that openpyxl would otherwise discard during a round trip.
    namespaces: list[tuple[str, str]] = []
    for _, namespace in ET.iterparse(io.BytesIO(data), events=("start-ns",)):
        if namespace not in namespaces:
            namespaces.append(namespace)
    for prefix, uri in namespaces:
        with contextlib.suppress(ValueError):
            ET.register_namespace(prefix or "", uri)
    return ET.fromstring(data)


class XlsxDocument:
    """Minimal OOXML worksheet editor that preserves unrelated ZIP parts.

    Only the canonical issue worksheet is parsed and serialized. Charts,
    drawings, tables, validation extensions, styles, and every other package
    part are copied byte-for-byte.
    """

    def __init__(
        self,
        sourcePath: Path,
        sheetPath: str,
        sheetRoot: ET.Element,
        sharedStrings: list[str],
    ) -> None:
        self.sourcePath = sourcePath
        self.sheetPath = sheetPath
        self.sheetRoot = sheetRoot
        self.sharedStrings = sharedStrings
        self.sheetData = sheetRoot.find(xmlName("sheetData"))
        if self.sheetData is None:
            raise QueueError(f"Worksheet {ISSUE_SHEET!r} has no sheetData")
        self._rows: dict[int, ET.Element] = {}
        self._cells: dict[tuple[int, int], ET.Element] = {}
        self._indexSheet()

    @classmethod
    def load(cls, workbookPath: Path) -> "XlsxDocument":
        with zipfile.ZipFile(workbookPath, "r") as archive:
            workbookRoot = parseXml(archive.read("xl/workbook.xml"))
            relationId: str | None = None
            sheets = workbookRoot.find(xmlName("sheets"))
            if sheets is not None:
                for sheet in sheets.findall(xmlName("sheet")):
                    if sheet.attrib.get("name") == ISSUE_SHEET:
                        relationId = sheet.attrib.get(f"{{{DOC_REL_NS}}}id")
                        break
            if not relationId:
                raise QueueError(f"Workbook is missing required sheet {ISSUE_SHEET!r}")

            relationRoot = parseXml(archive.read("xl/_rels/workbook.xml.rels"))
            target: str | None = None
            for relation in relationRoot.findall(f"{{{PKG_REL_NS}}}Relationship"):
                if relation.attrib.get("Id") == relationId:
                    target = relation.attrib.get("Target")
                    break
            if not target:
                raise QueueError(f"Cannot resolve worksheet relationship for {ISSUE_SHEET!r}")
            if target.startswith("/"):
                sheetPath = target.lstrip("/")
            else:
                sheetPath = posixpath.normpath(posixpath.join("xl", target))
            if sheetPath not in archive.namelist():
                raise QueueError(f"Resolved worksheet part is missing: {sheetPath}")

            sharedStrings: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                sharedRoot = parseXml(archive.read("xl/sharedStrings.xml"))
                for item in sharedRoot.findall(xmlName("si")):
                    sharedStrings.append("".join(node.text or "" for node in item.iter(xmlName("t"))))
            sheetRoot = parseXml(archive.read(sheetPath))
        return cls(workbookPath, sheetPath, sheetRoot, sharedStrings)

    def close(self) -> None:
        return

    def _indexSheet(self) -> None:
        self._rows.clear()
        self._cells.clear()
        for rowElement in self.sheetData.findall(xmlName("row")):
            rawRow = rowElement.attrib.get("r")
            if rawRow is None:
                continue
            rowIndex = int(rawRow)
            self._rows[rowIndex] = rowElement
            for cellElement in rowElement.findall(xmlName("c")):
                reference = cellElement.attrib.get("r")
                if not reference:
                    continue
                parsedRow, columnIndex = splitCellReference(reference)
                self._cells[(parsedRow, columnIndex)] = cellElement

    @property
    def maxRow(self) -> int:
        return max(self._rows, default=1)

    @property
    def maxColumn(self) -> int:
        return max((column for _, column in self._cells), default=1)

    def getCell(self, row: int, column: int) -> Any:
        cell = self._cells.get((row, column))
        if cell is None:
            return None
        cellType = cell.attrib.get("t")
        if cellType == "inlineStr":
            return "".join(node.text or "" for node in cell.iter(xmlName("t")))
        valueElement = cell.find(xmlName("v"))
        value = valueElement.text if valueElement is not None else None
        if value is None:
            return None
        if cellType == "s":
            try:
                return self.sharedStrings[int(value)]
            except (ValueError, IndexError):
                return value
        if cellType in {"str", "e"}:
            return value
        if cellType == "b":
            return value == "1"
        if cellType in {None, "n"}:
            try:
                number = float(value)
            except ValueError:
                return value
            return int(number) if number.is_integer() else number
        return value

    def setCell(self, row: int, column: int, value: Any) -> None:
        cell = self._cells.get((row, column))
        if cell is None:
            rowElement = self._ensureRow(row)
            cell = ET.Element(xmlName("c"), {"r": f"{columnIndexToName(column)}{row}"})
            inserted = False
            for index, sibling in enumerate(rowElement.findall(xmlName("c"))):
                siblingRef = sibling.attrib.get("r")
                if siblingRef and splitCellReference(siblingRef)[1] > column:
                    rowElement.insert(index, cell)
                    inserted = True
                    break
            if not inserted:
                rowElement.append(cell)
            self._cells[(row, column)] = cell

        for child in list(cell):
            cell.remove(child)
        cell.attrib.pop("t", None)

        if value is None:
            self._updateDimension()
            return
        if isinstance(value, bool):
            cell.attrib["t"] = "b"
            valueElement = ET.SubElement(cell, xmlName("v"))
            valueElement.text = "1" if value else "0"
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            cell.attrib["t"] = "n"
            valueElement = ET.SubElement(cell, xmlName("v"))
            valueElement.text = str(value)
        else:
            cell.attrib["t"] = "str"
            valueElement = ET.SubElement(cell, xmlName("v"))
            text = str(value)
            valueElement.text = text
            if text != text.strip():
                valueElement.attrib[f"{{{XML_NS}}}space"] = "preserve"
        self._updateDimension()

    def _ensureRow(self, row: int) -> ET.Element:
        existing = self._rows.get(row)
        if existing is not None:
            return existing
        rowElement = ET.Element(xmlName("row"), {"r": str(row)})
        inserted = False
        rows = self.sheetData.findall(xmlName("row"))
        for index, sibling in enumerate(rows):
            siblingRow = int(sibling.attrib.get("r", "0"))
            if siblingRow > row:
                self.sheetData.insert(index, rowElement)
                inserted = True
                break
        if not inserted:
            self.sheetData.append(rowElement)
        self._rows[row] = rowElement
        return rowElement

    def _updateDimension(self) -> None:
        dimension = self.sheetRoot.find(xmlName("dimension"))
        if dimension is None:
            dimension = ET.Element(xmlName("dimension"))
            self.sheetRoot.insert(0, dimension)
        dimension.attrib["ref"] = f"A1:{columnIndexToName(self.maxColumn)}{self.maxRow}"

    def save(self, workbookPath: Path) -> None:
        workbookPath.parent.mkdir(parents=True, exist_ok=True)
        tempFile = tempfile.NamedTemporaryFile(
            prefix=f".{workbookPath.stem}.",
            suffix=".tmp.xlsx",
            dir=workbookPath.parent,
            delete=False,
        )
        tempPath = Path(tempFile.name)
        tempFile.close()
        sheetBytes = ET.tostring(self.sheetRoot, encoding="utf-8", xml_declaration=True)
        try:
            with zipfile.ZipFile(self.sourcePath, "r") as sourceArchive:
                with zipfile.ZipFile(tempPath, "w") as targetArchive:
                    for item in sourceArchive.infolist():
                        data = sheetBytes if item.filename == self.sheetPath else sourceArchive.read(item.filename)
                        targetArchive.writestr(item, data)
            with tempPath.open("rb") as stream:
                os.fsync(stream.fileno())
            os.replace(tempPath, workbookPath)
            self.sourcePath = workbookPath
            if os.name != "nt":
                directoryFd = os.open(workbookPath.parent, os.O_RDONLY)
                try:
                    os.fsync(directoryFd)
                finally:
                    os.close(directoryFd)
        except PermissionError as exc:
            raise QueueError(
                f"Could not replace {workbookPath}. Close the workbook in Excel/LibreOffice and retry."
            ) from exc
        finally:
            with contextlib.suppress(FileNotFoundError):
                tempPath.unlink()


class WorkbookLock:
    """Portable advisory lock on a sidecar file.

    The lock file is intentionally separate from the XLSX because the XLSX is
    atomically replaced on every successful mutation.
    """

    def __init__(self, workbookPath: Path, timeoutSeconds: float = 30.0) -> None:
        if timeoutSeconds < 0:
            raise QueueError("--lock-timeout-seconds must be non-negative")
        self.workbookPath = workbookPath
        self.timeoutSeconds = timeoutSeconds
        self.lockPath = workbookPath.with_name(workbookPath.name + ".lock")
        self.handle: Any | None = None

    def __enter__(self) -> "WorkbookLock":
        self.lockPath.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.lockPath.open("a+b")
        if os.name == "nt":
            self.handle.seek(0, os.SEEK_END)
            if self.handle.tell() == 0:
                self.handle.write(b"0")
                self.handle.flush()
            self.handle.seek(0)

        deadline = time.monotonic() + self.timeoutSeconds
        while True:
            try:
                self._lockNonBlocking()
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise QueueError(
                        f"Timed out after {self.timeoutSeconds:.1f}s waiting for queue lock {self.lockPath}"
                    ) from exc
                time.sleep(0.1)

        metadata = {
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "lockedAtUtc": utcNowText(),
        }
        try:
            self.handle.seek(0)
            self.handle.truncate()
            self.handle.write(json.dumps(metadata).encode("utf-8"))
            self.handle.flush()
            os.fsync(self.handle.fileno())
        except OSError:
            # Lock ownership remains valid even if diagnostic metadata cannot be written.
            pass
        return self

    def __exit__(self, excType: Any, exc: Any, traceback: Any) -> None:
        if self.handle is None:
            return
        with contextlib.suppress(OSError):
            self._unlock()
        self.handle.close()
        self.handle = None

    def _lockNonBlocking(self) -> None:
        assert self.handle is not None
        if os.name == "nt":
            import msvcrt

            self.handle.seek(0)
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(self) -> None:
        assert self.handle is not None
        if os.name == "nt":
            import msvcrt

            self.handle.seek(0)
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)


def utcNow() -> datetime:
    return datetime.now(timezone.utc)


def utcNowText() -> str:
    return formatUtc(utcNow())


def formatUtc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parseUtc(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalizeStatus(value: Any) -> str:
    text = str(value or "").strip().upper().replace("-", "_")
    return LEGACY_STATUS_MAP.get(text, text)


def parseDependencies(value: Any) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    parts: list[str] = []
    for raw in re.split(r"[;\n]+", text):
        dependency = raw.strip()
        if dependency:
            parts.append(dependency)
    return list(dict.fromkeys(parts))


def parseTargetFiles(value: Any) -> set[str]:
    if value is None:
        return set()
    result: set[str] = set()
    for raw in re.split(r"[;\n]+", str(value)):
        path = raw.strip().replace("\\", "/")
        if path:
            result.add(path.rstrip("/"))
    return result


def parseInteger(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise QueueError(f"Expected integer value, got {value!r}") from exc


def readTextOption(text: str | None, filePath: str | None, optionName: str) -> str:
    if text and filePath:
        raise QueueError(f"Use either --{optionName} or --{optionName}-file, not both")
    if filePath:
        return Path(filePath).read_text(encoding="utf-8").strip()
    return (text or "").strip()


def ownerSegment(value: Any, fallback: str = "unknown", maxLength: int = 48) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9_.-]+", "-", text).strip("-_.")
    return (text[:maxLength].strip("-_.") or fallback)[:maxLength]


def generateControllerId(
    hostname: str | None = None,
    pid: int | None = None,
    unique: str | None = None,
) -> str:
    host = ownerSegment((hostname or socket.gethostname()).split(".", 1)[0], fallback="host", maxLength=32)
    process_id = pid if pid is not None else os.getpid()
    suffix = ownerSegment(unique or uuid.uuid4().hex[:8], fallback="run", maxLength=16)
    return f"ctrl-{host}-{process_id}-{suffix}"


def controllerOwnerPrefix(controllerId: str) -> str:
    controller = ownerSegment(controllerId, fallback="controller", maxLength=96)
    return f"controller/{controller}"


def controllerOwner(controllerId: str, worker: str = "subagent-1") -> str:
    return f"{controllerOwnerPrefix(controllerId)}/{ownerSegment(worker, fallback='worker', maxLength=48)}"


def controllerIdentityPayload(controllerId: str | None = None, worker: str = "subagent-1") -> dict[str, str]:
    generated = controllerId or generateControllerId()
    return {
        "controllerId": generated,
        "ownerPrefix": controllerOwnerPrefix(generated),
        "exampleOwner": controllerOwner(generated, worker),
    }


def resolveWorkbookPath(rawPath: str | Path | None) -> Path:
    if rawPath:
        path = Path(rawPath)
    elif os.environ.get("GAME_ISSUE_QUEUE_FILE"):
        path = Path(os.environ["GAME_ISSUE_QUEUE_FILE"])
    else:
        path = DEFAULT_WORKBOOK
    return path.expanduser().resolve()


def loadQueue(workbookPath: Path, writable: bool = False) -> QueueState:
    del writable
    if not workbookPath.is_file():
        raise QueueError(f"Queue workbook does not exist: {workbookPath}")
    document = XlsxDocument.load(workbookPath)
    headers: dict[str, int] = {}
    for column in range(1, document.maxColumn + 1):
        value = document.getCell(1, column)
        if value is not None:
            headers[str(value).strip()] = column
    tasks: list[TaskRecord] = []
    if all(header in headers for header in REQUIRED_HEADERS):
        for row in range(2, document.maxRow + 1):
            issueName = document.getCell(row, headers["Issue Name"])
            if issueName is None or not str(issueName).strip():
                continue
            values = {header: document.getCell(row, column) for header, column in headers.items()}
            tasks.append(TaskRecord(row=row, values=values))
    return QueueState(workbook=document, sheet=document, headers=headers, tasks=tasks)


def ensureWorkflowSchema(state: QueueState) -> bool:
    """Add missing workflow headers and normalize legacy queue cells."""

    changed = False
    headers = state.headers
    nextColumn = state.sheet.maxColumn + 1
    for header in WORKFLOW_HEADERS:
        if header not in headers:
            state.sheet.setCell(1, nextColumn, header)
            headers[header] = nextColumn
            nextColumn += 1
            changed = True
    for task in state.tasks:
        statusColumn = headers["Status"]
        existingStatus = state.sheet.getCell(task.row, statusColumn)
        normalized = normalizeStatus(existingStatus)
        if existingStatus != normalized:
            state.sheet.setCell(task.row, statusColumn, normalized)
            changed = True
        if state.sheet.getCell(task.row, headers["Progress %"]) is None:
            state.sheet.setCell(task.row, headers["Progress %"], 0)
            changed = True
        if state.sheet.getCell(task.row, headers["Attempt"]) is None:
            state.sheet.setCell(task.row, headers["Attempt"], 0)
            changed = True
    return changed


def refreshTasks(state: QueueState) -> QueueState:
    tasks: list[TaskRecord] = []
    for row in range(2, state.sheet.maxRow + 1):
        issueName = state.sheet.getCell(row, state.headers["Issue Name"])
        if issueName is None or not str(issueName).strip():
            continue
        values = {header: state.sheet.getCell(row, column) for header, column in state.headers.items()}
        tasks.append(TaskRecord(row=row, values=values))
    return QueueState(
        workbook=state.workbook,
        sheet=state.sheet,
        headers=state.headers,
        tasks=tasks,
    )


def setValue(state: QueueState, row: int, header: str, value: Any) -> None:
    if header not in state.headers:
        raise QueueError(f"Workbook is missing required column {header!r}")
    state.sheet.setCell(row, state.headers[header], value)


def atomicSave(state: QueueState, workbookPath: Path) -> None:
    state.workbook.save(workbookPath)


def taskByName(state: QueueState, issueName: str) -> TaskRecord:
    matches = [task for task in state.tasks if task.issueName == issueName]
    if not matches:
        raise QueueError(f"Unknown issue name: {issueName}")
    if len(matches) > 1:
        raise QueueError(f"Issue name is not unique: {issueName}")
    return matches[0]


def statusByIssue(state: QueueState) -> dict[str, str]:
    return {task.issueName: task.status for task in state.tasks}


def inactiveClaimIssueNames(
    state: QueueState,
    stale: Sequence[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> set[str]:
    now = now or utcNow()
    return {
        task.issueName
        for task in state.tasks
        if task.status == STATUS_IN_PROGRESS and not claimTimingHealth(task, now).healthy
    }


def activeTargetFiles(
    state: QueueState,
    excludeIssueName: str | None = None,
    stale: Sequence[dict[str, Any]] | None = None,
    now: datetime | None = None,
    includeInactive: bool = False,
) -> set[str]:
    files: set[str] = set()
    for task in state.tasks:
        if excludeIssueName is not None and task.issueName == excludeIssueName:
            continue
        if task.status == STATUS_IN_PROGRESS:
            files.update(task.targetFiles)
    return files


def taskActiveFileOverlaps(state: QueueState, task: TaskRecord, now: datetime | None = None) -> list[str]:
    return sorted(task.targetFiles & activeTargetFiles(state, excludeIssueName=task.issueName, now=now))


def taskSortKey(task: TaskRecord) -> tuple[Any, ...]:
    def numericSuffix(value: Any) -> int:
        match = re.search(r"(\d+)$", str(value or ""))
        return int(match.group(1)) if match else 9999

    return (
        PRIORITY_ORDER.get(task.priority, 99),
        numericSuffix(task.values.get("Epic #")),
        numericSuffix(task.values.get("Story #")),
        numericSuffix(task.values.get("Substory #")),
        task.row,
    )


def eligibleTasks(
    state: QueueState,
    priorities: set[str] | None = None,
    epic: str | None = None,
    component: str | None = None,
    allowFileOverlap: bool = False,
) -> tuple[list[TaskRecord], dict[str, list[str]]]:
    statuses = statusByIssue(state)
    eligible: list[TaskRecord] = []
    rejected: dict[str, list[str]] = {}
    for task in state.tasks:
        reasons: list[str] = []
        if task.status != STATUS_NOT_STARTED:
            reasons.append(f"status={task.status}")
        if priorities and task.priority not in priorities:
            reasons.append(f"priority={task.priority}")
        if epic and str(task.values.get("Epic #") or "").strip() != epic:
            reasons.append("epic-filter")
        if component:
            taskComponent = str(task.values.get("Component") or "")
            if component.lower() not in taskComponent.lower():
                reasons.append("component-filter")
        incomplete = [dependency for dependency in task.dependencies if statuses.get(dependency) != STATUS_DONE]
        if incomplete:
            reasons.append("dependencies-not-done:" + ",".join(incomplete))
        if reasons:
            rejected[task.issueName] = reasons
        else:
            eligible.append(task)
    eligible.sort(key=taskSortKey)
    return eligible, rejected


def targetFileOverlapAdvisories(
    state: QueueState,
    tasks: Iterable[TaskRecord] | None = None,
    stale: Sequence[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, list[str]]:
    activeFiles = activeTargetFiles(state, stale=stale, now=now)
    advisories: dict[str, list[str]] = {}
    for task in tasks if tasks is not None else state.tasks:
        if task.status != STATUS_NOT_STARTED:
            continue
        overlap = sorted(task.targetFiles & activeFiles)
        if overlap:
            advisories[task.issueName] = overlap
    return advisories


def controlPlaneAdvisories(tasks: Iterable[TaskRecord]) -> dict[str, list[str]]:
    """Map issue name -> matched control-plane target files for the given tasks.

    A row is flagged when its declared ``Target Files / Modules`` include the
    shared CI merge-gate or controller-governance files (``CONTROL_PLANE_PATHS``).
    This is advisory metadata only: eligibility and claim semantics are
    unchanged. It lets the controller/PM see that an otherwise-``CLEAN`` eligible
    row rewrites the validation authority gating all concurrent PRs and route it
    to a supervised lane rather than auto-claiming it.
    """

    controlPlane = set(CONTROL_PLANE_PATHS)
    advisories: dict[str, list[str]] = {}
    for task in tasks:
        matched = sorted(task.targetFiles & controlPlane)
        if matched:
            advisories[task.issueName] = matched
    return advisories


def rejectionReasonKey(reason: str) -> str:
    return reason.split(":", 1)[0].split("=", 1)[0]


def rejectionSummary(rejected: dict[str, list[str]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for reasons in rejected.values():
        for reason in reasons:
            key = rejectionReasonKey(reason)
            summary[key] = summary.get(key, 0) + 1
    return dict(sorted(summary.items()))


def statusCounts(state: QueueState) -> dict[str, int]:
    counts: dict[str, int] = {}
    for task in state.tasks:
        counts[task.status] = counts.get(task.status, 0) + 1
    return dict(sorted(counts.items()))


def activeClaimSummary(
    state: QueueState,
    stale: Sequence[dict[str, Any]],
    now: datetime | None = None,
    olderThanMinutes: int = DEFAULT_RECLAIM_AGE_MINUTES,
) -> dict[str, int]:
    now = now or utcNow()
    activeTasks = [task for task in state.tasks if task.status == STATUS_IN_PROGRESS]
    healthByIssue = {
        task.issueName: claimTimingHealth(task, now, olderThanMinutes=olderThanMinutes) for task in activeTasks
    }
    staleIssues = {issueName for issueName, health in healthByIssue.items() if health.heartbeatOverdue}
    leaseExpiredIssues = {issueName for issueName, health in healthByIssue.items() if health.leaseExpired}
    reclaimableIssues = {issueName for issueName, health in healthByIssue.items() if health.reclaimable}
    healthyCount = sum(1 for health in healthByIssue.values() if health.healthy)
    inactiveCount = len(activeTasks) - healthyCount
    return {
        "total": len(activeTasks),
        "unexpired": healthyCount,
        "healthy": healthyCount,
        "stale": len(staleIssues),
        "leaseExpired": len(leaseExpiredIssues),
        "reclaimable": len(reclaimableIssues),
        "suspect": inactiveCount - len(reclaimableIssues),
        "inactive": inactiveCount,
    }


def ownerMatchesPrefix(owner: str, ownerPrefix: str) -> bool:
    return owner == ownerPrefix or owner.startswith(f"{ownerPrefix}/")


def controllerCapacityPayload(
    state: QueueState,
    controllerId: str,
    activeFloor: int = DEFAULT_CONTROLLER_ACTIVE_ISSUE_FLOOR,
    activeLimit: int = DEFAULT_CONTROLLER_ACTIVE_ISSUE_LIMIT,
    eligibleCount: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if activeFloor < 0:
        raise QueueError("--controller-active-floor must be non-negative")
    if activeLimit < 0:
        raise QueueError("--controller-active-limit must be non-negative")
    if activeLimit < activeFloor:
        raise QueueError("--controller-active-limit must be greater than or equal to --controller-active-floor")
    controllerId = controllerId.strip()
    if not controllerId:
        raise QueueError("--controller-id must be non-empty")
    now = now or utcNow()
    ownerPrefix = controllerOwnerPrefix(controllerId)
    activeTasks = [
        task
        for task in state.tasks
        if task.status == STATUS_IN_PROGRESS
        and ownerMatchesPrefix(str(task.values.get("Owner") or "").strip(), ownerPrefix)
    ]
    healthByIssue = {task.issueName: claimTimingHealth(task, now) for task in activeTasks}
    healthyTasks = [task for task in activeTasks if healthByIssue[task.issueName].healthy]
    staleTasks = [task for task in activeTasks if healthByIssue[task.issueName].heartbeatOverdue]
    leaseExpiredTasks = [task for task in activeTasks if healthByIssue[task.issueName].leaseExpired]
    reclaimableTasks = [task for task in activeTasks if healthByIssue[task.issueName].reclaimable]
    suspectTasks = [task for task in activeTasks if healthByIssue[task.issueName].suspect]
    recoveryTasks = [task for task in activeTasks if not healthByIssue[task.issueName].healthy]
    activeNonStale = len(healthyTasks)
    deficit = max(0, activeFloor - activeNonStale)
    availableSlots = max(0, activeLimit - len(activeTasks))
    overLimitBy = max(0, len(activeTasks) - activeLimit)
    recoveryRequired = bool(recoveryTasks)
    fillableCandidate = (
        min(deficit, availableSlots, eligibleCount) if eligibleCount is not None else min(deficit, availableSlots)
    )
    fillable = 0 if recoveryRequired else fillableCandidate
    return {
        "controllerId": controllerId,
        "ownerPrefix": ownerPrefix,
        "activeFloor": activeFloor,
        "activeLimit": activeLimit,
        "activeTotal": len(activeTasks),
        "activeNonStale": activeNonStale,
        "healthyOwned": len(healthyTasks),
        "staleOwned": len(staleTasks),
        "leaseExpiredOwned": len(leaseExpiredTasks),
        "suspectOwned": len(suspectTasks),
        "reclaimableOwned": len(reclaimableTasks),
        "inactiveOwned": len(activeTasks) - activeNonStale,
        "deficitToFloor": deficit,
        "availableSlots": availableSlots,
        "overLimitBy": overLimitBy,
        "overCapacity": overLimitBy > 0,
        "eligibleCount": eligibleCount,
        "fillableDeficit": fillable,
        "needsRefill": fillable > 0,
        "recoveryRequired": recoveryRequired,
        "recoveryIssues": [
            {
                "issueName": task.issueName,
                "claimHealth": healthByIssue[task.issueName].claimHealth,
                "reclaimable": healthByIssue[task.issueName].reclaimable,
                "reclaimableAtUtc": formatUtc(healthByIssue[task.issueName].reclaimableAtUtc),
                "reclaimReason": healthByIssue[task.issueName].reclaimReason,
            }
            for task in sorted(recoveryTasks, key=taskSortKey)
        ],
        "refillBlockedByRecovery": recoveryRequired and deficit > 0,
        "activeIssues": [task.issueName for task in sorted(healthyTasks, key=taskSortKey)],
        "staleIssues": [task.issueName for task in sorted(staleTasks, key=taskSortKey)],
        "leaseExpiredIssues": [task.issueName for task in sorted(leaseExpiredTasks, key=taskSortKey)],
        "suspectIssues": [task.issueName for task in sorted(suspectTasks, key=taskSortKey)],
        "reclaimableIssues": [task.issueName for task in sorted(reclaimableTasks, key=taskSortKey)],
    }


def storyKey(task: TaskRecord) -> tuple[str, str]:
    return (
        str(task.values.get("Epic #") or "").strip(),
        str(task.values.get("Story #") or "").strip(),
    )


def storyKeyText(key: tuple[str, str]) -> str:
    return "/".join(key)


def stableChoice(items: Sequence[Any], seed: str, namespace: str, key: Any) -> Any:
    if not items:
        raise QueueError("Cannot select from an empty candidate list")
    return min(
        items,
        key=lambda item: (
            hashlib.sha256(f"{seed}|{namespace}|{key(item)}".encode("utf-8")).hexdigest(),
            key(item),
        ),
    )


def shortTaskPayload(task: TaskRecord, activeFiles: set[str] | None = None) -> dict[str, Any]:
    return {
        "issueName": task.issueName,
        "row": task.row,
        "priority": task.priority,
        "epic": str(task.values.get("Epic #") or "").strip(),
        "epicTitle": str(task.values.get("Epic Title") or "").strip(),
        "story": str(task.values.get("Story #") or "").strip(),
        "storyTitle": str(task.values.get("Story Title") or "").strip(),
        "substory": str(task.values.get("Substory #") or "").strip(),
        "substoryTitle": str(task.values.get("Substory Title") or "").strip(),
        "component": str(task.values.get("Component") or "").strip(),
        "targetFiles": sorted(task.targetFiles),
        "activeFileOverlaps": sorted(task.targetFiles & activeFiles) if activeFiles is not None else [],
        "dependencies": task.dependencies,
        "validation": str(task.values.get("Validation / Tests") or "").strip(),
    }


def shortlistTasks(
    state: QueueState,
    priorities: set[str] | None = None,
    epic: str | None = None,
    component: str | None = None,
    allowFileOverlap: bool = False,
    seed: str | None = None,
    includeRejected: bool = False,
    controllerId: str | None = None,
    controllerActiveFloor: int = DEFAULT_CONTROLLER_ACTIVE_ISSUE_FLOOR,
    controllerActiveLimit: int = DEFAULT_CONTROLLER_ACTIVE_ISSUE_LIMIT,
) -> dict[str, Any]:
    eligible, rejected = eligibleTasks(
        state,
        priorities=priorities,
        epic=epic,
        component=component,
        allowFileOverlap=allowFileOverlap,
    )
    now = utcNow()
    counts = statusCounts(state)
    stale = staleClaims(state, now=now)
    activeClaims = activeClaimSummary(state, stale, now=now)
    activeFiles = activeTargetFiles(state, stale=stale, now=now)
    advisoryOverlaps = targetFileOverlapAdvisories(state, stale=stale, now=now)
    controlPlaneRows = controlPlaneAdvisories(eligible)
    selectionSeed = seed or uuid.uuid4().hex
    payload: dict[str, Any] = {
        "eligible": bool(eligible),
        "selectionSeed": selectionSeed,
        "allowFileOverlap": allowFileOverlap,
        "targetFileOverlapPolicy": TARGET_FILE_OVERLAP_POLICY,
        "eligibleCount": len(eligible),
        "highestPriority": None,
        "highestPriorityEligibleCount": 0,
        "storyGroups": [],
        "selected": None,
        "statusCounts": counts,
        "activeCount": activeClaims["total"],
        "unexpiredActiveCount": activeClaims["unexpired"],
        "staleClaimCount": activeClaims["stale"],
        "activeClaims": activeClaims,
        "staleClaims": stale,
        "rejectedCount": len(rejected),
        "rejectionSummary": rejectionSummary(rejected),
        "advisoryTargetFileOverlapCount": len(advisoryOverlaps),
        "advisoryControlPlaneRowCount": len(controlPlaneRows),
        "mechanicalFilters": [
            "status=NOT_STARTED",
            "dependencies=DONE",
            "direct target-file overlaps reported as advisory metadata",
            "control-plane (CI gate/governance) target files reported as advisory metadata",
        ],
    }
    if controllerId:
        payload["controllerCapacity"] = controllerCapacityPayload(
            state,
            controllerId=controllerId,
            activeFloor=controllerActiveFloor,
            activeLimit=controllerActiveLimit,
            eligibleCount=len(eligible),
            now=now,
        )
    if includeRejected:
        payload["rejected"] = rejected
        payload["advisoryTargetFileOverlaps"] = advisoryOverlaps
        payload["advisoryControlPlaneRows"] = controlPlaneRows
    if not eligible:
        payload["reason"] = "No eligible task"
        return payload

    highestPriority = eligible[0].priority
    highestCandidates = [task for task in eligible if task.priority == highestPriority]
    grouped: dict[tuple[str, str], list[TaskRecord]] = {}
    for task in highestCandidates:
        grouped.setdefault(storyKey(task), []).append(task)

    selectedStoryKey = stableChoice(
        sorted(grouped),
        selectionSeed,
        "story",
        storyKeyText,
    )
    selectedTask = stableChoice(
        sorted(grouped[selectedStoryKey], key=taskSortKey),
        selectionSeed,
        "substory",
        lambda task: task.issueName,
    )
    storyGroups = []
    for key in sorted(grouped):
        tasks = sorted(grouped[key], key=taskSortKey)
        first = tasks[0]
        storyGroups.append(
            {
                "storyKey": storyKeyText(key),
                "epic": key[0],
                "epicTitle": str(first.values.get("Epic Title") or "").strip(),
                "story": key[1],
                "storyTitle": str(first.values.get("Story Title") or "").strip(),
                "priority": highestPriority,
                "eligibleCount": len(tasks),
                "selected": key == selectedStoryKey,
                "issues": [shortTaskPayload(task, activeFiles=activeFiles) for task in tasks],
            }
        )

    payload.update(
        {
            "highestPriority": highestPriority,
            "highestPriorityEligibleCount": len(highestCandidates),
            "storyGroups": storyGroups,
            "selected": {
                "storyKey": storyKeyText(selectedStoryKey),
                "issue": shortTaskPayload(selectedTask, activeFiles=activeFiles),
            },
        }
    )
    return payload


def validateQueueState(state: QueueState, now: datetime | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    now = now or utcNow()

    missing = [header for header in ALL_HEADERS if header not in state.headers]
    if missing:
        errors.append("Missing required columns: " + ", ".join(missing))
        return errors, warnings

    names: dict[str, int] = {}
    for task in state.tasks:
        if task.issueName in names:
            errors.append(f"Duplicate Issue Name at rows {names[task.issueName]} and {task.row}: {task.issueName}")
        else:
            names[task.issueName] = task.row
        if not ISSUE_NAME_PATTERN.match(task.issueName):
            errors.append(f"Row {task.row}: invalid issue name format: {task.issueName}")
        if task.status not in ALLOWED_STATUSES:
            errors.append(f"Row {task.row}: unsupported status {task.status!r}")

        try:
            progress = parseInteger(task.values.get("Progress %"), 0)
        except QueueError as exc:
            errors.append(f"Row {task.row}: {exc}")
            progress = 0
        if not 0 <= progress <= 100:
            errors.append(f"Row {task.row}: Progress % must be between 0 and 100, got {progress}")

        try:
            attempt = parseInteger(task.values.get("Attempt"), 0)
        except QueueError as exc:
            errors.append(f"Row {task.row}: {exc}")
            attempt = 0
        if attempt < 0:
            errors.append(f"Row {task.row}: Attempt must be non-negative")

        owner = str(task.values.get("Owner") or "").strip()
        claimId = str(task.values.get("Claim ID") or "").strip()
        claimedAt = parseUtc(task.values.get("Claimed At UTC"))
        updatedAt = parseUtc(task.values.get("Updated At UTC"))
        leaseUntil = parseUtc(task.values.get("Lease Until UTC"))
        completedAt = parseUtc(task.values.get("Completed At UTC"))

        if task.status == STATUS_IN_PROGRESS:
            if not owner:
                errors.append(f"Row {task.row}: IN_PROGRESS requires Owner")
            if not claimId:
                errors.append(f"Row {task.row}: IN_PROGRESS requires Claim ID")
            if claimedAt is None:
                errors.append(f"Row {task.row}: IN_PROGRESS requires valid Claimed At UTC")
            if updatedAt is None:
                errors.append(f"Row {task.row}: IN_PROGRESS requires valid Updated At UTC")
            if leaseUntil is None:
                errors.append(f"Row {task.row}: IN_PROGRESS requires valid Lease Until UTC")
            health = claimTimingHealth(task, now)
            if health.reclaimable:
                warnings.append(
                    f"Row {task.row}: IN_PROGRESS reclaimable claim ({health.reclaimReason}; "
                    f"last heartbeat {formatUtc(health.lastHeartbeatAtUtc) if health.lastHeartbeatAtUtc else 'missing'}, "
                    f"lease {formatUtc(health.leaseUntilUtc) if health.leaseUntilUtc else 'missing'}, "
                    f"reclaimable at {formatUtc(health.reclaimableAtUtc)}); inspect worker/worktree/PR state "
                    "and run reclaim-stale --dry-run before reclaiming"
                )
            elif health.heartbeatOverdue:
                warnings.append(
                    f"Row {task.row}: IN_PROGRESS heartbeat overdue but lease remains valid until "
                    f"{formatUtc(health.leaseUntilUtc) if health.leaseUntilUtc else 'missing'}; inspect worker status "
                    "and publish a verified heartbeat or recovery update before refilling this slot"
                )
            elif health.leaseExpired:
                warnings.append(
                    f"Row {task.row}: IN_PROGRESS lease expired but heartbeat "
                    f"{formatUtc(health.lastHeartbeatAtUtc) if health.lastHeartbeatAtUtc else 'missing'} has not met "
                    f"{DEFAULT_RECLAIM_AGE_MINUTES}-minute reclaim threshold; inspect worker status before refresh "
                    "or later reclaim-stale --dry-run"
                )
            if attempt < 1:
                errors.append(f"Row {task.row}: IN_PROGRESS requires Attempt >= 1")
            if progress >= 100:
                warnings.append(f"Row {task.row}: IN_PROGRESS has Progress %=100; complete it or lower progress")
        elif task.status == STATUS_NOT_STARTED:
            if claimId or leaseUntil:
                errors.append(f"Row {task.row}: NOT_STARTED must not retain Claim ID or active lease")
            if progress != 0:
                warnings.append(f"Row {task.row}: NOT_STARTED normally has Progress %=0")
        elif task.status == STATUS_DONE:
            if progress != 100:
                errors.append(f"Row {task.row}: DONE requires Progress %=100")
            if completedAt is None:
                errors.append(f"Row {task.row}: DONE requires valid Completed At UTC")
            if not str(task.values.get("Result Summary") or "").strip():
                errors.append(f"Row {task.row}: DONE requires Result Summary")
            if not str(task.values.get("Validation Results") or "").strip():
                errors.append(f"Row {task.row}: DONE requires Validation Results")

    allNames = set(names)
    graph: dict[str, list[str]] = {}
    for task in state.tasks:
        graph[task.issueName] = task.dependencies
        for dependency in task.dependencies:
            if dependency == task.issueName:
                errors.append(f"Row {task.row}: issue depends on itself")
            elif dependency not in allNames:
                errors.append(f"Row {task.row}: unknown dependency {dependency!r}")

    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            try:
                start = stack.index(name)
            except ValueError:
                start = 0
            errors.append("Dependency cycle: " + " -> ".join(stack[start:] + [name]))
            return
        visiting.add(name)
        stack.append(name)
        for dependency in graph.get(name, []):
            if dependency in graph:
                visit(dependency)
        stack.pop()
        visiting.remove(name)
        visited.add(name)

    for name in graph:
        visit(name)

    return errors, warnings


def taskPayload(task: TaskRecord, state: QueueState | None = None, now: datetime | None = None) -> dict[str, Any]:
    now = now or utcNow()
    payload = {key: value for key, value in task.values.items()}
    payload["Row"] = task.row
    payload["Status"] = task.status
    payload["Dependencies Parsed"] = task.dependencies
    payload["Target Files Parsed"] = sorted(task.targetFiles)
    payload["Target File Overlap Policy"] = TARGET_FILE_OVERLAP_POLICY
    payload["Active File Overlaps"] = taskActiveFileOverlaps(state, task, now=now) if state is not None else []
    payload.update(taskLeasePayload(task, now))
    return payload


def ageMinutes(now: datetime, then: datetime | None) -> int | None:
    if then is None:
        return None
    return max(0, int((now - then).total_seconds() // 60))


def minutesUntil(now: datetime, then: datetime | None) -> int | None:
    if then is None:
        return None
    return max(0, int((then - now).total_seconds() // 60))


def claimTimingHealth(
    task: TaskRecord,
    now: datetime,
    olderThanMinutes: int = DEFAULT_RECLAIM_AGE_MINUTES,
    heartbeatIntervalMinutes: int = DEFAULT_HEARTBEAT_INTERVAL_MINUTES,
) -> ClaimTimingHealth:
    if olderThanMinutes < 0:
        raise QueueError("--older-than-minutes must be non-negative")
    if heartbeatIntervalMinutes < 1:
        raise QueueError("heartbeat interval must be positive")

    leaseUntil = parseUtc(task.values.get("Lease Until UTC"))
    lastHeartbeat = parseUtc(task.values.get("Updated At UTC")) or parseUtc(task.values.get("Claimed At UTC"))
    heartbeatDueAt = lastHeartbeat + timedelta(minutes=heartbeatIntervalMinutes) if lastHeartbeat else None
    heartbeatOverdueAt = lastHeartbeat + timedelta(minutes=olderThanMinutes) if lastHeartbeat else None
    heartbeatOverdue = lastHeartbeat is None or lastHeartbeat <= now - timedelta(minutes=olderThanMinutes)
    leaseExpired = leaseUntil is None or leaseUntil <= now

    reclaimableBoundaries: list[datetime] = []
    if leaseUntil is not None:
        reclaimableBoundaries.append(leaseUntil)
    if lastHeartbeat is not None:
        reclaimableBoundaries.append(lastHeartbeat + timedelta(minutes=olderThanMinutes))
    reclaimableAt = max(reclaimableBoundaries) if reclaimableBoundaries else now
    reclaimable = leaseExpired and heartbeatOverdue and reclaimableAt <= now

    if not heartbeatOverdue and not leaseExpired:
        claimHealth = "healthy"
        reclaimReason = None
    elif reclaimable:
        claimHealth = "reclaimable"
        if leaseUntil is None and lastHeartbeat is None:
            reclaimReason = "missing lease and missing heartbeat"
        elif leaseUntil is None:
            reclaimReason = "missing lease and heartbeat overdue"
        elif lastHeartbeat is None:
            reclaimReason = "lease expired and missing heartbeat"
        else:
            reclaimReason = "lease expired and heartbeat overdue"
    elif heartbeatOverdue:
        claimHealth = "heartbeat_overdue_lease_valid"
        reclaimReason = "heartbeat overdue but lease still valid"
    else:
        claimHealth = "lease_expired_heartbeat_recent"
        reclaimReason = "lease expired but heartbeat recent"

    return ClaimTimingHealth(
        lastHeartbeatAtUtc=lastHeartbeat,
        heartbeatAgeMinutes=ageMinutes(now, lastHeartbeat),
        heartbeatDueAtUtc=heartbeatDueAt,
        heartbeatDueInMinutes=minutesUntil(now, heartbeatDueAt),
        heartbeatOverdueAtUtc=heartbeatOverdueAt,
        heartbeatOverdue=heartbeatOverdue,
        leaseUntilUtc=leaseUntil,
        leaseExpired=leaseExpired,
        leaseRemainingMinutes=minutesUntil(now, leaseUntil) if not leaseExpired else None,
        leaseExpiredMinutes=ageMinutes(now, leaseUntil) if leaseExpired else None,
        reclaimableAtUtc=reclaimableAt,
        reclaimable=reclaimable,
        claimHealth=claimHealth,
        reclaimReason=reclaimReason,
        staleThresholdMinutes=olderThanMinutes,
        heartbeatIntervalMinutes=heartbeatIntervalMinutes,
    )


def taskLeasePayload(task: TaskRecord, now: datetime) -> dict[str, Any]:
    if task.status != STATUS_IN_PROGRESS:
        return {}
    return claimTimingHealth(task, now).payload()


def staleClaimPayload(
    task: TaskRecord,
    now: datetime,
    olderThanMinutes: int = DEFAULT_RECLAIM_AGE_MINUTES,
) -> dict[str, Any] | None:
    if task.status != STATUS_IN_PROGRESS:
        return None
    health = claimTimingHealth(task, now, olderThanMinutes=olderThanMinutes)
    if not health.heartbeatOverdue:
        return None

    return {
        "issueName": task.issueName,
        "row": task.row,
        "owner": str(task.values.get("Owner") or ""),
        "claimId": str(task.values.get("Claim ID") or ""),
        **health.payload(),
    }


def staleClaims(
    state: QueueState,
    olderThanMinutes: int = DEFAULT_RECLAIM_AGE_MINUTES,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    if olderThanMinutes < 0:
        raise QueueError("--older-than-minutes must be non-negative")
    now = now or utcNow()
    records = [
        record
        for task in sorted(state.tasks, key=taskSortKey)
        if (record := staleClaimPayload(task, now, olderThanMinutes)) is not None
    ]
    return records


def reclaimableClaims(
    state: QueueState,
    olderThanMinutes: int = DEFAULT_RECLAIM_AGE_MINUTES,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    if olderThanMinutes < 0:
        raise QueueError("--older-than-minutes must be non-negative")
    now = now or utcNow()
    return [
        record for record in staleClaims(state, olderThanMinutes=olderThanMinutes, now=now) if record["reclaimable"]
    ]


def markStaleClaimsForInspection(stale: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **record,
            "reclaimReady": False,
            "timingEligible": bool(record.get("reclaimable")),
            "requiredInspection": "worker worktree, branch, pull request, and recoverable changes",
        }
        for record in stale
    ]


def claimTask(
    workbookPath: Path,
    owner: str,
    issueName: str | None = None,
    leaseMinutes: int = DEFAULT_LEASE_MINUTES,
    priorities: set[str] | None = None,
    epic: str | None = None,
    component: str | None = None,
    allowFileOverlap: bool = False,
    lockTimeoutSeconds: float = 30.0,
) -> dict[str, Any]:
    owner = owner.strip()
    if not owner:
        raise QueueError("--owner must be non-empty")
    if leaseMinutes < 1:
        raise QueueError("--lease-minutes must be positive")

    with WorkbookLock(workbookPath, lockTimeoutSeconds):
        state = loadQueue(workbookPath, writable=True)
        try:
            ensureWorkflowSchema(state)
            state = refreshTasks(state)
            now = utcNow()
            errors, _ = validateQueueState(state, now=now)
            if errors:
                raise QueueError("Queue validation failed before claim:\n- " + "\n- ".join(errors))

            if issueName:
                task = taskByName(state, issueName)
                eligible, rejected = eligibleTasks(
                    state,
                    priorities=priorities,
                    epic=epic,
                    component=component,
                    allowFileOverlap=allowFileOverlap,
                )
                if task.issueName not in {candidate.issueName for candidate in eligible}:
                    reasons = rejected.get(task.issueName, ["not eligible"])
                    raise QueueError(f"Issue is not eligible: {task.issueName}: {'; '.join(reasons)}")
            else:
                eligible, _ = eligibleTasks(
                    state,
                    priorities=priorities,
                    epic=epic,
                    component=component,
                    allowFileOverlap=allowFileOverlap,
                )
                if not eligible:
                    return {"claimed": False, "reason": "No eligible task"}
                task = eligible[0]

            claimId = str(uuid.uuid4())
            setValue(state, task.row, "Status", STATUS_IN_PROGRESS)
            setValue(state, task.row, "Owner", owner)
            setValue(state, task.row, "Claim ID", claimId)
            setValue(state, task.row, "Claimed At UTC", formatUtc(now))
            setValue(state, task.row, "Updated At UTC", formatUtc(now))
            setValue(state, task.row, "Lease Until UTC", formatUtc(now + timedelta(minutes=leaseMinutes)))
            setValue(state, task.row, "Completed At UTC", None)
            setValue(state, task.row, "Progress %", 0)
            setValue(state, task.row, "Last Note", f"Claimed by {owner}")
            setValue(state, task.row, "Result Summary", None)
            setValue(state, task.row, "Validation Results", None)
            setValue(state, task.row, "Attempt", parseInteger(task.values.get("Attempt"), 0) + 1)
            atomicSave(state, workbookPath)

            state = refreshTasks(state)
            claimed = taskByName(state, task.issueName)
            payload = taskPayload(claimed, state=state, now=now)
            payload.update({"claimed": True, "claimId": claimId, "owner": owner})
            return payload
        finally:
            state.workbook.close()


def proposeTask(
    workbookPath: Path,
    *,
    issueName: str,
    epicTitle: str,
    storyTitle: str,
    substoryTitle: str,
    priority: str,
    component: str,
    targetFiles: Sequence[str],
    issueType: str = "Bug",
    dependencies: str = "None",
    description: str = "",
    acceptance: str = "",
    validation: str = "",
    sourceUrls: Sequence[str] = (),
    sprint: str = "None",
    lockTimeoutSeconds: float = 30.0,
) -> dict[str, Any]:
    """Append a new NOT_STARTED issue row to the canonical workbook.

    The row is validated transactionally: it is only persisted when the
    resulting queue still passes ``validateQueueState`` so a malformed proposal
    can never corrupt the backlog.
    """

    issueName = issueName.strip()
    tokens = ISSUE_NAME_TOKENS.match(issueName)
    if not tokens:
        raise QueueError(
            "Issue name must match [EPIC_NN][STORY_NN][SUBSTORY_NN]<title>, got: " + (issueName or "<empty>")
        )
    priority = priority.strip().upper()
    if priority not in VALID_PRIORITIES:
        raise QueueError(f"--priority must be one of {', '.join(VALID_PRIORITIES)}, got {priority or '<empty>'}")
    requiredText = {
        "--epic-title": epicTitle,
        "--story-title": storyTitle,
        "--substory-title": substoryTitle,
        "--component": component,
    }
    for label, value in requiredText.items():
        if not str(value or "").strip():
            raise QueueError(f"{label} must be non-empty")
    targets = [line.strip() for line in targetFiles if str(line or "").strip()]
    if not targets:
        raise QueueError("--target-file must be provided at least once")
    urls = [line.strip() for line in sourceUrls if str(line or "").strip()]
    # The workbook stores "no dependencies" as an empty cell; the literal token
    # "None" is normalized away so it is not treated as an unknown dependency.
    deps = [
        token.strip()
        for token in re.split(r"[;\n]+", str(dependencies or ""))
        if token.strip() and token.strip().lower() != "none"
    ]

    epicNumber, storyNumber, substoryNumber, _title = tokens.groups()

    with WorkbookLock(workbookPath, lockTimeoutSeconds):
        state = loadQueue(workbookPath, writable=True)
        try:
            ensureWorkflowSchema(state)
            state = refreshTasks(state)
            now = utcNow()
            errors, _ = validateQueueState(state, now=now)
            if errors:
                raise QueueError("Queue validation failed before propose:\n- " + "\n- ".join(errors))

            duplicate = next((task for task in state.tasks if task.issueName == issueName), None)
            if duplicate is not None:
                raise QueueError(f"Issue name already exists at row {duplicate.row}: {issueName}")

            newRow = state.sheet.maxRow + 1
            cells: dict[str, Any] = {
                "Issue Name": issueName,
                "Epic #": epicNumber,
                "Epic Title": epicTitle.strip(),
                "Story #": storyNumber,
                "Story Title": storyTitle.strip(),
                "Substory #": substoryNumber,
                "Substory Title": substoryTitle.strip(),
                "Priority": priority,
                "Issue Type": (issueType or "Bug").strip() or "Bug",
                "Component": component.strip(),
                "Dependencies": "\n".join(deps) if deps else None,
                "Target Files / Modules": "\n".join(targets),
                "Technical Code-Level Description": (description or "").strip(),
                "Acceptance Criteria": (acceptance or "").strip(),
                "Validation / Tests": (validation or "").strip(),
                "Source URLs": "\n".join(urls) if urls else None,
                "Status": STATUS_NOT_STARTED,
                "Owner": "",
                "Sprint": (sprint or "").strip() or None,
                "Claim ID": "",
                "Claimed At UTC": None,
                "Updated At UTC": None,
                "Lease Until UTC": None,
                "Completed At UTC": None,
                "Progress %": 0,
                "Last Note": "",
                "Result Summary": "",
                "Validation Results": "",
                "Attempt": 0,
            }
            for header, value in cells.items():
                setValue(state, newRow, header, value)

            state = refreshTasks(state)
            postErrors, postWarnings = validateQueueState(state, now=now)
            if postErrors:
                raise QueueError("Proposed row would invalidate the queue:\n- " + "\n- ".join(postErrors))

            atomicSave(state, workbookPath)
            state = refreshTasks(state)
            proposed = taskByName(state, issueName)
            payload = taskPayload(proposed, state=state, now=now)
            payload.update({"proposed": True, "row": proposed.row, "warnings": postWarnings})
            return payload
        finally:
            state.workbook.close()


def requireClaim(state: QueueState, issueName: str, claimId: str, owner: str) -> TaskRecord:
    task = taskByName(state, issueName)
    actualClaim = str(task.values.get("Claim ID") or "").strip()
    actualOwner = str(task.values.get("Owner") or "").strip()
    if actualClaim != claimId.strip():
        raise QueueError(f"Claim ID mismatch for {issueName}")
    if actualOwner != owner.strip():
        raise QueueError(f"Owner mismatch for {issueName}: expected {actualOwner!r}, got {owner!r}")
    return task


def heartbeatTask(
    workbookPath: Path,
    issueName: str,
    claimId: str,
    owner: str,
    progress: int | None,
    note: str,
    leaseMinutes: int = DEFAULT_LEASE_MINUTES,
    lockTimeoutSeconds: float = 30.0,
) -> dict[str, Any]:
    if progress is not None and not 0 <= progress <= 99:
        raise QueueError("heartbeat --progress must be between 0 and 99")
    if leaseMinutes < 1:
        raise QueueError("--lease-minutes must be positive")
    with WorkbookLock(workbookPath, lockTimeoutSeconds):
        state = loadQueue(workbookPath, writable=True)
        try:
            ensureWorkflowSchema(state)
            state = refreshTasks(state)
            task = requireClaim(state, issueName, claimId, owner)
            if task.status != STATUS_IN_PROGRESS:
                raise QueueError(f"heartbeat requires IN_PROGRESS, got {task.status}")
            now = utcNow()
            previousTiming = claimTimingHealth(task, now)
            if progress is not None:
                setValue(state, task.row, "Progress %", progress)
            if note.strip():
                setValue(state, task.row, "Last Note", note.strip())
            setValue(state, task.row, "Updated At UTC", formatUtc(now))
            requestedLeaseUntil = now + timedelta(minutes=leaseMinutes)
            currentLeaseUntil = parseUtc(task.values.get("Lease Until UTC"))
            leaseUntil = max(currentLeaseUntil, requestedLeaseUntil) if currentLeaseUntil else requestedLeaseUntil
            setValue(state, task.row, "Lease Until UTC", formatUtc(leaseUntil))
            atomicSave(state, workbookPath)
            state = refreshTasks(state)
            updatedTask = taskByName(state, issueName)
            payload = taskPayload(updatedTask, state=state, now=now)
            payload["previousTiming"] = previousTiming.payload()
            payload["resultingTiming"] = claimTimingHealth(updatedTask, now).payload()
            return payload
        finally:
            state.workbook.close()


def finishTask(
    workbookPath: Path,
    issueName: str,
    claimId: str,
    owner: str,
    status: str,
    note: str = "",
    summary: str = "",
    validation: str = "",
    lockTimeoutSeconds: float = 30.0,
) -> dict[str, Any]:
    if status not in {STATUS_DONE, STATUS_BLOCKED, STATUS_FAILED, STATUS_CANCELLED}:
        raise QueueError(f"Unsupported terminal status: {status}")
    if status == STATUS_DONE and (not summary.strip() or not validation.strip()):
        raise QueueError("complete requires non-empty result summary and validation results")

    with WorkbookLock(workbookPath, lockTimeoutSeconds):
        state = loadQueue(workbookPath, writable=True)
        try:
            ensureWorkflowSchema(state)
            state = refreshTasks(state)
            task = requireClaim(state, issueName, claimId, owner)
            if task.status != STATUS_IN_PROGRESS:
                raise QueueError(f"Task transition requires IN_PROGRESS, got {task.status}")
            now = utcNow()
            setValue(state, task.row, "Status", status)
            setValue(state, task.row, "Updated At UTC", formatUtc(now))
            setValue(state, task.row, "Lease Until UTC", None)
            if status == STATUS_DONE:
                setValue(state, task.row, "Completed At UTC", formatUtc(now))
                setValue(state, task.row, "Progress %", 100)
                setValue(state, task.row, "Result Summary", summary.strip())
                setValue(state, task.row, "Validation Results", validation.strip())
                setValue(state, task.row, "Last Note", note.strip() or "Completed")
            else:
                setValue(state, task.row, "Completed At UTC", None)
                if summary.strip():
                    setValue(state, task.row, "Result Summary", summary.strip())
                if validation.strip():
                    setValue(state, task.row, "Validation Results", validation.strip())
                setValue(state, task.row, "Last Note", note.strip() or status.title())
            atomicSave(state, workbookPath)
            state = refreshTasks(state)
            return taskPayload(taskByName(state, issueName), state=state)
        finally:
            state.workbook.close()


def releaseTask(
    workbookPath: Path,
    issueName: str,
    claimId: str,
    owner: str,
    note: str,
    lockTimeoutSeconds: float = 30.0,
) -> dict[str, Any]:
    with WorkbookLock(workbookPath, lockTimeoutSeconds):
        state = loadQueue(workbookPath, writable=True)
        try:
            ensureWorkflowSchema(state)
            state = refreshTasks(state)
            task = requireClaim(state, issueName, claimId, owner)
            if task.status not in {STATUS_IN_PROGRESS, STATUS_BLOCKED, STATUS_FAILED}:
                raise QueueError(f"release is not valid from status {task.status}")
            now = utcNowText()
            setValue(state, task.row, "Status", STATUS_NOT_STARTED)
            setValue(state, task.row, "Owner", None)
            setValue(state, task.row, "Claim ID", None)
            setValue(state, task.row, "Claimed At UTC", None)
            setValue(state, task.row, "Updated At UTC", now)
            setValue(state, task.row, "Lease Until UTC", None)
            setValue(state, task.row, "Completed At UTC", None)
            setValue(state, task.row, "Progress %", 0)
            setValue(state, task.row, "Last Note", note.strip() or f"Released by {owner}")
            setValue(state, task.row, "Result Summary", None)
            setValue(state, task.row, "Validation Results", None)
            atomicSave(state, workbookPath)
            state = refreshTasks(state)
            return taskPayload(taskByName(state, issueName), state=state)
        finally:
            state.workbook.close()


def reclaimStaleTasks(
    workbookPath: Path,
    olderThanMinutes: int = DEFAULT_RECLAIM_AGE_MINUTES,
    lockTimeoutSeconds: float = 30.0,
) -> list[dict[str, Any]]:
    if olderThanMinutes < 0:
        raise QueueError("--older-than-minutes must be non-negative")
    with WorkbookLock(workbookPath, lockTimeoutSeconds):
        state = loadQueue(workbookPath, writable=True)
        reclaimed: list[dict[str, Any]] = []
        try:
            ensureWorkflowSchema(state)
            state = refreshTasks(state)
            now = utcNow()
            for stale in reclaimableClaims(state, olderThanMinutes=olderThanMinutes, now=now):
                task = taskByName(state, stale["issueName"])
                priorOwner = str(task.values.get("Owner") or "unknown")
                priorClaim = str(task.values.get("Claim ID") or "unknown")
                setValue(state, task.row, "Status", STATUS_NOT_STARTED)
                setValue(state, task.row, "Owner", None)
                setValue(state, task.row, "Claim ID", None)
                setValue(state, task.row, "Claimed At UTC", None)
                setValue(state, task.row, "Updated At UTC", formatUtc(now))
                setValue(state, task.row, "Lease Until UTC", None)
                setValue(state, task.row, "Completed At UTC", None)
                setValue(state, task.row, "Progress %", 0)
                setValue(
                    state,
                    task.row,
                    "Last Note",
                    f"Stale claim reclaimed from {priorOwner}; prior claim {priorClaim}",
                )
                setValue(state, task.row, "Result Summary", None)
                setValue(state, task.row, "Validation Results", None)
                reclaimed.append(
                    {
                        **stale,
                        "priorOwner": priorOwner,
                        "priorClaimId": priorClaim,
                    }
                )
            if reclaimed:
                atomicSave(state, workbookPath)
            return reclaimed
        finally:
            state.workbook.close()


def renderWorkerPrompt(task: TaskRecord) -> str:
    values = task.values
    targetFiles = (
        str(values.get("Target Files / Modules") or "").strip() or "Determine from verified source inspection."
    )
    dependencies = "\n".join(f"- {item}" for item in task.dependencies) or "- None"
    return f"""You are a Codex worker subagent operating in the Fall of Nouraajd repository.

Queue identity
- Issue: {task.issueName}
- Claim ID: {values.get('Claim ID')}
- Owner: {values.get('Owner')}
- Priority: {values.get('Priority')}
- Component: {values.get('Component')}

1. Goal
{values.get('Substory Title')}

2. Git delivery
Git commit, push, and pull-request operations are outside this local orchestration phase.
Do not commit, push, merge, or open a PR. The controller handles integration.

3. Scope
{values.get('Technical Code-Level Description')}

4. Relevant files to inspect
{targetFiles}

5. Required source verification
Inspect the relevant project files first.
Verify repository-specific claims against GitHub raw source files when available.
Do not assume names, ids, resource paths, dialog wiring, runtime object names, APIs, or method names.
Explain the verified root cause before editing.
Make the smallest safe change that fixes or implements the verified issue.
Preserve backward compatibility unless something is clearly broken.

6. Dependencies
{dependencies}

7. Acceptance criteria
{values.get('Acceptance Criteria')}

8. Required validation
{values.get('Validation / Tests')}

9. Queue protocol
- Report queue milestones to the controller after source inspection, root-cause analysis, implementation, focused
    validation, and full validation.
- Include this exact Claim ID and Owner in milestone reports so the controller can publish workbook updates from a
    workbook-only branch.
- The controller owns workbook updates; worker implementation branches must not edit the workbook or workflow columns.
- Do not run issue_queue.py heartbeat, complete, block, fail, cancel, or release from this implementation worktree.
- On success, provide a result summary and exact validation results for controller completion.
- On a verified blocker, report a precise reason to the controller. Do not invent missing source details.

10. Required final report
Report:
- what was checked
- what was broken
- what changed
- what still needs manual review
- exact tests/commands run and their results
"""


def listTasks(
    state: QueueState,
    statuses: set[str] | None,
    owner: str | None,
    epic: str | None,
) -> list[TaskRecord]:
    result: list[TaskRecord] = []
    for task in state.tasks:
        if statuses and task.status not in statuses:
            continue
        if owner and str(task.values.get("Owner") or "") != owner:
            continue
        if epic and str(task.values.get("Epic #") or "") != epic:
            continue
        result.append(task)
    return sorted(result, key=taskSortKey)


def printJson(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def printTable(tasks: Sequence[TaskRecord]) -> None:
    if not tasks:
        print("No tasks.")
        return
    now = utcNow()
    rows = [
        (
            task.status,
            task.priority,
            str(task.values.get("Owner") or ""),
            str(task.values.get("Progress %") or 0),
            "expired" if taskLeasePayload(task, now).get("leaseExpired") else "",
            task.issueName,
        )
        for task in tasks
    ]
    header = ("STATUS", "PRI", "OWNER", "%", "LEASE", "ISSUE")
    widths = [max(len(row[index]) for row in rows + [header]) for index in range(len(header))]
    print("  ".join(header[index].ljust(widths[index]) for index in range(len(header))))
    print("  ".join("-" * widths[index] for index in range(len(header))))
    for row in rows:
        print("  ".join(row[index].ljust(widths[index]) for index in range(len(header))))


def addCommonArguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workbook",
        default=None,
        help=f"Queue workbook path. Default: $GAME_ISSUE_QUEUE_FILE or {DEFAULT_WORKBOOK}",
    )
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)


def buildParser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    controllerParser = subparsers.add_parser("controller-id", help="Generate a unique controller owner prefix")
    addCommonArguments(controllerParser)
    controllerParser.add_argument("--controller-id", help="Reuse an existing controller id instead of generating one")
    controllerParser.add_argument("--worker", default="subagent-1", help="Worker name for the example owner")
    controllerParser.add_argument("--plain", action="store_true", help="Print only the controller id")

    initParser = subparsers.add_parser("init", help="Add missing workflow columns and normalize legacy statuses")
    addCommonArguments(initParser)

    validateParser = subparsers.add_parser("validate", help="Validate queue schema and state invariants")
    addCommonArguments(validateParser)

    proposeParser = subparsers.add_parser(
        "propose", help="Append a new NOT_STARTED issue (e.g. an autonomously discovered bug)"
    )
    addCommonArguments(proposeParser)
    proposeParser.add_argument(
        "--issue-name", required=True, help="[EPIC_NN][STORY_NN][SUBSTORY_NN]<title>"
    )
    proposeParser.add_argument("--epic-title", required=True)
    proposeParser.add_argument("--story-title", required=True)
    proposeParser.add_argument("--substory-title", required=True)
    proposeParser.add_argument("--priority", required=True, help="P0, P1, or P2")
    proposeParser.add_argument("--component", required=True)
    proposeParser.add_argument(
        "--target-file", action="append", default=[], help="Target file/module; may be repeated"
    )
    proposeParser.add_argument("--issue-type", default="Bug")
    proposeParser.add_argument("--dependencies", default="None")
    proposeParser.add_argument("--description")
    proposeParser.add_argument("--description-file")
    proposeParser.add_argument("--acceptance")
    proposeParser.add_argument("--acceptance-file")
    proposeParser.add_argument("--validation")
    proposeParser.add_argument("--validation-file")
    proposeParser.add_argument(
        "--source-url", action="append", default=[], help="Evidence/source URL; may be repeated"
    )
    proposeParser.add_argument("--sprint", default="None")

    listParser = subparsers.add_parser("list", help="List tasks")
    addCommonArguments(listParser)
    listParser.add_argument("--status", action="append", default=[])
    listParser.add_argument("--owner")
    listParser.add_argument("--epic")
    listParser.add_argument("--json", action="store_true")

    showParser = subparsers.add_parser("show", help="Show one task as JSON")
    addCommonArguments(showParser)
    showParser.add_argument("--issue", required=True)

    nextParser = subparsers.add_parser("next", help="Preview the next eligible task without claiming it")
    addCommonArguments(nextParser)
    nextParser.add_argument("--owner", default="preview")
    nextParser.add_argument("--priority", action="append", default=[])
    nextParser.add_argument("--epic")
    nextParser.add_argument("--component")
    nextParser.add_argument(
        "--allow-file-overlap",
        action="store_true",
        help="Compatibility no-op; target-file overlaps are advisory.",
    )

    shortlistParser = subparsers.add_parser(
        "shortlist",
        help="Show read-only eligible story groups and a seeded recommendation",
    )
    addCommonArguments(shortlistParser)
    shortlistParser.add_argument("--priority", action="append", default=[])
    shortlistParser.add_argument("--epic")
    shortlistParser.add_argument("--component")
    shortlistParser.add_argument(
        "--allow-file-overlap",
        action="store_true",
        help="Compatibility no-op; target-file overlaps are advisory.",
    )
    shortlistParser.add_argument("--seed", help="Stable seed for reproducible story and substory selection")
    shortlistParser.add_argument("--include-rejected", action="store_true", help="Include per-issue rejection reasons")
    shortlistParser.add_argument("--json", action="store_true", help="Output JSON (default)")
    shortlistParser.add_argument("--controller-id", help="Include active-worker capacity status for this controller")
    shortlistParser.add_argument(
        "--controller-active-floor",
        type=int,
        default=DEFAULT_CONTROLLER_ACTIVE_ISSUE_FLOOR,
        help=(
            "Minimum healthy active issues this controller should keep when eligible work exists "
            f"(default: {DEFAULT_CONTROLLER_ACTIVE_ISSUE_FLOOR})"
        ),
    )
    shortlistParser.add_argument(
        "--controller-active-limit",
        type=int,
        default=DEFAULT_CONTROLLER_ACTIVE_ISSUE_LIMIT,
        help=(
            "Maximum unresolved implementation claims this controller should own at once "
            f"(default: {DEFAULT_CONTROLLER_ACTIVE_ISSUE_LIMIT})"
        ),
    )

    claimParser = subparsers.add_parser("claim", help="Atomically claim an eligible task")
    addCommonArguments(claimParser)
    claimParser.add_argument("--owner", required=True)
    claimParser.add_argument("--issue")
    claimParser.add_argument("--lease-minutes", type=int, default=DEFAULT_LEASE_MINUTES)
    claimParser.add_argument("--priority", action="append", default=[])
    claimParser.add_argument("--epic")
    claimParser.add_argument("--component")
    claimParser.add_argument(
        "--allow-file-overlap",
        action="store_true",
        help="Compatibility no-op; target-file overlaps are advisory.",
    )
    claimParser.add_argument("--format", choices=("json", "prompt"), default="json")

    heartbeatParser = subparsers.add_parser("heartbeat", help="Update progress and extend an active claim lease")
    addCommonArguments(heartbeatParser)
    heartbeatParser.add_argument("--issue", required=True)
    heartbeatParser.add_argument("--claim-id", required=True)
    heartbeatParser.add_argument("--owner", required=True)
    heartbeatParser.add_argument("--progress", type=int)
    heartbeatParser.add_argument("--note", default="")
    heartbeatParser.add_argument("--lease-minutes", type=int, default=DEFAULT_LEASE_MINUTES)

    promptParser = subparsers.add_parser("prompt", help="Render a claimed task as a worker-agent prompt")
    addCommonArguments(promptParser)
    promptParser.add_argument("--issue", required=True)
    promptParser.add_argument("--claim-id", required=True)
    promptParser.add_argument("--owner", required=True)

    completeParser = subparsers.add_parser("complete", help="Mark an active claim DONE")
    addCommonArguments(completeParser)
    completeParser.add_argument("--issue", required=True)
    completeParser.add_argument("--claim-id", required=True)
    completeParser.add_argument("--owner", required=True)
    completeParser.add_argument("--note", default="")
    completeParser.add_argument("--summary")
    completeParser.add_argument("--summary-file")
    completeParser.add_argument("--validation")
    completeParser.add_argument("--validation-file")

    for command, status in (("block", STATUS_BLOCKED), ("fail", STATUS_FAILED), ("cancel", STATUS_CANCELLED)):
        finishParser = subparsers.add_parser(command, help=f"Mark an active claim {status}")
        addCommonArguments(finishParser)
        finishParser.add_argument("--issue", required=True)
        finishParser.add_argument("--claim-id", required=True)
        finishParser.add_argument("--owner", required=True)
        finishParser.add_argument("--note", required=True)
        finishParser.add_argument("--summary")
        finishParser.add_argument("--summary-file")
        finishParser.add_argument("--validation")
        finishParser.add_argument("--validation-file")
        finishParser.set_defaults(targetStatus=status)

    releaseParser = subparsers.add_parser("release", help="Return an owned task to NOT_STARTED")
    addCommonArguments(releaseParser)
    releaseParser.add_argument("--issue", required=True)
    releaseParser.add_argument("--claim-id", required=True)
    releaseParser.add_argument("--owner", required=True)
    releaseParser.add_argument("--note", default="")

    reclaimParser = subparsers.add_parser("reclaim-stale", help="Release stale IN_PROGRESS claims")
    addCommonArguments(reclaimParser)
    reclaimParser.add_argument(
        "--older-than-minutes",
        type=int,
        default=DEFAULT_RECLAIM_AGE_MINUTES,
        help=(
            "Only reclaim claims whose last update is at least this many minutes old "
            f"(default: {DEFAULT_RECLAIM_AGE_MINUTES})"
        ),
    )
    reclaimParser.add_argument("--dry-run", action="store_true", help="Report stale claims without modifying the queue")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = buildParser()
    args = parser.parse_args(argv)
    if args.command == "controller-id":
        payload = controllerIdentityPayload(args.controller_id, args.worker)
        if args.plain:
            print(payload["controllerId"])
        else:
            printJson(payload)
        return 0

    workbookPath = resolveWorkbookPath(args.workbook)

    try:
        if args.command == "init":
            with WorkbookLock(workbookPath, args.lock_timeout_seconds):
                state = loadQueue(workbookPath, writable=True)
                try:
                    changed = ensureWorkflowSchema(state)
                    if changed:
                        atomicSave(state, workbookPath)
                    printJson({"workbook": str(workbookPath), "changed": changed})
                finally:
                    state.workbook.close()
            return 0

        if args.command == "validate":
            state = loadQueue(workbookPath, writable=False)
            try:
                errors, warnings = validateQueueState(state)
            finally:
                state.workbook.close()
            printJson({"workbook": str(workbookPath), "errors": errors, "warnings": warnings})
            return 1 if errors else 0

        if args.command == "propose":
            description = readTextOption(args.description, args.description_file, "description")
            acceptance = readTextOption(args.acceptance, args.acceptance_file, "acceptance")
            validation = readTextOption(args.validation, args.validation_file, "validation")
            printJson(
                proposeTask(
                    workbookPath,
                    issueName=args.issue_name,
                    epicTitle=args.epic_title,
                    storyTitle=args.story_title,
                    substoryTitle=args.substory_title,
                    priority=args.priority,
                    component=args.component,
                    targetFiles=args.target_file,
                    issueType=args.issue_type,
                    dependencies=args.dependencies,
                    description=description,
                    acceptance=acceptance,
                    validation=validation,
                    sourceUrls=args.source_url,
                    sprint=args.sprint,
                    lockTimeoutSeconds=args.lock_timeout_seconds,
                )
            )
            return 0

        if args.command in {"list", "show", "next", "shortlist", "prompt"}:
            state = loadQueue(workbookPath, writable=False)
            try:
                now = utcNow()
                if args.command == "list":
                    statuses = {normalizeStatus(item) for item in args.status} if args.status else None
                    tasks = listTasks(state, statuses, args.owner, args.epic)
                    if args.json:
                        printJson([taskPayload(task, state=state, now=now) for task in tasks])
                    else:
                        printTable(tasks)
                    return 0
                if args.command == "show":
                    printJson(taskPayload(taskByName(state, args.issue), state=state, now=now))
                    return 0
                if args.command == "next":
                    priorities = {item.upper() for item in args.priority} or None
                    eligible, rejected = eligibleTasks(
                        state,
                        priorities=priorities,
                        epic=args.epic,
                        component=args.component,
                        allowFileOverlap=args.allow_file_overlap,
                    )
                    if not eligible:
                        printJson({"eligible": False, "reason": "No eligible task", "rejected": rejected})
                        return 3
                    printJson({"eligible": True, "task": taskPayload(eligible[0], state=state, now=now)})
                    return 0
                if args.command == "shortlist":
                    priorities = {item.upper() for item in args.priority} or None
                    printJson(
                        shortlistTasks(
                            state,
                            priorities=priorities,
                            epic=args.epic,
                            component=args.component,
                            allowFileOverlap=args.allow_file_overlap,
                            seed=args.seed,
                            includeRejected=args.include_rejected,
                            controllerId=args.controller_id,
                            controllerActiveFloor=args.controller_active_floor,
                            controllerActiveLimit=args.controller_active_limit,
                        )
                    )
                    return 0
                task = requireClaim(state, args.issue, args.claim_id, args.owner)
                print(renderWorkerPrompt(task))
                return 0
            finally:
                state.workbook.close()

        if args.command == "claim":
            priorities = {item.upper() for item in args.priority} or None
            result = claimTask(
                workbookPath,
                owner=args.owner,
                issueName=args.issue,
                leaseMinutes=args.lease_minutes,
                priorities=priorities,
                epic=args.epic,
                component=args.component,
                allowFileOverlap=args.allow_file_overlap,
                lockTimeoutSeconds=args.lock_timeout_seconds,
            )
            if not result.get("claimed"):
                printJson(result)
                return 3
            if args.format == "prompt":
                state = loadQueue(workbookPath, writable=False)
                try:
                    print(renderWorkerPrompt(taskByName(state, result["Issue Name"])))
                finally:
                    state.workbook.close()
            else:
                printJson(result)
            return 0

        if args.command == "heartbeat":
            printJson(
                heartbeatTask(
                    workbookPath,
                    issueName=args.issue,
                    claimId=args.claim_id,
                    owner=args.owner,
                    progress=args.progress,
                    note=args.note,
                    leaseMinutes=args.lease_minutes,
                    lockTimeoutSeconds=args.lock_timeout_seconds,
                )
            )
            return 0

        if args.command == "complete":
            summary = readTextOption(args.summary, args.summary_file, "summary")
            validation = readTextOption(args.validation, args.validation_file, "validation")
            printJson(
                finishTask(
                    workbookPath,
                    issueName=args.issue,
                    claimId=args.claim_id,
                    owner=args.owner,
                    status=STATUS_DONE,
                    note=args.note,
                    summary=summary,
                    validation=validation,
                    lockTimeoutSeconds=args.lock_timeout_seconds,
                )
            )
            return 0

        if args.command in {"block", "fail", "cancel"}:
            summary = readTextOption(args.summary, args.summary_file, "summary")
            validation = readTextOption(args.validation, args.validation_file, "validation")
            printJson(
                finishTask(
                    workbookPath,
                    issueName=args.issue,
                    claimId=args.claim_id,
                    owner=args.owner,
                    status=args.targetStatus,
                    note=args.note,
                    summary=summary,
                    validation=validation,
                    lockTimeoutSeconds=args.lock_timeout_seconds,
                )
            )
            return 0

        if args.command == "release":
            printJson(
                releaseTask(
                    workbookPath,
                    issueName=args.issue,
                    claimId=args.claim_id,
                    owner=args.owner,
                    note=args.note,
                    lockTimeoutSeconds=args.lock_timeout_seconds,
                )
            )
            return 0

        if args.command == "reclaim-stale":
            if args.dry_run:
                state = loadQueue(workbookPath, writable=False)
                try:
                    now = utcNow()
                    stale = staleClaims(state, olderThanMinutes=args.older_than_minutes, now=now)
                    reclaimable = [record for record in stale if record["reclaimable"]]
                    printJson(
                        {
                            "workbook": str(workbookPath),
                            "olderThanMinutes": args.older_than_minutes,
                            "heartbeatIntervalMinutes": DEFAULT_HEARTBEAT_INTERVAL_MINUTES,
                            "reclaimSafety": {
                                "timingOnly": True,
                                "requiresInspection": True,
                                "message": (
                                    "Dry-run reclaimable rows satisfy queue timing only; inspect worker state and PRs "
                                    "before mutating."
                                ),
                            },
                            "staleCount": len(stale),
                            "reclaimableStaleCount": len(reclaimable),
                            "activeClaims": activeClaimSummary(
                                state,
                                stale,
                                now=now,
                                olderThanMinutes=args.older_than_minutes,
                            ),
                            "stale": markStaleClaimsForInspection(stale),
                            "reclaimable": markStaleClaimsForInspection(reclaimable),
                        }
                    )
                finally:
                    state.workbook.close()
            else:
                printJson(
                    {
                        "reclaimed": reclaimStaleTasks(
                            workbookPath,
                            olderThanMinutes=args.older_than_minutes,
                            lockTimeoutSeconds=args.lock_timeout_seconds,
                        )
                    }
                )
            return 0

        raise QueueError(f"Unsupported command {args.command}")
    except (QueueError, OSError, ValueError) as exc:
        print(f"issue_queue: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
