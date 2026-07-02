#!/usr/bin/env python3
"""Versioned structured worker reports and deterministic bounded restart handoffs.

Worker milestone and end-of-task reports used to be free-form text, so a
controller restart or handoff could lose claim linkage, the exact validation
commands, the CI head SHA the evidence applies to, changed files, blockers, and
risks. This module defines one normalized report model:

- ``schemaVersion``: the report schema version (currently 1);
- worker identity: ``owner`` in the ``controller/<controller-id>/<agent>``
    form, the exact ``claimId``, and optional ``controllerId``,
    ``registrationId``, ``role``, and ``phase`` (role/phase reuse the
    ``scripts/subagent_registry.py`` enums);
- the ``issue`` name, implementation ``branch``, and ``filesChanged``;
- ``commands`` whose per-command ``status`` is exactly one of ``passed``,
    ``failed``, ``skipped``, ``blocked``, or ``not_run``; ``passed`` and
    ``failed`` entries carry an ``exitCode`` and any ``outputSummary`` is
    bounded to ``MAX_OUTPUT_SUMMARY_CHARS`` characters;
- ``ciHeadSha``: the plausible git SHA (7-40 lowercase hex characters) the
    validation evidence applies to;
- an ``outcome`` status: ``IN_PROGRESS``, ``COMPLETE``, ``BLOCKED``, or
    ``FAILED`` (``COMPLETE`` requires at least one passed command and forbids
    failed commands).

Reports are worker assertions, not verified queue evidence. Nothing in this
module reads or mutates the XLSX workbook, and a report never advances queue
state; queue mutations still flow through ``scripts/issue_queue.py``.

``validate`` checks the schema, cross-checks internal identity consistency
(``controllerId`` must equal the owner's controller segment), rejects
mismatched ``--expect-owner``/``--expect-claim-id``/``--expect-issue``/
``--expect-branch`` evidence, and rejects a stale ``ciHeadSha`` that does not
match ``--expect-ci-sha`` or the current branch head resolved read-only from
``--repo``. ``render`` emits human Markdown or canonical JSON from the same
normalized model. ``handoff`` builds a deterministic, bounded restart handoff:
its content derives only from the source report (wall-clock time never affects
content or ordering, and the report fingerprint excludes ``createdAtUtc``), and
every carried section is capped at ``HANDOFF_MAX_ITEMS_PER_SECTION`` items
(default 10, CLI-adjustable up to ``HANDOFF_MAX_ITEMS_LIMIT``) with explicit
omitted counts. ``registry-payload`` converts an accepted report into a
``scripts/subagent_registry.py report`` payload so registry ``lastSeen`` only
advances from schema-valid worker evidence.

Exit codes: 0 success, 1 validation errors, 2 usage/input errors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

try:
    from scripts import subagent_registry, workflow_observations
except ModuleNotFoundError:  # Support `python3 scripts/worker_report.py`.
    import subagent_registry
    import workflow_observations

SCHEMA_VERSION = 1
COMMAND_STATUSES = ("passed", "failed", "skipped", "blocked", "not_run")
OUTCOMES = ("IN_PROGRESS", "COMPLETE", "BLOCKED", "FAILED")
OWNER_PATTERN = re.compile(r"^controller/([A-Za-z0-9][A-Za-z0-9._-]*)/([A-Za-z0-9][A-Za-z0-9._-]*)$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{7,40}$")
FULL_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
MIN_SHA_MATCH_CHARS = 7

MAX_CLAIM_ID_CHARS = 128
MAX_ISSUE_CHARS = 300
MAX_BRANCH_CHARS = 200
MAX_COMMAND_CHARS = 500
MAX_TEXT_CHARS = 500
MAX_OUTPUT_SUMMARY_CHARS = 2000
MAX_LIST_ENTRIES = 100

# Restart handoffs are bounded: each carried section keeps at most this many
# items by default; the CLI may raise the cap up to HANDOFF_MAX_ITEMS_LIMIT.
HANDOFF_MAX_ITEMS_PER_SECTION = 10
HANDOFF_MAX_ITEMS_LIMIT = 50

REQUIRED_KEYS = (
    "schemaVersion",
    "owner",
    "claimId",
    "issue",
    "branch",
    "outcome",
    "ciHeadSha",
    "filesChanged",
    "commands",
)
OPTIONAL_KEYS = (
    "controllerId",
    "registrationId",
    "role",
    "phase",
    "createdAtUtc",
    "blockers",
    "risks",
    "nextAction",
    "observationRefs",
)
ALLOWED_KEYS = frozenset(REQUIRED_KEYS + OPTIONAL_KEYS)
COMMAND_REQUIRED_KEYS = ("command", "status")
COMMAND_OPTIONAL_KEYS = ("exitCode", "outputSummary")
COMMAND_ALLOWED_KEYS = frozenset(COMMAND_REQUIRED_KEYS + COMMAND_OPTIONAL_KEYS)

SAFE_NEXT_ACTION_BY_OUTCOME = {
    "IN_PROGRESS": "Resume from the last accepted phase evidence and rerun the pending validation before new edits.",
    "COMPLETE": "Verify the implementation PR and CI state for the recorded ciHeadSha, then publish terminal queue status.",
    "BLOCKED": "Reconcile the recorded blockers with the controller before resuming implementation.",
    "FAILED": "Re-verify the root cause and the failing validation commands before retrying the implementation.",
}


class WorkerReportError(RuntimeError):
    """Raised for invalid worker-report operations or invalid report content."""


def enumText(values: Sequence[str]) -> str:
    return ", ".join(sorted(values))


def isPlainString(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validateRepoRelativePath(value: Any, label: str, errors: list[str]) -> None:
    if not isPlainString(value):
        errors.append(f"{label}: must be a non-empty string")
        return
    if "\\" in value:
        errors.append(f"{label}: must use forward slashes: {value!r}")
        return
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        errors.append(f"{label}: must be repository-relative: {value!r}")
        return
    if any(part in ("", ".", "..") for part in value.rstrip("/").split("/")):
        errors.append(f"{label}: must not contain empty, '.', or '..' segments: {value!r}")


def validateStringList(payload: dict[str, Any], name: str, maxChars: int, errors: list[str]) -> None:
    values = payload[name]
    if not isinstance(values, list):
        errors.append(f"{name}: must be a list")
        return
    if len(values) > MAX_LIST_ENTRIES:
        errors.append(f"{name}: must not exceed {MAX_LIST_ENTRIES} entries")
    for index, value in enumerate(values):
        if not isPlainString(value):
            errors.append(f"{name}[{index}]: must be a non-empty string")
        elif len(value) > maxChars:
            errors.append(f"{name}[{index}]: exceeds {maxChars} characters")


def validateCommandEntry(entry: Any, index: int) -> list[str]:
    prefix = f"commands[{index}]"
    if not isinstance(entry, dict):
        return [f"{prefix}: expected an object, got {type(entry).__name__}"]
    errors = [f"{prefix}: missing required key {key!r}" for key in COMMAND_REQUIRED_KEYS if key not in entry]
    errors += [f"{prefix}: unknown key {key!r}" for key in sorted(set(entry) - COMMAND_ALLOWED_KEYS)]
    if errors:
        return errors
    if not isPlainString(entry["command"]):
        errors.append(f"{prefix}: command must be a non-empty string")
    elif len(entry["command"]) > MAX_COMMAND_CHARS:
        errors.append(f"{prefix}: command exceeds {MAX_COMMAND_CHARS} characters")
    status = entry["status"]
    if status not in COMMAND_STATUSES:
        errors.append(f"{prefix}: status {status!r} is not one of {enumText(COMMAND_STATUSES)}")
        return errors
    has_exit_code = "exitCode" in entry
    if status in ("passed", "failed"):
        exit_code = entry.get("exitCode")
        if not has_exit_code or isinstance(exit_code, bool) or not isinstance(exit_code, int):
            errors.append(f"{prefix}: status {status!r} requires an integer exitCode")
        elif status == "passed" and exit_code != 0:
            errors.append(f"{prefix}: a passed command must record exitCode 0, got {exit_code}")
    elif has_exit_code:
        errors.append(f"{prefix}: status {status!r} must not carry an exitCode")
    if "outputSummary" in entry:
        summary = entry["outputSummary"]
        if not isinstance(summary, str):
            errors.append(f"{prefix}: outputSummary must be a string")
        elif len(summary) > MAX_OUTPUT_SUMMARY_CHARS:
            errors.append(f"{prefix}: outputSummary exceeds {MAX_OUTPUT_SUMMARY_CHARS} characters")
    return errors


def validateReportPayload(payload: Any) -> list[str]:
    """Validate a schema-version-1 worker report; returns a list of error strings."""

    if not isinstance(payload, dict):
        return [f"report: expected an object, got {type(payload).__name__}"]
    errors = [f"report: missing required key {key!r}" for key in REQUIRED_KEYS if key not in payload]
    errors += [f"report: unknown key {key!r}" for key in sorted(set(payload) - ALLOWED_KEYS)]
    if errors:
        return errors
    if payload["schemaVersion"] != SCHEMA_VERSION:
        errors.append(f"schemaVersion: expected {SCHEMA_VERSION}, got {payload['schemaVersion']!r}")
    owner_match = OWNER_PATTERN.match(payload["owner"]) if isinstance(payload["owner"], str) else None
    if owner_match is None:
        errors.append(f"owner: must match controller/<controller-id>/<agent>, got {payload['owner']!r}")
    if not isPlainString(payload["claimId"]) or len(payload["claimId"]) > MAX_CLAIM_ID_CHARS:
        errors.append(f"claimId: must be a non-empty string of at most {MAX_CLAIM_ID_CHARS} characters")
    if not isPlainString(payload["issue"]) or len(payload["issue"]) > MAX_ISSUE_CHARS:
        errors.append(f"issue: must be a non-empty string of at most {MAX_ISSUE_CHARS} characters")
    branch = payload["branch"]
    if not isPlainString(branch) or len(branch) > MAX_BRANCH_CHARS or re.search(r"\s", branch):
        errors.append(f"branch: must be a non-empty whitespace-free string of at most {MAX_BRANCH_CHARS} characters")
    if payload["outcome"] not in OUTCOMES:
        errors.append(f"outcome: {payload['outcome']!r} is not one of {enumText(OUTCOMES)}")
    if not isinstance(payload["ciHeadSha"], str) or not SHA_PATTERN.match(payload["ciHeadSha"]):
        errors.append(
            f"ciHeadSha: must be a plausible 7-40 character lowercase hex git SHA, got {payload['ciHeadSha']!r}"
        )

    files = payload["filesChanged"]
    if not isinstance(files, list):
        errors.append("filesChanged: must be a list")
    else:
        if len(files) > MAX_LIST_ENTRIES:
            errors.append(f"filesChanged: must not exceed {MAX_LIST_ENTRIES} entries")
        for index, value in enumerate(files):
            validateRepoRelativePath(value, f"filesChanged[{index}]", errors)
        if len(files) != len(set(files) if all(isinstance(f, str) for f in files) else files):
            errors.append("filesChanged: must not contain duplicates")

    commands = payload["commands"]
    if not isinstance(commands, list):
        errors.append("commands: must be a list")
    else:
        if len(commands) > MAX_LIST_ENTRIES:
            errors.append(f"commands: must not exceed {MAX_LIST_ENTRIES} entries")
        for index, entry in enumerate(commands):
            errors.extend(validateCommandEntry(entry, index))
        statuses = [entry.get("status") for entry in commands if isinstance(entry, dict)]
        if payload["outcome"] == "COMPLETE":
            if "passed" not in statuses:
                errors.append("outcome: COMPLETE requires at least one command with status 'passed'")
            if "failed" in statuses:
                errors.append("outcome: COMPLETE must not carry commands with status 'failed'")

    if "controllerId" in payload:
        if not isPlainString(payload["controllerId"]):
            errors.append("controllerId: must be a non-empty string")
        elif owner_match is not None and payload["controllerId"] != owner_match.group(1):
            errors.append(
                f"controllerId: {payload['controllerId']!r} does not match the owner controller segment "
                f"{owner_match.group(1)!r}"
            )
    if "registrationId" in payload and not isPlainString(payload["registrationId"]):
        errors.append("registrationId: must be a non-empty string")
    if "role" in payload and payload["role"] not in subagent_registry.enumValues(subagent_registry.AgentRole):
        errors.append(
            f"role: {payload['role']!r} is not one of "
            f"{enumText(subagent_registry.enumValues(subagent_registry.AgentRole))}"
        )
    if "phase" in payload and payload["phase"] not in subagent_registry.enumValues(subagent_registry.AgentPhase):
        errors.append(
            f"phase: {payload['phase']!r} is not one of "
            f"{enumText(subagent_registry.enumValues(subagent_registry.AgentPhase))}"
        )
    if "createdAtUtc" in payload and subagent_registry.parseUtc(payload["createdAtUtc"]) is None:
        errors.append(f"createdAtUtc: {payload['createdAtUtc']!r} is not a valid UTC timestamp")
    for name in ("blockers", "risks"):
        if name in payload:
            validateStringList(payload, name, MAX_TEXT_CHARS, errors)
    if "nextAction" in payload and (
        not isPlainString(payload["nextAction"]) or len(payload["nextAction"]) > MAX_TEXT_CHARS
    ):
        errors.append(f"nextAction: must be a non-empty string of at most {MAX_TEXT_CHARS} characters")
    if "observationRefs" in payload:
        refs = payload["observationRefs"]
        if not isinstance(refs, list):
            errors.append("observationRefs: must be a list")
        else:
            for index, ref in enumerate(refs):
                if not isinstance(ref, str) or not workflow_observations.ID_PATTERN.match(ref):
                    errors.append(f"observationRefs[{index}]: {ref!r} is not a valid workflow-observation id")
            if len(refs) != len(set(ref for ref in refs if isinstance(ref, str))):
                errors.append("observationRefs: must not contain duplicates")
    return errors


def identityErrors(
    payload: dict[str, Any],
    expectedOwner: str | None = None,
    expectedClaimId: str | None = None,
    expectedIssue: str | None = None,
    expectedBranch: str | None = None,
) -> list[str]:
    """Cross-check report identity against durable controller-side evidence."""

    errors: list[str] = []
    checks = (
        ("owner", expectedOwner),
        ("claimId", expectedClaimId),
        ("issue", expectedIssue),
        ("branch", expectedBranch),
    )
    for name, expected in checks:
        if expected is not None and payload.get(name) != expected:
            errors.append(
                f"identity mismatch: report {name} {payload.get(name)!r} does not match expected {expected!r}"
            )
    return errors


def shaMatches(first: str, second: str) -> bool:
    """Abbreviation-tolerant SHA comparison: the shorter must be a >=7-char prefix of the longer."""

    shorter, longer = sorted((first.lower(), second.lower()), key=len)
    return len(shorter) >= MIN_SHA_MATCH_CHARS and longer.startswith(shorter)


def ciShaErrors(payload: dict[str, Any], evidenceSha: str, evidenceLabel: str) -> list[str]:
    evidence = str(evidenceSha or "").strip().lower()
    if not SHA_PATTERN.match(evidence):
        return [f"ciHeadSha evidence from {evidenceLabel} is not a plausible git SHA: {evidenceSha!r}"]
    report_sha = str(payload.get("ciHeadSha") or "")
    if not shaMatches(report_sha, evidence):
        return [f"stale ciHeadSha: report {report_sha!r} does not match {evidenceLabel} {evidence!r}"]
    return []


def resolveBranchHead(repoRoot: Path, branch: str) -> str | None:
    """Read-only resolution of the current branch head via git rev-parse --verify."""

    result = subprocess.run(
        ["git", "-C", str(repoRoot), "rev-parse", "--verify", "--quiet", branch],
        capture_output=True,
        text=True,
        check=False,
    )
    head = result.stdout.strip().lower()
    if result.returncode == 0 and FULL_SHA_PATTERN.match(head):
        return head
    return None


def canonicalJson(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def normalizeReport(payload: dict[str, Any]) -> dict[str, Any]:
    """One normalized model behind JSON and Markdown output.

    Order-insensitive sets (filesChanged, observationRefs) are sorted; commands,
    blockers, and risks keep their authored, meaningful order.
    """

    normalized = json.loads(json.dumps(payload))
    normalized["filesChanged"] = sorted(normalized["filesChanged"])
    if "observationRefs" in normalized:
        normalized["observationRefs"] = sorted(normalized["observationRefs"])
    return normalized


def reportFingerprint(payload: dict[str, Any]) -> str:
    """Deterministic content fingerprint; ``createdAtUtc`` is excluded on purpose."""

    normalized = normalizeReport(payload)
    normalized.pop("createdAtUtc", None)
    return hashlib.sha256(canonicalJson(normalized).encode("utf-8")).hexdigest()


def requireValidReport(payload: Any, action: str) -> dict[str, Any]:
    errors = validateReportPayload(payload)
    if errors:
        raise WorkerReportError(f"Refusing to {action} from an invalid report: " + "; ".join(errors))
    return normalizeReport(payload)


def buildHandoff(payload: dict[str, Any], maxItems: int = HANDOFF_MAX_ITEMS_PER_SECTION) -> dict[str, Any]:
    """Deterministic bounded restart handoff derived only from the report content."""

    if not isinstance(maxItems, int) or isinstance(maxItems, bool) or not 1 <= maxItems <= HANDOFF_MAX_ITEMS_LIMIT:
        raise WorkerReportError(
            f"maxItems must be an integer between 1 and {HANDOFF_MAX_ITEMS_LIMIT}, got {maxItems!r}"
        )
    normalized = requireValidReport(payload, "build a handoff")

    def capped(items: list[Any]) -> tuple[list[Any], int]:
        return items[:maxItems], max(0, len(items) - maxItems)

    commands = normalized["commands"]
    pending = [entry for entry in commands if entry["status"] != "passed"]
    accepted = [
        {"command": entry["command"], "exitCode": entry["exitCode"]}
        for entry in commands
        if entry["status"] == "passed"
    ]
    files_kept, files_omitted = capped(normalized["filesChanged"])
    pending_kept, pending_omitted = capped(pending)
    accepted_kept, accepted_omitted = capped(accepted)
    blockers_kept, blockers_omitted = capped(normalized.get("blockers", []))
    risks_kept, risks_omitted = capped(normalized.get("risks", []))
    refs_kept, refs_omitted = capped(normalized.get("observationRefs", []))

    source = {name: normalized[name] for name in ("owner", "claimId", "issue", "branch", "outcome", "ciHeadSha")}
    for name in ("controllerId", "registrationId", "role", "phase"):
        if name in normalized:
            source[name] = normalized[name]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "restart-handoff",
        "maxItemsPerSection": maxItems,
        "reportFingerprint": reportFingerprint(normalized),
        "source": source,
        "commandStatusCounts": {
            status: sum(1 for entry in commands if entry["status"] == status) for status in COMMAND_STATUSES
        },
        "filesChanged": files_kept,
        "filesChangedOmitted": files_omitted,
        "pendingValidation": pending_kept,
        "pendingValidationOmitted": pending_omitted,
        "acceptedEvidence": accepted_kept,
        "acceptedEvidenceOmitted": accepted_omitted,
        "blockers": blockers_kept,
        "blockersOmitted": blockers_omitted,
        "risks": risks_kept,
        "risksOmitted": risks_omitted,
        "observationRefs": refs_kept,
        "observationRefsOmitted": refs_omitted,
        "safeNextAction": normalized.get("nextAction") or SAFE_NEXT_ACTION_BY_OUTCOME[normalized["outcome"]],
    }


def commandLine(entry: dict[str, Any]) -> str:
    text = f"- [{entry['status']}] `{entry['command']}`"
    if "exitCode" in entry:
        text += f" (exit {entry['exitCode']})"
    if entry.get("outputSummary"):
        text += f" - {entry['outputSummary']}"
    return text


def bulletSection(title: str, items: list[str], omitted: int = 0) -> list[str]:
    lines = ["", f"## {title} ({len(items)} kept, {omitted} omitted)" if omitted else f"## {title} ({len(items)})"]
    lines.extend(f"- {item}" for item in items)
    if not items:
        lines.append("- none")
    return lines


def renderReportMarkdown(payload: dict[str, Any]) -> str:
    """Human Markdown rendering of the same normalized model as the canonical JSON."""

    normalized = requireValidReport(payload, "render Markdown")
    lines = [f"# Worker report: {normalized['issue']}", ""]
    lines.append(f"- Owner: `{normalized['owner']}`")
    lines.append(f"- Claim ID: `{normalized['claimId']}`")
    for name, label in (
        ("controllerId", "Controller ID"),
        ("registrationId", "Registration ID"),
        ("role", "Role"),
        ("phase", "Phase"),
    ):
        if name in normalized:
            lines.append(f"- {label}: `{normalized[name]}`")
    lines.append(f"- Branch: `{normalized['branch']}`")
    lines.append(f"- Outcome: {normalized['outcome']}")
    lines.append(f"- CI head SHA: `{normalized['ciHeadSha']}`")
    if "createdAtUtc" in normalized:
        lines.append(f"- Created at (UTC): {normalized['createdAtUtc']}")
    lines.extend(bulletSection("Files changed", [f"`{path}`" for path in normalized["filesChanged"]]))
    lines.extend(["", f"## Validation commands ({len(normalized['commands'])})"])
    lines.extend(commandLine(entry) for entry in normalized["commands"])
    if not normalized["commands"]:
        lines.append("- none")
    lines.extend(bulletSection("Blockers", normalized.get("blockers", [])))
    lines.extend(bulletSection("Risks", normalized.get("risks", [])))
    if "observationRefs" in normalized:
        lines.extend(bulletSection("Observation refs", [f"`{ref}`" for ref in normalized["observationRefs"]]))
    lines.extend(
        ["", "## Next action", f"{normalized.get('nextAction') or SAFE_NEXT_ACTION_BY_OUTCOME[normalized['outcome']]}"]
    )
    return "\n".join(lines) + "\n"


def renderHandoffMarkdown(handoff: dict[str, Any]) -> str:
    source = handoff["source"]
    lines = [f"# Restart handoff: {source['issue']}", ""]
    lines.append(f"- Owner: `{source['owner']}`")
    lines.append(f"- Claim ID: `{source['claimId']}`")
    lines.append(f"- Branch: `{source['branch']}`")
    lines.append(f"- Outcome: {source['outcome']}")
    lines.append(f"- CI head SHA: `{source['ciHeadSha']}`")
    lines.append(f"- Report fingerprint: `{handoff['reportFingerprint']}`")
    lines.append(f"- Max items per section: {handoff['maxItemsPerSection']}")
    counts = handoff["commandStatusCounts"]
    lines.append("- Command status counts: " + ", ".join(f"{status}={counts[status]}" for status in COMMAND_STATUSES))
    lines.extend(
        [
            "",
            f"## Pending validation ({len(handoff['pendingValidation'])} kept, {handoff['pendingValidationOmitted']} omitted)",
        ]
    )
    lines.extend(commandLine(entry) for entry in handoff["pendingValidation"])
    if not handoff["pendingValidation"]:
        lines.append("- none")
    lines.extend(
        [
            "",
            f"## Accepted evidence ({len(handoff['acceptedEvidence'])} kept, {handoff['acceptedEvidenceOmitted']} omitted)",
        ]
    )
    lines.extend(f"- `{entry['command']}` (exit {entry['exitCode']})" for entry in handoff["acceptedEvidence"])
    if not handoff["acceptedEvidence"]:
        lines.append("- none")
    lines.extend(
        bulletSection(
            "Files changed", [f"`{path}`" for path in handoff["filesChanged"]], handoff["filesChangedOmitted"]
        )
    )
    lines.extend(bulletSection("Blockers", handoff["blockers"], handoff["blockersOmitted"]))
    lines.extend(bulletSection("Risks", handoff["risks"], handoff["risksOmitted"]))
    lines.extend(["", "## Safe next action", handoff["safeNextAction"]])
    return "\n".join(lines) + "\n"


def registryReportPayload(payload: dict[str, Any], lastSeenUtc: str | None = None) -> dict[str, Any]:
    """Minimal optional integration: convert a report into a subagent_registry report payload."""

    normalized = requireValidReport(payload, "build a registry payload")
    last_seen = lastSeenUtc or normalized.get("createdAtUtc")
    if not last_seen:
        raise WorkerReportError("registry payload requires --last-seen-utc or a report createdAtUtc")
    registry_payload: dict[str, Any] = {
        "owner": normalized["owner"],
        "claimId": normalized["claimId"],
        "lastSeenUtc": last_seen,
        "changedFiles": normalized["filesChanged"],
        "note": f"worker report: outcome={normalized['outcome']} ciHeadSha={normalized['ciHeadSha']}",
    }
    if "phase" in normalized:
        registry_payload["phase"] = normalized["phase"]
    if normalized["commands"]:
        registry_payload["validationCommand"] = normalized["commands"][-1]["command"]
    errors = subagent_registry.validateReportPayload(registry_payload)
    if errors:
        raise WorkerReportError("registry payload rejected: " + "; ".join(errors))
    return registry_payload


def loadReport(text: str | None, filePath: str | None) -> dict[str, Any]:
    if text and filePath:
        raise WorkerReportError("use either --report or --report-file, not both")
    if filePath:
        raw = Path(filePath).read_text(encoding="utf-8")
    elif text:
        raw = text
    else:
        raise WorkerReportError("a report is required: pass --report or --report-file")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WorkerReportError(f"report is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise WorkerReportError("report top-level JSON must be an object")
    return payload


def parseCommandJson(rawEntries: Sequence[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for raw in rawEntries:
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise WorkerReportError(f"--command-json is not valid JSON: {exc}") from exc
        if not isinstance(entry, dict):
            raise WorkerReportError("--command-json must be a JSON object")
        entries.append(entry)
    return entries


def buildReportFromArgs(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "owner": args.owner.strip(),
        "claimId": args.claim_id.strip(),
        "issue": args.issue.strip(),
        "branch": args.branch.strip(),
        "outcome": args.outcome,
        "ciHeadSha": args.ci_head_sha.strip().lower(),
        "filesChanged": list(args.file_changed),
        "commands": parseCommandJson(args.command_json),
    }
    created_at = args.created_at_utc or subagent_registry.formatUtc(subagent_registry.utcNow())
    if not args.no_created_at:
        payload["createdAtUtc"] = created_at
    for name, value in (
        ("controllerId", args.controller_id),
        ("registrationId", args.registration_id),
        ("role", args.role),
        ("phase", args.phase),
        ("nextAction", args.next_action),
    ):
        if value:
            payload[name] = value
    for name, values in (
        ("blockers", args.blocker),
        ("risks", args.risk),
        ("observationRefs", args.observation_ref),
    ):
        if values:
            payload[name] = list(values)
    return payload


def printJson(payload: dict[str, Any]) -> None:
    print(canonicalJson(payload), end="")


def addReportArguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--report", default=None, help="Inline JSON worker report")
    parser.add_argument("--report-file", default=None, help="Path to a JSON worker report")


def buildParser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    createParser = subparsers.add_parser("create", help="Build and validate a schema-version-1 worker report")
    createParser.add_argument("--owner", required=True, help="controller/<controller-id>/<agent>")
    createParser.add_argument("--claim-id", required=True)
    createParser.add_argument("--issue", required=True)
    createParser.add_argument("--branch", required=True)
    createParser.add_argument("--outcome", required=True, choices=sorted(OUTCOMES))
    createParser.add_argument("--ci-head-sha", required=True, help="Git SHA the validation evidence applies to")
    createParser.add_argument("--file-changed", action="append", default=[])
    createParser.add_argument(
        "--command-json",
        action="append",
        default=[],
        help='JSON command entry, e.g. {"command": "python3 test.py", "status": "passed", "exitCode": 0}',
    )
    createParser.add_argument("--controller-id", default=None)
    createParser.add_argument("--registration-id", default=None)
    createParser.add_argument(
        "--role", default=None, choices=sorted(subagent_registry.enumValues(subagent_registry.AgentRole))
    )
    createParser.add_argument(
        "--phase", default=None, choices=sorted(subagent_registry.enumValues(subagent_registry.AgentPhase))
    )
    createParser.add_argument("--created-at-utc", default=None)
    createParser.add_argument("--no-created-at", action="store_true", help="Omit createdAtUtc for byte-stable output")
    createParser.add_argument("--blocker", action="append", default=[])
    createParser.add_argument("--risk", action="append", default=[])
    createParser.add_argument("--observation-ref", action="append", default=[])
    createParser.add_argument("--next-action", default=None)
    createParser.add_argument("--output", default=None, help="Write the report JSON to this path instead of stdout")

    validateParser = subparsers.add_parser("validate", help="Validate schema, identity consistency, and CI SHA")
    addReportArguments(validateParser)
    validateParser.add_argument("--expect-owner", default=None)
    validateParser.add_argument("--expect-claim-id", default=None)
    validateParser.add_argument("--expect-issue", default=None)
    validateParser.add_argument("--expect-branch", default=None)
    validateParser.add_argument("--expect-ci-sha", default=None, help="Trusted CI/branch head SHA evidence")
    validateParser.add_argument("--repo", default=None, help="Resolve the report branch head read-only from this repo")

    renderParser = subparsers.add_parser("render", help="Render the normalized report as Markdown or canonical JSON")
    addReportArguments(renderParser)
    renderParser.add_argument("--format", default="markdown", choices=("markdown", "json"))

    handoffParser = subparsers.add_parser("handoff", help="Build a deterministic bounded restart handoff")
    addReportArguments(handoffParser)
    handoffParser.add_argument("--format", default="json", choices=("markdown", "json"))
    handoffParser.add_argument(
        "--max-items",
        type=int,
        default=HANDOFF_MAX_ITEMS_PER_SECTION,
        help=f"Per-section item cap (default {HANDOFF_MAX_ITEMS_PER_SECTION}, limit {HANDOFF_MAX_ITEMS_LIMIT})",
    )

    registryParser = subparsers.add_parser(
        "registry-payload", help="Convert a report into a subagent_registry report payload"
    )
    addReportArguments(registryParser)
    registryParser.add_argument("--last-seen-utc", default=None)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = buildParser()
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            payload = buildReportFromArgs(args)
            errors = validateReportPayload(payload)
            if errors:
                printJson({"valid": False, "errors": errors})
                return 1
            if args.output:
                Path(args.output).parent.mkdir(parents=True, exist_ok=True)
                Path(args.output).write_text(canonicalJson(normalizeReport(payload)), encoding="utf-8")
            else:
                printJson(normalizeReport(payload))
            return 0
        report = loadReport(args.report, args.report_file)
        if args.command == "validate":
            errors = validateReportPayload(report)
            if not errors:
                errors += identityErrors(
                    report,
                    expectedOwner=args.expect_owner,
                    expectedClaimId=args.expect_claim_id,
                    expectedIssue=args.expect_issue,
                    expectedBranch=args.expect_branch,
                )
                if args.expect_ci_sha:
                    errors += ciShaErrors(report, args.expect_ci_sha, "--expect-ci-sha")
                if args.repo:
                    head = resolveBranchHead(Path(args.repo), report["branch"])
                    if head is None:
                        errors.append(f"branch {report['branch']!r} cannot be resolved in repo {args.repo!r}")
                    else:
                        errors += ciShaErrors(report, head, f"current head of branch {report['branch']!r}")
            printJson(
                {
                    "valid": not errors,
                    "errors": errors,
                    "owner": report.get("owner"),
                    "claimId": report.get("claimId"),
                    "issue": report.get("issue"),
                }
            )
            return 1 if errors else 0
        if args.command == "render":
            if args.format == "json":
                printJson(requireValidReport(report, "render JSON"))
            else:
                print(renderReportMarkdown(report), end="")
            return 0
        if args.command == "handoff":
            handoff = buildHandoff(report, maxItems=args.max_items)
            if args.format == "json":
                printJson(handoff)
            else:
                print(renderHandoffMarkdown(handoff), end="")
            return 0
        if args.command == "registry-payload":
            printJson(registryReportPayload(report, lastSeenUtc=args.last_seen_utc))
            return 0
        raise WorkerReportError(f"Unsupported command {args.command}")
    except (WorkerReportError, OSError, ValueError) as exc:
        print(f"worker_report: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
