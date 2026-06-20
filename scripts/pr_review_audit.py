#!/usr/bin/env python3
"""Read-only PR review classifier for controller cleanup and merge decisions."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
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
    "startup_failure",
    "timed_out",
}
PENDING_STATES = {"expected", "in_progress", "pending", "queued", "requested", "waiting"}

CLEAN_MERGE_STATES = {"clean", "has_hooks"}
UPDATE_MERGE_STATES = {"behind", "conflicting", "dirty"}
HUMAN_MERGE_STATES = {"blocked", "draft", "unknown", "unstable"}

OPEN_STATES = {"open"}
OBSOLETE_LABELS = {"duplicate", "obsolete", "superseded"}


@dataclass(frozen=True)
class CheckSummary:
    state: str
    failed: tuple[str, ...] = ()
    pending: tuple[str, ...] = ()
    total: int = 0


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


def stateFromCheck(check: dict[str, Any]) -> str:
    state = normalizeToken(firstValue(check, "state", "status", default=""))
    conclusion = normalizeToken(firstValue(check, "conclusion", "result", default=""))
    rollup = normalizeToken(firstValue(check, "rollup", "checkRollup", default=""))

    for token in (conclusion, state, rollup):
        if token in FAILURE_STATES:
            return "failure"
    if state in {"completed", "complete"} and not conclusion:
        return "unknown"
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
        rawChecks = firstValue(rawChecks, "nodes", "items", "checks", default=())
    if isinstance(rawChecks, str) or not isinstance(rawChecks, Iterable):
        rawChecks = [rawChecks]

    failed: list[str] = []
    pending: list[str] = []
    unknown = False
    checks = list(rawChecks or ())
    for index, rawCheck in enumerate(checks, start=1):
        check = rawCheck if isinstance(rawCheck, dict) else {"state": rawCheck}
        name = checkName(check, f"check {index}")
        state = stateFromCheck(check)
        if state == "failure":
            failed.append(name)
        elif state == "pending":
            pending.append(name)
        elif state == "unknown":
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
    return any(
        truthy(firstValue(queue, name, default=False))
        for name in ("stale", "claimStale", "claim_stale", "leaseExpired", "lease_expired")
    )


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
    merged = truthy(firstValue(record, "merged", "isMerged", default=False))
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
        buckets.append("poll")
    elif checks.state == "unknown":
        blockers.append("check rollup is missing or unrecognized")
        buckets.append("human_review_required")

    queue = queuePayload(record)
    if queueClaimIsStale(queue):
        blockers.append("linked workbook claim is stale or lease-expired")
        buckets.append("human_review_required")

    if prType == "unknown_pr":
        buckets.append("human_review_required")

    if "needs_update_rebase" in buckets:
        return "needs_update_rebase", buckets
    if "failing_ci" in buckets:
        return "failing_ci", buckets
    if "human_review_required" in buckets:
        return "human_review_required", buckets
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
            "needs_update_rebase",
            "never_touch",
            "obsolete_duplicate_close",
        }
    )
    humanApproval = actionCategory in {
        "branch_cleanup_candidate",
        "human_review_required",
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
