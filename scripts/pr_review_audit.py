#!/usr/bin/env python3
"""Read-only PR review classifier for controller cleanup and merge decisions."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

WORKBOOK_PATH = "planning/fall_of_nouraajd_issue_proposals.xlsx"

SUCCESS_STATES = {"success", "successful", "passed", "pass"}
FAILURE_STATES = {
    "action_required",
    "cancelled",
    "canceled",
    "error",
    "failure",
    "failed",
    "stale",
    "startup_failure",
    "timed_out",
}
PENDING_STATES = {"expected", "in_progress", "pending", "queued", "requested", "waiting"}
NEUTRAL_STATES = {"neutral", "skipped"}

CLEAN_MERGE_STATES = {"clean", "has_hooks"}
UPDATE_MERGE_STATES = {"behind", "conflicting", "dirty"}
HUMAN_MERGE_STATES = {"blocked", "draft", "unknown", "unstable"}

OPEN_STATES = {"open"}
OBSOLETE_LABELS = {"duplicate", "obsolete", "superseded"}
AUTO_MERGE_DISABLED_MARKERS = (
    "auto_merge_is_not_allowed",
    "enablepullrequestautomerge",
)


@dataclass(frozen=True)
class CheckSummary:
    state: str
    failed: tuple[str, ...] = ()
    pending: tuple[str, ...] = ()
    total: int = 0


@dataclass(frozen=True)
class CheckAttempt:
    identity: tuple[str, str]
    name: str
    state: str
    timestamp: float | None
    attempt: int | None
    index: int


def normalizeToken(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return normalizeToken(value) in {"1", "true", "yes", "y", "on"}


def firstValue(mapping: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in mapping:
            return mapping[name]
    return default


def normalizeFiles(record: dict[str, Any]) -> tuple[str, ...]:
    rawFiles = firstValue(record, "files", "changedFiles", "changed_files", "filenames", default=())
    if isinstance(rawFiles, dict):
        rawFiles = firstValue(rawFiles, "nodes", "items", "files", default=())
    if isinstance(rawFiles, str):
        rawFiles = [rawFiles]
    elif not isinstance(rawFiles, Iterable):
        rawFiles = ()
    files: list[str] = []
    for item in rawFiles or ():
        if isinstance(item, dict):
            item = firstValue(item, "filename", "path", "name", default="")
        if item:
            files.append(str(item))
    return tuple(sorted(dict.fromkeys(files)))


def normalizeLabels(record: dict[str, Any]) -> tuple[str, ...]:
    rawLabels = firstValue(record, "labels", "labelNames", "label_names", default=())
    if isinstance(rawLabels, dict):
        rawLabels = firstValue(rawLabels, "nodes", "items", "labels", default=())
    if isinstance(rawLabels, str):
        rawLabels = [rawLabels]
    elif not isinstance(rawLabels, Iterable):
        rawLabels = ()
    labels: list[str] = []
    for item in rawLabels or ():
        if isinstance(item, dict):
            item = firstValue(item, "name", "title", default="")
        token = normalizeToken(item)
        if token:
            labels.append(token)
    return tuple(sorted(dict.fromkeys(labels)))


def queuePayload(record: dict[str, Any]) -> dict[str, Any]:
    payload = firstValue(record, "queue", "workbook", "workbookRow", "linkedQueueRow", default={})
    if isinstance(payload, dict):
        return payload
    return {}


def checkName(check: dict[str, Any], fallback: str) -> str:
    return str(firstValue(check, "name", "context", "checkName", "job", default=fallback))


def nestedValue(mapping: dict[str, Any], *names: str) -> Any:
    value: Any = mapping
    for name in names:
        if not isinstance(value, dict):
            return None
        value = value.get(name)
    return value


def checkWorkflowName(check: dict[str, Any]) -> str:
    workflow = firstValue(check, "workflowName", "workflow_name", "workflow", default="")
    if isinstance(workflow, dict):
        workflow = firstValue(workflow, "name", "workflowName", "workflow_name", default="")
    return str(workflow or "")


def checkIdentity(check: dict[str, Any], fallback: str) -> tuple[str, str]:
    workflow = normalizeToken(checkWorkflowName(check))
    name = normalizeToken(checkName(check, fallback))
    return (workflow, name)


def parseTimestamp(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def checkTimestamp(check: dict[str, Any]) -> float | None:
    timestamps = [
        parseTimestamp(firstValue(check, name, default=None))
        for name in (
            "completedAt",
            "completed_at",
            "updatedAt",
            "updated_at",
            "startedAt",
            "started_at",
            "createdAt",
            "created_at",
        )
    ]
    timestamps = [timestamp for timestamp in timestamps if timestamp is not None]
    return max(timestamps) if timestamps else None


def parseAttempt(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def checkAttemptNumber(check: dict[str, Any]) -> int | None:
    values = [
        firstValue(
            check,
            "runAttempt",
            "run_attempt",
            "attempt",
            "attemptNumber",
            "attempt_number",
            "checkRunAttempt",
            "check_run_attempt",
            default=None,
        ),
        nestedValue(check, "checkSuite", "workflowRun", "runAttempt"),
        nestedValue(check, "check_suite", "workflow_run", "run_attempt"),
        nestedValue(check, "workflowRun", "runAttempt"),
        nestedValue(check, "workflow_run", "run_attempt"),
    ]
    attempts = [attempt for attempt in (parseAttempt(value) for value in values) if attempt is not None]
    return max(attempts) if attempts else None


def currentCheckAttempt(attempts: Sequence[CheckAttempt]) -> CheckAttempt:
    if not attempts:
        raise ValueError("check attempt group cannot be empty")
    if all(attempt.timestamp is not None for attempt in attempts):
        return max(
            attempts,
            key=lambda attempt: (
                attempt.timestamp,
                attempt.attempt if attempt.attempt is not None else -1,
                attempt.index,
            ),
        )
    if all(attempt.attempt is not None for attempt in attempts):
        return max(attempts, key=lambda attempt: (attempt.attempt, attempt.index))

    stateRank = {"failure": 3, "pending": 2, "unknown": 1, "success": 0}
    return max(attempts, key=lambda attempt: (stateRank[attempt.state], attempt.index))


def stateFromCheck(check: dict[str, Any]) -> str:
    state = normalizeToken(firstValue(check, "state", "status", default=""))
    conclusion = normalizeToken(firstValue(check, "conclusion", "result", default=""))
    rollup = normalizeToken(firstValue(check, "rollup", "checkRollup", default=""))

    for token in (conclusion, state, rollup):
        if token in FAILURE_STATES:
            return "failure"
    if state in {"completed", "complete"} and not conclusion:
        return "unknown"
    if conclusion in NEUTRAL_STATES or state in NEUTRAL_STATES or rollup in NEUTRAL_STATES:
        return "success"
    if conclusion in SUCCESS_STATES or state in SUCCESS_STATES or rollup in SUCCESS_STATES:
        return "success"
    if state in PENDING_STATES or conclusion in PENDING_STATES or rollup in PENDING_STATES:
        return "pending"
    return "unknown"


def summaryFromRollup(value: Any) -> CheckSummary | None:
    if isinstance(value, dict):
        value = firstValue(value, "state", "status", "conclusion", "rollup", default="")
    token = normalizeToken(value)
    if not token:
        return None
    if token in SUCCESS_STATES:
        return CheckSummary(state="success", total=1)
    if token in FAILURE_STATES:
        return CheckSummary(state="failure", failed=("check rollup",), total=1)
    if token in PENDING_STATES:
        return CheckSummary(state="pending", pending=("check rollup",), total=1)
    return CheckSummary(state="unknown", total=1)


def checkSummary(record: dict[str, Any]) -> CheckSummary:
    rawChecks = firstValue(
        record,
        "checks",
        "checkRuns",
        "check_runs",
        "statusCheckRollup",
        "status_check_rollup",
        "statusChecks",
        "status_checks",
        default=None,
    )
    if rawChecks is None:
        rollup = firstValue(
            record,
            "checkRollup",
            "check_rollup",
            "checksState",
            "checks_state",
            "ciState",
            "ci_state",
            default=None,
        )
        summary = summaryFromRollup(rollup)
        return summary or CheckSummary(state="unknown")

    if isinstance(rawChecks, dict):
        nested = firstValue(rawChecks, "nodes", "items", "checks", default=None)
        if nested is None:
            # An object-shaped rollup with no nested check collection may carry the
            # aggregate state directly (e.g. {"state": "SUCCESS"}); interpret it the
            # same way as the checkRollup fallback instead of dropping it to unknown.
            summary = summaryFromRollup(rawChecks)
            if summary is not None:
                return summary
        rawChecks = nested if nested is not None else ()
    if isinstance(rawChecks, str) or not isinstance(rawChecks, Iterable):
        rawChecks = [rawChecks]

    byIdentity: dict[tuple[str, str], list[CheckAttempt]] = {}
    unknown = False
    checks = list(rawChecks or ())
    for index, rawCheck in enumerate(checks, start=1):
        check = rawCheck if isinstance(rawCheck, dict) else {"state": rawCheck}
        name = checkName(check, f"check {index}")
        state = stateFromCheck(check)
        attempt = CheckAttempt(
            identity=checkIdentity(check, f"check {index}"),
            name=name,
            state=state,
            timestamp=checkTimestamp(check),
            attempt=checkAttemptNumber(check),
            index=index,
        )
        byIdentity.setdefault(attempt.identity, []).append(attempt)

    failed: list[str] = []
    pending: list[str] = []
    for attempt in (currentCheckAttempt(attempts) for attempts in byIdentity.values()):
        if attempt.state == "failure":
            failed.append(attempt.name)
        elif attempt.state == "pending":
            pending.append(attempt.name)
        elif attempt.state == "unknown":
            unknown = True

    if failed:
        return CheckSummary(state="failure", failed=tuple(failed), pending=tuple(pending), total=len(checks))
    if pending:
        return CheckSummary(state="pending", pending=tuple(pending), total=len(checks))
    if unknown or not checks:
        return CheckSummary(state="unknown", total=len(checks))
    return CheckSummary(state="success", total=len(checks))


def mergeState(record: dict[str, Any]) -> str:
    return normalizeToken(
        firstValue(record, "mergeStateStatus", "merge_state_status", "mergeableState", "mergeable_state", default="")
    )


def isWorkbookOnly(files: Sequence[str]) -> bool:
    return tuple(files) == (WORKBOOK_PATH,)


def isWorkflowFile(path: str) -> bool:
    return path == "AGENTS.md" or path.startswith(("docs/", "prompts/", "scripts/", ".github/"))


def hasQueueLink(queue: dict[str, Any]) -> bool:
    return any(
        firstValue(queue, name, default=None)
        for name in ("issue", "issueName", "status", "owner", "claimId", "claim_id")
    )


def queueStatus(queue: dict[str, Any]) -> str:
    return normalizeToken(firstValue(queue, "status", "queueStatus", "rowStatus", default=""))


def queueClaimIsStale(queue: dict[str, Any]) -> bool:
    if any(
        truthy(firstValue(queue, name, default=False))
        for name in (
            "stale",
            "claimStale",
            "claim_stale",
            "heartbeatOverdue",
            "heartbeat_overdue",
            "leaseExpired",
            "lease_expired",
            "reclaimable",
        )
    ):
        return True

    claimHealth = normalizeToken(firstValue(queue, "claimHealth", "claim_health", default=""))
    return bool(claimHealth and claimHealth != "healthy")


def queueOwner(queue: dict[str, Any]) -> str:
    return str(firstValue(queue, "owner", "assignee", default="") or "")


def controllerOwned(queue: dict[str, Any]) -> bool:
    explicit = firstValue(queue, "controllerOwned", "controller_owned", default=None)
    if explicit is not None:
        return truthy(explicit)
    return queueOwner(queue).startswith("controller/")


def classifyPrType(record: dict[str, Any], files: Sequence[str], queue: dict[str, Any]) -> tuple[str, list[str]]:
    blockers: list[str] = []
    if isWorkbookOnly(files):
        return "workbook_only_queue_pr", blockers
    if queueStatus(queue) == "in_progress" and not queueClaimIsStale(queue):
        return "implementation_pr_with_active_workbook_claim", blockers
    if queueStatus(queue) == "in_progress" and queueClaimIsStale(queue):
        return "implementation_pr_with_stale_workbook_claim", blockers
    if hasQueueLink(queue) or firstValue(record, "linkedIssue", "issue", "issueName", default=None):
        return "implementation_pr", blockers
    if files and all(isWorkflowFile(path) for path in files):
        return "workflow_pr", blockers
    blockers.append("missing queue link, changed-file class, or PR type signal")
    return "unknown_pr", blockers


def localSafetyBlockers(record: dict[str, Any]) -> list[str]:
    local = firstValue(record, "local", "branch", "recovery", default={})
    if not isinstance(local, dict):
        local = {}
    blockers: list[str] = []
    if truthy(firstValue(local, "dirty", "dirtyWorktree", "worktreeDirty", default=False)):
        blockers.append("local worktree is dirty")
    if truthy(firstValue(local, "unpushedCommits", "unpushed", default=False)):
        blockers.append("branch has unpushed commits")
    if truthy(firstValue(local, "unreviewedCommits", "unreviewed", default=False)):
        blockers.append("branch has unreviewed commits")
    return blockers


def autoMergePolicyBlocker(record: dict[str, Any]) -> str | None:
    candidates = [
        firstValue(
            record,
            "autoMergeError",
            "auto_merge_error",
            "autoMergeFailure",
            "auto_merge_failure",
            "mergeError",
            "merge_error",
            default="",
        ),
        nestedValue(record, "autoMerge", "error"),
        nestedValue(record, "auto_merge", "error"),
        nestedValue(record, "autoMergeRequest", "error"),
        nestedValue(record, "auto_merge_request", "error"),
    ]
    for value in candidates:
        text = str(value or "").strip()
        normalized = normalizeToken(text)
        if text and any(marker in normalized for marker in AUTO_MERGE_DISABLED_MARKERS):
            return "repository auto-merge is disabled or unavailable"
    return None


def actionFromSignals(
    record: dict[str, Any],
    prType: str,
    labels: Sequence[str],
    merge: str,
    checks: CheckSummary,
    blockers: list[str],
) -> tuple[str, list[str]]:
    buckets: list[str] = [prType]
    state = normalizeToken(firstValue(record, "state", default="open"))
    merged = (
        state == "merged"
        or truthy(firstValue(record, "merged", "isMerged", default=False))
        or bool(firstValue(record, "mergedAt", "merged_at", "mergeCommit", "merge_commit", default=None))
    )
    branchMerged = truthy(firstValue(record, "branchMergedToMain", "branch_merged_to_main", default=False))
    draft = truthy(firstValue(record, "draft", "isDraft", default=False))
    reviewDecision = normalizeToken(firstValue(record, "reviewDecision", "review_decision", default=""))

    localBlockers = localSafetyBlockers(record)
    if localBlockers:
        blockers.extend(localBlockers)
        buckets.append("never_touch")
        return "never_touch", buckets

    if state not in OPEN_STATES:
        if merged or branchMerged:
            buckets.append("branch_cleanup_candidate")
            return "branch_cleanup_candidate", buckets
        buckets.append("human_review_required")
        blockers.append(f"PR state is {state or 'unknown'}")
        return "human_review_required", buckets

    if any(label in OBSOLETE_LABELS for label in labels) or truthy(
        firstValue(record, "obsolete", "duplicate", "superseded", default=False)
    ):
        buckets.append("obsolete_duplicate_close")
        return "obsolete_duplicate_close", buckets

    if draft:
        blockers.append("PR is draft")
        buckets.append("human_review_required")
    if reviewDecision in {"changes_requested", "review_required"}:
        blockers.append(f"review decision is {reviewDecision}")
        buckets.append("human_review_required")
    if merge in UPDATE_MERGE_STATES:
        blockers.append(f"merge state {merge.upper()} requires update/rebase")
        buckets.append("needs_update_rebase")
    elif merge in HUMAN_MERGE_STATES:
        blockers.append(f"merge state {merge.upper()} requires human review")
        buckets.append("human_review_required")
    elif not merge:
        blockers.append("merge state is missing")
        buckets.append("human_review_required")
    elif merge not in CLEAN_MERGE_STATES:
        blockers.append(f"merge state {merge.upper()} is unrecognized")
        buckets.append("human_review_required")

    if checks.state == "failure":
        blockers.append("required check failure: " + ", ".join(checks.failed))
        buckets.append("failing_ci")
    elif checks.state == "pending":
        if prType == "workbook_only_queue_pr":
            buckets.append("ci_exempt_pending")
        else:
            buckets.append("poll")
    elif checks.state == "unknown":
        blockers.append("check rollup is missing or unrecognized")
        buckets.append("human_review_required")

    autoMergeBlocker = autoMergePolicyBlocker(record)
    if autoMergeBlocker:
        blockers.append(autoMergeBlocker)
        buckets.append("merge_policy_blocked")

    queue = queuePayload(record)
    if queueClaimIsStale(queue):
        blockers.append("linked workbook claim requires recovery before merge or cleanup")
        buckets.append("human_review_required")

    if prType == "unknown_pr":
        buckets.append("human_review_required")

    if "needs_update_rebase" in buckets:
        return "needs_update_rebase", buckets
    if "failing_ci" in buckets:
        return "failing_ci", buckets
    if "human_review_required" in buckets:
        return "human_review_required", buckets
    if "merge_policy_blocked" in buckets:
        return "merge_policy_blocked", buckets
    if "poll" in buckets:
        return "poll", buckets
    buckets.append("ready_to_merge")
    return "ready_to_merge", buckets


def recommendedActions(actionCategory: str, prType: str, blockers: Sequence[str]) -> list[str]:
    if actionCategory == "ready_to_merge" and prType == "workbook_only_queue_pr":
        return ["confirm XLSX-only diff and queue validation, then merge according to workbook-only policy"]
    if actionCategory == "ready_to_merge":
        return ["confirm required evidence and merge according to pull request policy"]
    if actionCategory == "poll":
        return ["poll pending required checks for the exact PR head"]
    if actionCategory == "failing_ci":
        return ["fix or re-run failed required checks before merge or cleanup"]
    if actionCategory == "needs_update_rebase":
        return ["update or rebase the branch before any merge decision"]
    if actionCategory == "merge_policy_blocked":
        return [
            "request repository auto-merge settings or explicit alternate merge authorization before retrying merge"
        ]
    if actionCategory == "obsolete_duplicate_close":
        return ["request explicit human approval before closing obsolete or duplicate work"]
    if actionCategory == "branch_cleanup_candidate":
        return ["request explicit human approval before deleting local or remote branches"]
    if actionCategory == "never_touch":
        return ["do not merge, close, delete, or overwrite until recoverable work is reviewed"]
    if blockers:
        return ["collect missing signals or resolve blockers before cleanup or merge"]
    return ["inspect manually before taking action"]


def classifyPr(record: dict[str, Any]) -> dict[str, Any]:
    files = normalizeFiles(record)
    labels = normalizeLabels(record)
    queue = queuePayload(record)
    checks = checkSummary(record)
    blockers: list[str] = []
    prType, typeBlockers = classifyPrType(record, files, queue)
    blockers.extend(typeBlockers)
    actionCategory, buckets = actionFromSignals(record, prType, labels, mergeState(record), checks, blockers)
    buckets = sorted(dict.fromkeys(buckets))
    blockerTuple = tuple(dict.fromkeys(blockers))
    isControllerOwned = controllerOwned(queue)
    dispatchAttention = (
        isControllerOwned
        and prType
        in {
            "implementation_pr",
            "implementation_pr_with_active_workbook_claim",
            "implementation_pr_with_stale_workbook_claim",
            "unknown_pr",
        }
        and actionCategory
        in {
            "failing_ci",
            "human_review_required",
            "merge_policy_blocked",
            "needs_update_rebase",
            "never_touch",
            "obsolete_duplicate_close",
        }
    )
    humanApproval = actionCategory in {
        "branch_cleanup_candidate",
        "human_review_required",
        "merge_policy_blocked",
        "never_touch",
        "obsolete_duplicate_close",
    }
    return {
        "number": firstValue(record, "number", "prNumber", "id", default=None),
        "title": firstValue(record, "title", default=""),
        "state": normalizeToken(firstValue(record, "state", default="open")) or "unknown",
        "actionCategory": actionCategory,
        "prType": prType,
        "buckets": buckets,
        "changedFiles": list(files),
        "checkState": checks.state,
        "failedChecks": list(checks.failed),
        "pendingChecks": list(checks.pending),
        "mergeState": mergeState(record) or "missing",
        "controllerOwned": isControllerOwned,
        "controllerDispatchAttention": dispatchAttention,
        "mergeAllowed": actionCategory == "ready_to_merge",
        "cleanupAllowed": False,
        "humanApprovalRequired": humanApproval,
        "blockers": list(blockerTuple),
        "recommendedActions": recommendedActions(actionCategory, prType, blockerTuple),
    }


def loadRecords(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        records = firstValue(payload, "pullRequests", "pull_requests", "prs", "items", "nodes", default=None)
        if records is None:
            records = [payload]
    else:
        raise ValueError("input JSON must be an object or list")
    if not isinstance(records, list):
        raise ValueError("pull request records must be a list")
    normalized: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("each pull request record must be an object")
        normalized.append(record)
    return normalized


def auditPayload(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    reviews = [classifyPr(record) for record in records]
    actionCounts = Counter(review["actionCategory"] for review in reviews)
    typeCounts = Counter(review["prType"] for review in reviews)
    return {
        "readOnly": True,
        "summary": {
            "total": len(reviews),
            "actions": dict(sorted(actionCounts.items())),
            "types": dict(sorted(typeCounts.items())),
            "controllerDispatchAttention": sum(1 for review in reviews if review["controllerDispatchAttention"]),
            "mergeAllowed": sum(1 for review in reviews if review["mergeAllowed"]),
            "cleanupAllowed": 0,
        },
        "pullRequests": reviews,
    }


def renderTable(payload: dict[str, Any]) -> str:
    lines = ["PR\tACTION\tTYPE\tCHECKS\tMERGE\tATTENTION\tBLOCKERS"]
    for review in payload["pullRequests"]:
        number = review["number"]
        prNumber = f"#{number}" if number is not None else "-"
        blockers = "; ".join(review["blockers"]) if review["blockers"] else "-"
        attention = "yes" if review["controllerDispatchAttention"] else "no"
        lines.append(
            "\t".join(
                [
                    prNumber,
                    review["actionCategory"],
                    review["prType"],
                    review["checkState"],
                    review["mergeState"],
                    attention,
                    blockers,
                ]
            )
        )
    return "\n".join(lines)


def readInput(path: str | None) -> Any:
    if path:
        text = Path(path).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()
    if not text.strip():
        raise ValueError("no input JSON provided")
    return json.loads(text)


def parseArgs(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="JSON file containing normalized pull request records; defaults to stdin")
    parser.add_argument("--format", choices=("json", "table"), default="json")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parseArgs(argv or sys.argv[1:])
    try:
        payload = auditPayload(loadRecords(readInput(args.input)))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"pr_review_audit: {exc}", file=sys.stderr)
        return 2
    if args.format == "table":
        print(renderTable(payload))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
