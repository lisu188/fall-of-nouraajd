#!/usr/bin/env python3
"""Immutable workflow-observation ledger for controller and optimizer runs."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

SCHEMA_VERSION = 1
DEFAULT_ROOT = Path("planning/workflow_observations")
RECORDS_DIR = "records"
RESOLUTIONS_DIR = "resolutions"
LEDGER_FILE_DIRS = {RECORDS_DIR, RESOLUTIONS_DIR}

CATEGORIES = {
    "queue_lease",
    "subagent_status",
    "git_worktrees",
    "prs",
    "ci",
    "resources",
    "recovery",
    "prompt_drift",
    "observability",
    "other",
}
SEVERITIES = ("critical", "high", "medium", "low")
SEVERITY_RANK = {severity: index for index, severity in enumerate(SEVERITIES)}
PHASES = {
    "startup",
    "dispatch",
    "claim",
    "implementation",
    "review",
    "validation",
    "merge",
    "completion",
    "cleanup",
    "optimizer",
    "other",
}
ROLES = {"controller", "worker", "qa", "project_manager", "optimizer", "reviewer", "other"}
RESOLUTION_STATUSES = {"resolved", "duplicate", "invalid", "wont-fix"}

ID_PATTERN = re.compile(r"^\d{8}T\d{6}Z-[a-z0-9][a-z0-9._-]{0,63}-[0-9a-f]{8}$")
TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{7,40}$")
SECRET_PATTERNS = (
    re.compile(r"gh[opsu]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_.-]{20,}"),
    re.compile(r"(?i)\b(password|secret|token|api[_-]?key)\s*="),
)
FORBIDDEN_EVIDENCE_KEYS = {"env", "environment", "env_dump", "environment_dump", "secrets", "secret", "token"}

MAX_SUMMARY_CHARS = 200
MAX_DETAILS_CHARS = 12000
MAX_IMPACT_CHARS = 4000
MAX_EVIDENCE_ENTRIES = 20
MAX_EVIDENCE_TEXT_CHARS = 8000
MAX_JSON_BYTES = 65536


class ObservationError(RuntimeError):
    """Raised for invalid ledger operations."""


@dataclass(frozen=True)
class LoadedObservation:
    path: Path
    payload: dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.payload["id"])

    @property
    def fingerprint(self) -> str:
        return str(self.payload["fingerprint"])

    @property
    def createdAtUtc(self) -> str:
        return str(self.payload["createdAtUtc"])

    @property
    def severity(self) -> str:
        return str(self.payload["severity"])


@dataclass(frozen=True)
class LoadedResolution:
    path: Path
    payload: dict[str, Any]

    @property
    def observationId(self) -> str:
        return str(self.payload["observationId"])


def utcNow() -> datetime:
    return datetime.now(timezone.utc)


def formatUtc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parseUtc(text: Any) -> datetime:
    if not isinstance(text, str) or not TIMESTAMP_PATTERN.match(text):
        raise ObservationError(f"malformed UTC timestamp: {text!r}")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ObservationError(f"malformed UTC timestamp: {text!r}") from exc


def recordsDir(root: Path) -> Path:
    return root / RECORDS_DIR


def resolutionsDir(root: Path) -> Path:
    return root / RESOLUTIONS_DIR


def sanitizeControllerId(controllerId: str) -> str:
    lowered = controllerId.strip().lower()
    sanitized = re.sub(r"[^a-z0-9._-]+", "-", lowered).strip("-._")
    return (sanitized or "unknown")[:64]


def generateObservationId(controllerId: str, now: datetime | None = None) -> str:
    timestamp = (now or utcNow()).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{sanitizeControllerId(controllerId)}-{secrets.token_hex(4)}"


def canonicalJson(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def writeJsonExclusive(path: Path, payload: dict[str, Any]) -> None:
    data = canonicalJson(payload)
    if len(data) > MAX_JSON_BYTES:
        raise ObservationError(f"{path.name}: JSON payload exceeds {MAX_JSON_BYTES} bytes")
    path.parent.mkdir(parents=True, exist_ok=True)
    tempPath = path.parent / f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp"
    try:
        fd = os.open(tempPath, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            with contextlib.suppress(OSError):
                os.close(fd)
            raise
        os.link(tempPath, path)
        if os.name != "nt":
            directoryFd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directoryFd)
            finally:
                os.close(directoryFd)
    except FileExistsError as exc:
        raise ObservationError(f"refusing to overwrite existing ledger file: {path}") from exc
    finally:
        with contextlib.suppress(FileNotFoundError):
            tempPath.unlink()


def loadJsonFile(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ObservationError(f"{path}: cannot read file: {exc}") from exc
    if not raw.endswith(b"\n"):
        raise ObservationError(f"{path}: JSON must end with one newline")
    if len(raw) > MAX_JSON_BYTES:
        raise ObservationError(f"{path}: JSON payload exceeds {MAX_JSON_BYTES} bytes")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ObservationError(f"{path}: malformed UTF-8 JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ObservationError(f"{path}: top-level JSON must be an object")
    if canonicalJson(payload) != raw:
        raise ObservationError(f"{path}: JSON is not canonical")
    return payload


def containsSecret(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


def containsUnsafeControls(value: str) -> bool:
    return any(ord(character) < 32 and character not in "\n\r\t" for character in value)


def validateStringField(name: str, value: Any, maxChars: int, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{name} must be a non-empty string")
        return
    if len(value) > maxChars:
        errors.append(f"{name} exceeds {maxChars} characters")
    if containsSecret(value):
        errors.append(f"{name} appears to contain a secret")
    if containsUnsafeControls(value):
        errors.append(f"{name} contains unsafe control characters")


def validateSourceCommit(value: Any, errors: list[str], fieldName: str = "sourceCommit") -> None:
    if not isinstance(value, str) or not COMMIT_PATTERN.match(value):
        errors.append(f"{fieldName} must be a 7-40 character lowercase hex commit")


def normalizeRepoPath(pathText: Any) -> str:
    if not isinstance(pathText, str) or not pathText.strip():
        raise ObservationError("affected paths must be non-empty strings")
    if "\\" in pathText:
        raise ObservationError(f"affected path must use forward slashes: {pathText}")
    path = PurePosixPath(pathText)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ObservationError(f"affected path must be repository-relative without traversal: {pathText}")
    return path.as_posix()


def validateAffectedPaths(value: Any, errors: list[str]) -> list[str]:
    if value is None:
        errors.append("affectedPaths is required")
        return []
    if not isinstance(value, list):
        errors.append("affectedPaths must be a list")
        return []
    if not value:
        errors.append("affectedPaths must contain at least one path")
        return []
    normalized: list[str] = []
    for item in value:
        try:
            normalized.append(normalizeRepoPath(item))
        except ObservationError as exc:
            errors.append(str(exc))
    if len(normalized) != len(set(normalized)):
        errors.append("affectedPaths must not contain duplicates")
    return normalized


def walkEvidenceStrings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for nested in value.values():
            result.extend(walkEvidenceStrings(nested))
        return result
    if isinstance(value, list):
        result = []
        for nested in value:
            result.extend(walkEvidenceStrings(nested))
        return result
    return []


def walkEvidenceKeys(value: Any) -> list[str]:
    if isinstance(value, dict):
        result: list[str] = []
        for key, nested in value.items():
            result.append(str(key).lower())
            result.extend(walkEvidenceKeys(nested))
        return result
    if isinstance(value, list):
        result = []
        for nested in value:
            result.extend(walkEvidenceKeys(nested))
        return result
    return []


def validateEvidence(value: Any, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append("evidence must be a list")
        return
    if not value:
        errors.append("evidence must contain at least one entry")
    if len(value) > MAX_EVIDENCE_ENTRIES:
        errors.append(f"evidence must not exceed {MAX_EVIDENCE_ENTRIES} entries")
    for index, entry in enumerate(value):
        if not isinstance(entry, dict) or not entry:
            errors.append(f"evidence[{index}] must be a non-empty object")
            continue
        badKeys = FORBIDDEN_EVIDENCE_KEYS.intersection(walkEvidenceKeys(entry))
        if badKeys:
            errors.append(
                f"evidence[{index}] contains forbidden environment/secret key(s): {', '.join(sorted(badKeys))}"
            )
        for text in walkEvidenceStrings(entry):
            if len(text) > MAX_EVIDENCE_TEXT_CHARS:
                errors.append(f"evidence[{index}] contains oversized text")
            if containsSecret(text):
                errors.append(f"evidence[{index}] appears to contain a secret")
            if containsUnsafeControls(text):
                errors.append(f"evidence[{index}] contains unsafe control characters")


def normalizeFingerprint(source: str) -> str:
    text = source.strip().lower()
    text = re.sub(r"\b[0-9a-f]{7,40}\b", "<hex>", text)
    text = re.sub(r"\d{4}-\d{2}-\d{2}t\d{2}:\d{2}:\d{2}z", "<time>", text)
    text = re.sub(r"\d+", "<n>", text)
    text = re.sub(r"[^a-z0-9_./:<>\-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        text = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return text[:200]


def buildFingerprint(
    category: str, phase: str, summary: str, affectedPaths: Sequence[str], explicit: str | None
) -> str:
    if explicit:
        if containsSecret(explicit):
            raise ObservationError("fingerprint appears to contain a secret")
        if containsUnsafeControls(explicit):
            raise ObservationError("fingerprint contains unsafe control characters")
        return normalizeFingerprint(explicit)
    return normalizeFingerprint("|".join([category, phase, summary, *affectedPaths]))


def validateObservationPayload(path: Path, payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    observationId = payload.get("id")
    if not isinstance(observationId, str) or not ID_PATTERN.match(observationId):
        errors.append("id is malformed")
    elif path.name != f"{observationId}.json":
        errors.append("filename must equal observation id")
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("schemaVersion must be 1")
    try:
        parseUtc(payload.get("createdAtUtc"))
    except ObservationError as exc:
        errors.append(str(exc))
    validateStringField("controllerId", payload.get("controllerId"), 128, errors)
    if payload.get("role") not in ROLES:
        errors.append(f"role must be one of {sorted(ROLES)}")
    validateSourceCommit(payload.get("sourceCommit"), errors)
    if payload.get("category") not in CATEGORIES:
        errors.append(f"category must be one of {sorted(CATEGORIES)}")
    if payload.get("severity") not in SEVERITIES:
        errors.append(f"severity must be one of {list(SEVERITIES)}")
    if payload.get("phase") not in PHASES:
        errors.append(f"phase must be one of {sorted(PHASES)}")
    validateStringField("summary", payload.get("summary"), MAX_SUMMARY_CHARS, errors)
    validateStringField("details", payload.get("details"), MAX_DETAILS_CHARS, errors)
    validateStringField("impact", payload.get("impact"), MAX_IMPACT_CHARS, errors)
    validateEvidence(payload.get("evidence"), errors)
    affectedPaths = validateAffectedPaths(payload.get("affectedPaths"), errors)
    fingerprint = payload.get("fingerprint")
    if not isinstance(fingerprint, str) or not fingerprint.strip() or len(fingerprint) > 200:
        errors.append("fingerprint must be a non-empty string up to 200 characters")
    else:
        if containsSecret(fingerprint):
            errors.append("fingerprint appears to contain a secret")
        if containsUnsafeControls(fingerprint):
            errors.append("fingerprint contains unsafe control characters")
        if fingerprint != normalizeFingerprint(fingerprint):
            errors.append("fingerprint must be normalized")
    for optionalName in ("queueIssue", "worker", "branch", "suggestedImprovement"):
        optionalValue = payload.get(optionalName)
        if optionalValue is not None and (not isinstance(optionalValue, str) or containsSecret(optionalValue)):
            errors.append(f"{optionalName} must be a string without secrets when present")
    return errors


def validateResolutionPayload(
    path: Path,
    payload: dict[str, Any],
    observations: dict[str, LoadedObservation],
) -> list[str]:
    errors: list[str] = []
    observationId = payload.get("observationId")
    if not isinstance(observationId, str) or not ID_PATTERN.match(observationId):
        errors.append("observationId is malformed")
    elif path.name != f"{observationId}.json":
        errors.append("filename must equal observation id")
    elif observationId not in observations:
        errors.append(f"orphan resolution for unknown observation {observationId}")
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("schemaVersion must be 1")
    try:
        parseUtc(payload.get("resolvedAtUtc"))
    except ObservationError as exc:
        errors.append(str(exc))
    status = payload.get("status")
    if status not in RESOLUTION_STATUSES:
        errors.append(f"status must be one of {sorted(RESOLUTION_STATUSES)}")
    validateStringField("resolver", payload.get("resolver"), 128, errors)
    validateSourceCommit(payload.get("sourceCommit"), errors)
    validateStringField("resolutionSummary", payload.get("resolutionSummary"), MAX_IMPACT_CHARS, errors)
    validateEvidence(payload.get("evidence"), errors)
    if status == "resolved":
        if not isinstance(payload.get("mergedPr"), int) or payload.get("mergedPr") <= 0:
            errors.append("resolved receipts require positive integer mergedPr")
        mergeCommit = payload.get("mergeCommit")
        if not isinstance(mergeCommit, str) or not re.match(r"^[0-9a-f]{40}$", mergeCommit):
            errors.append("resolved receipts require 40-character mergeCommit")
    else:
        if "mergedPr" in payload or "mergeCommit" in payload:
            errors.append("mergedPr and mergeCommit are only valid for resolved receipts")
    if status == "duplicate":
        canonicalId = payload.get("canonicalObservationId")
        if not isinstance(canonicalId, str) or not ID_PATTERN.match(canonicalId):
            errors.append("duplicate receipts require canonicalObservationId")
        elif canonicalId == observationId:
            errors.append("duplicate receipt cannot point to itself")
        elif canonicalId not in observations:
            errors.append(f"duplicate canonical observation does not exist: {canonicalId}")
    elif "canonicalObservationId" in payload:
        errors.append("canonicalObservationId is only valid for duplicate receipts")
    return errors


def readLedger(root: Path) -> tuple[dict[str, LoadedObservation], dict[str, LoadedResolution], list[str]]:
    errors: list[str] = []
    observations: dict[str, LoadedObservation] = {}
    resolutions: dict[str, LoadedResolution] = {}

    recordDir = recordsDir(root)
    if recordDir.exists() and not recordDir.is_dir():
        errors.append(f"{recordDir}: records path is not a directory")
    elif recordDir.exists():
        for path in sorted(recordDir.iterdir()):
            if not path.is_file():
                errors.append(f"{path}: ledger entries must be files")
            elif path.suffix != ".json":
                errors.append(f"{path}: ledger files must use .json extension")
        for path in sorted(recordDir.glob("*.json")):
            try:
                payload = loadJsonFile(path)
                payloadErrors = validateObservationPayload(path, payload)
                errors.extend(f"{path}: {error}" for error in payloadErrors)
                if isinstance(payload.get("id"), str):
                    if payload["id"] in observations:
                        errors.append(f"{path}: duplicate observation id {payload['id']}")
                    observations[payload["id"]] = LoadedObservation(path, payload)
            except ObservationError as exc:
                errors.append(str(exc))

    resolutionDir = resolutionsDir(root)
    if resolutionDir.exists() and not resolutionDir.is_dir():
        errors.append(f"{resolutionDir}: resolutions path is not a directory")
    elif resolutionDir.exists():
        for path in sorted(resolutionDir.iterdir()):
            if not path.is_file():
                errors.append(f"{path}: ledger entries must be files")
            elif path.suffix != ".json":
                errors.append(f"{path}: ledger files must use .json extension")
        for path in sorted(resolutionDir.glob("*.json")):
            try:
                payload = loadJsonFile(path)
                payloadErrors = validateResolutionPayload(path, payload, observations)
                errors.extend(f"{path}: {error}" for error in payloadErrors)
                if isinstance(payload.get("observationId"), str):
                    if payload["observationId"] in resolutions:
                        errors.append(f"{path}: multiple receipts for {payload['observationId']}")
                    resolutions[payload["observationId"]] = LoadedResolution(path, payload)
            except ObservationError as exc:
                errors.append(str(exc))

    errors.extend(validateDuplicateCycles(resolutions))
    return observations, resolutions, errors


def gitPathForRoot(root: Path) -> str:
    if root.is_absolute():
        try:
            return root.resolve().relative_to(Path.cwd().resolve()).as_posix()
        except ValueError:
            return root.as_posix()
    return PurePosixPath(str(root)).as_posix()


def validatePrChanges(root: Path, baseRef: str) -> list[str]:
    if not baseRef or not baseRef.strip():
        return ["--base must be a non-empty git ref"]

    rootPath = gitPathForRoot(root)
    try:
        result = subprocess.run(
            ["git", "diff", "--name-status", "--no-renames", baseRef],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise ObservationError("git executable not found on PATH; cannot inspect ledger diff") from exc
    except OSError as exc:
        raise ObservationError(f"could not execute git diff for ledger inspection: {exc}") from exc
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown git diff failure"
        raise ObservationError(f"could not inspect ledger diff from {baseRef}: {message}")

    errors: list[str] = []
    rootParts = tuple(PurePosixPath(rootPath).parts)
    ledgerChanges: list[tuple[str, str]] = []
    nonLedgerChanges: list[str] = []
    for line in result.stdout.splitlines():
        columns = line.split("\t")
        if len(columns) < 2:
            errors.append(f"malformed git diff entry: {line}")
            continue
        status = columns[0]
        changedPath = columns[-1]
        path = PurePosixPath(changedPath)
        parts = path.parts
        if rootParts and parts[: len(rootParts)] != rootParts:
            nonLedgerChanges.append(changedPath)
            continue
        ledgerChanges.append((status, changedPath))

    if not ledgerChanges:
        return errors

    for changedPath in nonLedgerChanges:
        errors.append(f"{changedPath}: ledger PR changes must not be mixed with non-ledger changes")

    for status, changedPath in ledgerChanges:
        path = PurePosixPath(changedPath)
        parts = path.parts
        relativeParts = parts[len(rootParts) :]
        if len(relativeParts) != 2 or relativeParts[0] not in LEDGER_FILE_DIRS:
            errors.append(
                f"{changedPath}: ledger PR changes must add only {RECORDS_DIR}/<id>.json or "
                f"{RESOLUTIONS_DIR}/<id>.json files"
            )
        if path.suffix != ".json":
            errors.append(f"{changedPath}: ledger PR changes must be JSON files")
        if status != "A":
            errors.append(f"{changedPath}: immutable ledger files may only be added in PRs, got {status}")
    return errors


def validateDuplicateCycles(resolutions: dict[str, LoadedResolution]) -> list[str]:
    graph = {
        observationId: str(resolution.payload.get("canonicalObservationId"))
        for observationId, resolution in resolutions.items()
        if resolution.payload.get("status") == "duplicate"
    }
    errors: list[str] = []
    for start in sorted(graph):
        seen: set[str] = set()
        current = start
        while current in graph:
            if current in seen:
                errors.append(f"duplicate cycle involving {start}")
                break
            seen.add(current)
            current = graph[current]
    return errors


def currentCommit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError as exc:
        raise ObservationError("could not determine source commit; pass --source-commit") from exc
    text = result.stdout.strip().lower()
    if result.returncode == 0 and COMMIT_PATTERN.match(text):
        return text
    raise ObservationError("could not determine source commit; pass --source-commit")


def loadText(value: str | None, filePath: str | None, fieldName: str) -> str:
    if value and filePath:
        raise ObservationError(f"use either --{fieldName} or --{fieldName}-file, not both")
    if filePath:
        return Path(filePath).read_text(encoding="utf-8")
    if value is None:
        raise ObservationError(f"--{fieldName} is required")
    return value


def loadEvidence(jsonText: str | None, filePath: str | None) -> list[dict[str, Any]]:
    if jsonText and filePath:
        raise ObservationError("use either --evidence-json or --evidence-file, not both")
    if filePath:
        raw = Path(filePath).read_text(encoding="utf-8")
    elif jsonText:
        raw = jsonText
    else:
        return []
    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        raise ObservationError("evidence JSON must be an object or list")
    return parsed


def buildObservation(args: argparse.Namespace) -> dict[str, Any]:
    affectedPaths = sorted({normalizeRepoPath(path) for path in args.affected_path})
    sourceCommit = args.source_commit or currentCommit()
    createdAt = formatUtc(utcNow())
    fingerprint = buildFingerprint(args.category, args.phase, args.summary, affectedPaths, args.fingerprint)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "id": generateObservationId(args.controller_id),
        "createdAtUtc": createdAt,
        "controllerId": args.controller_id,
        "role": args.role,
        "sourceCommit": sourceCommit,
        "category": args.category,
        "severity": args.severity,
        "phase": args.phase,
        "summary": args.summary,
        "details": loadText(args.details, args.details_file, "details"),
        "impact": args.impact,
        "evidence": loadEvidence(args.evidence_json, args.evidence_file),
        "affectedPaths": affectedPaths,
        "fingerprint": fingerprint,
        **optionalString("queueIssue", args.queue_issue),
        **optionalString("worker", args.worker),
        **optionalString("branch", args.branch),
        **optionalString("suggestedImprovement", args.suggested_improvement),
    }


def optionalString(name: str, value: str | None) -> dict[str, str]:
    return {name: value} if value else {}


def buildResolution(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "observationId": args.id,
        "resolvedAtUtc": formatUtc(utcNow()),
        "status": args.status,
        "resolver": args.resolver,
        "sourceCommit": args.source_commit or currentCommit(),
        "resolutionSummary": loadText(args.summary, args.summary_file, "summary"),
        "evidence": loadEvidence(args.evidence_json, args.evidence_file),
    }
    if args.status == "resolved":
        payload["mergedPr"] = args.merged_pr
        payload["mergeCommit"] = args.merge_commit
    if args.status == "duplicate":
        payload["canonicalObservationId"] = args.canonical_id
    return payload


def recordObservation(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root)
    for attempt in range(5):
        payload = buildObservation(args)
        errors = validateObservationPayload(recordsDir(root) / f"{payload['id']}.json", payload)
        if errors:
            raise ObservationError("; ".join(errors))
        try:
            writeJsonExclusive(recordsDir(root) / f"{payload['id']}.json", payload)
            return payload
        except ObservationError:
            if attempt == 4:
                raise
    raise ObservationError("could not create a unique observation id")


def resolveObservation(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root)
    observations, resolutions, errors = readLedger(root)
    if errors:
        raise ObservationError("ledger is invalid: " + "; ".join(errors))
    if args.id not in observations:
        raise ObservationError(f"unknown observation: {args.id}")
    if args.id in resolutions:
        raise ObservationError(f"observation already has a receipt: {args.id}")
    payload = buildResolution(args)
    errors = validateResolutionPayload(resolutionsDir(root) / f"{args.id}.json", payload, observations)
    pendingResolutions = {**resolutions, args.id: LoadedResolution(resolutionsDir(root) / f"{args.id}.json", payload)}
    errors.extend(validateDuplicateCycles(pendingResolutions))
    if errors:
        raise ObservationError("; ".join(errors))
    writeJsonExclusive(resolutionsDir(root) / f"{args.id}.json", payload)
    return payload


def observationState(observationId: str, resolutions: dict[str, LoadedResolution]) -> str:
    return "resolved" if observationId in resolutions else "open"


def listPayload(root: Path, stateFilter: str) -> dict[str, Any]:
    observations, resolutions, errors = readLedger(root)
    if errors:
        raise ObservationError("ledger is invalid: " + "; ".join(errors))
    items: list[dict[str, Any]] = []
    for observation in sorted(observations.values(), key=lambda item: (item.createdAtUtc, item.id)):
        state = observationState(observation.id, resolutions)
        if stateFilter != "all" and state != stateFilter:
            continue
        item = {
            "id": observation.id,
            "state": state,
            "createdAtUtc": observation.createdAtUtc,
            "severity": observation.severity,
            "category": observation.payload["category"],
            "phase": observation.payload["phase"],
            "fingerprint": observation.fingerprint,
            "summary": observation.payload["summary"],
        }
        if observation.id in resolutions:
            item["resolutionStatus"] = resolutions[observation.id].payload["status"]
        items.append(item)
    return {"root": str(root), "state": stateFilter, "observations": items}


def showPayload(root: Path, observationId: str) -> dict[str, Any]:
    observations, resolutions, errors = readLedger(root)
    if errors:
        raise ObservationError("ledger is invalid: " + "; ".join(errors))
    if observationId not in observations:
        raise ObservationError(f"unknown observation: {observationId}")
    return {
        "observation": observations[observationId].payload,
        "resolution": resolutions.get(observationId).payload if observationId in resolutions else None,
    }


def nextPayload(root: Path) -> dict[str, Any]:
    observations, resolutions, errors = readLedger(root)
    if errors:
        raise ObservationError("ledger is invalid: " + "; ".join(errors))
    openObservations = [item for item in observations.values() if item.id not in resolutions]
    groups: dict[str, list[LoadedObservation]] = defaultdict(list)
    for observation in openObservations:
        groups[observation.fingerprint].append(observation)
    candidates: list[dict[str, Any]] = []
    for fingerprint, group in groups.items():
        group = sorted(group, key=lambda item: (item.createdAtUtc, item.id))
        severity = min((item.severity for item in group), key=lambda value: SEVERITY_RANK[value])
        candidate = {
            "fingerprint": fingerprint,
            "severity": severity,
            "severityRank": SEVERITY_RANK[severity],
            "recurrenceCount": len(group),
            "oldestOccurrence": group[0].createdAtUtc,
            "ids": [item.id for item in group],
            "summary": group[0].payload["summary"],
            "ranking": (
                f"severity={severity}, recurrence={len(group)}, oldest={group[0].createdAtUtc}, "
                f"tieBreak={fingerprint}"
            ),
        }
        candidates.append(candidate)
    candidates.sort(
        key=lambda item: (item["severityRank"], -item["recurrenceCount"], item["oldestOccurrence"], item["fingerprint"])
    )
    return {"next": candidates[0] if candidates else None, "candidates": candidates}


def validatePayload(root: Path, baseRef: str | None = None) -> tuple[dict[str, Any], list[str]]:
    observations, resolutions, errors = readLedger(root)
    openCount = sum(1 for observationId in observations if observationId not in resolutions)
    statusCounts = Counter(
        status
        for status in (resolution.payload.get("status") for resolution in resolutions.values())
        if isinstance(status, str) and status in RESOLUTION_STATUSES
    )
    if baseRef is not None:
        errors.extend(validatePrChanges(root, baseRef))
    payload: dict[str, Any] = {
        "root": str(root),
        "records": len(observations),
        "resolutions": len(resolutions),
        "open": openCount,
        "resolutionStatusCounts": dict(sorted(statusCounts.items())),
        "errors": errors,
    }
    if baseRef is not None:
        payload["base"] = baseRef
    return payload, errors


def printJson(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def addCommonRoot(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="ledger root directory")


def parseArgs(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    record = subparsers.add_parser("record", help="create an immutable observation record")
    addCommonRoot(record)
    record.add_argument("--controller-id", required=True)
    record.add_argument("--role", required=True, choices=sorted(ROLES))
    record.add_argument("--source-commit")
    record.add_argument("--category", required=True, choices=sorted(CATEGORIES))
    record.add_argument("--severity", required=True, choices=list(SEVERITIES))
    record.add_argument("--phase", required=True, choices=sorted(PHASES))
    record.add_argument("--summary", required=True)
    record.add_argument("--details")
    record.add_argument("--details-file")
    record.add_argument("--impact", required=True)
    record.add_argument("--evidence-json")
    record.add_argument("--evidence-file")
    record.add_argument("--affected-path", action="append", default=[], required=True)
    record.add_argument("--fingerprint")
    record.add_argument("--queue-issue")
    record.add_argument("--worker")
    record.add_argument("--branch")
    record.add_argument("--suggested-improvement")

    validate = subparsers.add_parser("validate", help="validate the ledger")
    addCommonRoot(validate)
    validate.add_argument(
        "--base",
        help="reject PR diffs that mix ledger and non-ledger changes or modify/delete existing ledger files",
    )

    listCommand = subparsers.add_parser("list", help="list observations")
    addCommonRoot(listCommand)
    listCommand.add_argument("--state", choices=("open", "resolved", "all"), default="open")

    show = subparsers.add_parser("show", help="show an observation and optional receipt")
    addCommonRoot(show)
    show.add_argument("--id", required=True)

    nextCommand = subparsers.add_parser("next", help="rank open observations")
    addCommonRoot(nextCommand)

    resolve = subparsers.add_parser("resolve", help="create an immutable resolution receipt")
    addCommonRoot(resolve)
    resolve.add_argument("--id", required=True)
    resolve.add_argument("--status", required=True, choices=sorted(RESOLUTION_STATUSES))
    resolve.add_argument("--resolver", required=True)
    resolve.add_argument("--source-commit")
    resolve.add_argument("--summary")
    resolve.add_argument("--summary-file")
    resolve.add_argument("--evidence-json")
    resolve.add_argument("--evidence-file")
    resolve.add_argument("--merged-pr", type=int)
    resolve.add_argument("--merge-commit")
    resolve.add_argument("--canonical-id")

    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parseArgs(argv or sys.argv[1:])
    try:
        if args.command == "record":
            printJson({"record": recordObservation(args)})
        elif args.command == "validate":
            payload, errors = validatePayload(Path(args.root), args.base)
            printJson(payload)
            return 1 if errors else 0
        elif args.command == "list":
            printJson(listPayload(Path(args.root), args.state))
        elif args.command == "show":
            printJson(showPayload(Path(args.root), args.id))
        elif args.command == "next":
            printJson(nextPayload(Path(args.root)))
        elif args.command == "resolve":
            printJson({"resolution": resolveObservation(args)})
        else:  # pragma: no cover - argparse prevents this
            raise ObservationError(f"unknown command {args.command}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, ObservationError) as exc:
        print(f"workflow_observations: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
