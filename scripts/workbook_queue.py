#!/usr/bin/env python3
"""Aggregate controller queue operations across planning XLSX workbooks."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from scripts import issue_queue
except ModuleNotFoundError:  # Support `python3 scripts/workbook_queue.py`.
    import issue_queue

DEFAULT_PATTERN = "planning/*.xlsx"
ENV_WORKBOOKS = "GAME_ISSUE_QUEUE_FILES"


@dataclass
class WorkbookQueue:
    path: Path
    state: issue_queue.QueueState


@dataclass
class Discovery:
    queues: list[WorkbookQueue]
    skipped: list[dict[str, str]]

    def close(self) -> None:
        for queue in self.queues:
            with contextlib.suppress(Exception):
                queue.state.workbook.close()


class AggregateQueueError(issue_queue.QueueError):
    pass


def displayPath(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def resolveWorkbookPaths(rawPaths: Sequence[str] | None = None) -> list[Path]:
    candidates: list[Path] = []
    if rawPaths:
        candidates.extend(Path(item).expanduser() for item in rawPaths if item)
    elif os.environ.get(ENV_WORKBOOKS):
        candidates.extend(
            Path(item).expanduser() for item in os.environ[ENV_WORKBOOKS].split(os.pathsep) if item.strip()
        )
    elif os.environ.get("GAME_ISSUE_QUEUE_FILE"):
        candidates.append(Path(os.environ["GAME_ISSUE_QUEUE_FILE"]).expanduser())
    else:
        candidates.extend(sorted(Path.cwd().glob(DEFAULT_PATTERN)))

    result: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        path = candidate.resolve()
        if path not in seen:
            result.append(path)
            seen.add(path)
    return result


def discoverQueues(rawPaths: Sequence[str] | None = None) -> Discovery:
    queues: list[WorkbookQueue] = []
    skipped: list[dict[str, str]] = []
    for path in resolveWorkbookPaths(rawPaths):
        if not path.is_file():
            skipped.append({"workbook": displayPath(path), "reason": "file does not exist"})
            continue
        try:
            state = issue_queue.loadQueue(path, writable=False)
        except Exception as exc:
            skipped.append({"workbook": displayPath(path), "reason": str(exc)})
            continue
        missing = [header for header in issue_queue.REQUIRED_HEADERS if header not in state.headers]
        if missing:
            state.workbook.close()
            skipped.append(
                {
                    "workbook": displayPath(path),
                    "reason": "missing required columns: " + ", ".join(missing),
                }
            )
            continue
        queues.append(WorkbookQueue(path=path, state=state))
    return Discovery(queues=queues, skipped=skipped)


def aggregateState(discovery: Discovery) -> issue_queue.QueueState:
    if not discovery.queues:
        raise AggregateQueueError("No queue-compatible workbooks were discovered")
    tasks: list[issue_queue.TaskRecord] = []
    first = discovery.queues[0].state
    for queue in discovery.queues:
        source = displayPath(queue.path)
        for task in queue.state.tasks:
            values = dict(task.values)
            values["Workbook"] = source
            tasks.append(issue_queue.TaskRecord(row=task.row, values=values))
    return issue_queue.QueueState(
        workbook=first.workbook,
        sheet=first.sheet,
        headers=first.headers,
        tasks=tasks,
    )


def sourceByIssue(discovery: Discovery) -> tuple[dict[str, WorkbookQueue], dict[str, list[str]]]:
    sources: dict[str, WorkbookQueue] = {}
    duplicates: dict[str, list[str]] = {}
    for queue in discovery.queues:
        for task in queue.state.tasks:
            if task.issueName in sources:
                duplicates.setdefault(task.issueName, [displayPath(sources[task.issueName].path)]).append(
                    displayPath(queue.path)
                )
            else:
                sources[task.issueName] = queue
    return sources, duplicates


def requireUniqueIssue(discovery: Discovery, issueName: str) -> WorkbookQueue:
    sources, duplicates = sourceByIssue(discovery)
    if issueName in duplicates:
        raise AggregateQueueError(
            f"Issue name is duplicated across workbooks: {issueName}: " + ", ".join(duplicates[issueName])
        )
    if issueName not in sources:
        raise AggregateQueueError(f"Unknown issue name across discovered workbooks: {issueName}")
    return sources[issueName]


def addWorkbook(payload: dict[str, Any], path: Path) -> dict[str, Any]:
    payload = dict(payload)
    payload["Workbook"] = displayPath(path)
    payload["workbook"] = displayPath(path)
    return payload


def annotateShortlist(payload: dict[str, Any], discovery: Discovery) -> dict[str, Any]:
    sources, _ = sourceByIssue(discovery)

    def annotateIssue(record: dict[str, Any]) -> None:
        issueName = str(record.get("issueName") or "")
        queue = sources.get(issueName)
        if queue:
            record["workbook"] = displayPath(queue.path)

    for group in payload.get("storyGroups", []):
        for issue in group.get("issues", []):
            annotateIssue(issue)
    selected = payload.get("selected")
    if isinstance(selected, dict) and isinstance(selected.get("issue"), dict):
        annotateIssue(selected["issue"])
    for issueName, reasons in list((payload.get("rejected") or {}).items()):
        queue = sources.get(issueName)
        if queue and isinstance(reasons, list):
            payload.setdefault("rejectedWorkbooks", {})[issueName] = displayPath(queue.path)
    payload["workbooks"] = [displayPath(queue.path) for queue in discovery.queues]
    payload["skippedWorkbooks"] = discovery.skipped
    return payload


def filterPerWorkbookDependencyErrors(
    errors: Iterable[str],
    globalNames: set[str],
) -> list[str]:
    result: list[str] = []
    prefix = "unknown dependency "
    for error in errors:
        if prefix in error:
            dependency = error.split(prefix, 1)[1].strip()
            if len(dependency) >= 2 and dependency[0] == dependency[-1] and dependency[0] in {"'", '"'}:
                dependency = dependency[1:-1]
            if dependency in globalNames:
                continue
        result.append(error)
    return result


def aggregateDependencyErrors(tasks: Sequence[issue_queue.TaskRecord]) -> list[str]:
    graph = {task.issueName: task.dependencies for task in tasks}
    errors: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            start = stack.index(name) if name in stack else 0
            errors.append("Cross-workbook dependency cycle: " + " -> ".join(stack[start:] + [name]))
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
    return errors


def validateDiscovery(discovery: Discovery) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    aggregate = aggregateState(discovery)
    globalNames = {task.issueName for task in aggregate.tasks}
    _, duplicates = sourceByIssue(discovery)
    for issueName, workbooks in sorted(duplicates.items()):
        errors.append(f"Duplicate Issue Name across workbooks: {issueName}: {', '.join(workbooks)}")

    for queue in discovery.queues:
        queueErrors, queueWarnings = issue_queue.validateQueueState(queue.state)
        queueErrors = filterPerWorkbookDependencyErrors(queueErrors, globalNames)
        label = displayPath(queue.path)
        errors.extend(f"{label}: {message}" for message in queueErrors)
        warnings.extend(f"{label}: {message}" for message in queueWarnings)

    known = globalNames
    for task in aggregate.tasks:
        for dependency in task.dependencies:
            if dependency not in known:
                errors.append(
                    f"{task.values.get('Workbook')}: row {task.row}: unknown aggregate dependency {dependency!r}"
                )
    errors.extend(aggregateDependencyErrors(aggregate.tasks))
    return errors, warnings


def workbookSummary(discovery: Discovery) -> dict[str, Any]:
    return {
        "compatible": [
            {
                "workbook": displayPath(queue.path),
                "issues": len(queue.state.tasks),
                "sheet": issue_queue.ISSUE_SHEET,
            }
            for queue in discovery.queues
        ],
        "skipped": discovery.skipped,
        "compatibleCount": len(discovery.queues),
        "skippedCount": len(discovery.skipped),
    }


def printJson(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def addWorkbookArguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workbook",
        action="append",
        default=[],
        help=(
            "Queue workbook path; repeat to select multiple workbooks. Default: "
            f"${ENV_WORKBOOKS}, $GAME_ISSUE_QUEUE_FILE, or {DEFAULT_PATTERN}"
        ),
    )
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)


def addFilters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--priority", action="append", default=[])
    parser.add_argument("--epic")
    parser.add_argument("--component")
    parser.add_argument("--allow-file-overlap", action="store_true")


def buildParser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    workbooks = subparsers.add_parser("workbooks", help="Discover planning workbooks and report queue compatibility")
    addWorkbookArguments(workbooks)
    workbooks.add_argument("--json", action="store_true")

    validate = subparsers.add_parser("validate", help="Validate all discovered queue workbooks as one queue")
    addWorkbookArguments(validate)

    controller = subparsers.add_parser("controller-id", help="Generate a unique controller owner prefix")
    controller.add_argument("--controller-id")
    controller.add_argument("--worker", default="subagent-1")
    controller.add_argument("--plain", action="store_true")

    listParser = subparsers.add_parser("list", help="List tasks across all queue workbooks")
    addWorkbookArguments(listParser)
    listParser.add_argument("--status", action="append", default=[])
    listParser.add_argument("--owner")
    listParser.add_argument("--epic")
    listParser.add_argument("--json", action="store_true")

    show = subparsers.add_parser("show", help="Show one task and its source workbook")
    addWorkbookArguments(show)
    show.add_argument("--issue", required=True)

    nextParser = subparsers.add_parser("next", help="Preview the next aggregate eligible task")
    addWorkbookArguments(nextParser)
    nextParser.add_argument("--owner", default="preview")
    addFilters(nextParser)

    shortlist = subparsers.add_parser("shortlist", help="Build one seeded shortlist across all queue workbooks")
    addWorkbookArguments(shortlist)
    addFilters(shortlist)
    shortlist.add_argument("--seed")
    shortlist.add_argument("--include-rejected", action="store_true")
    shortlist.add_argument("--json", action="store_true")
    shortlist.add_argument("--controller-id")
    shortlist.add_argument(
        "--controller-active-floor", type=int, default=issue_queue.DEFAULT_CONTROLLER_ACTIVE_ISSUE_FLOOR
    )
    shortlist.add_argument(
        "--controller-active-limit", type=int, default=issue_queue.DEFAULT_CONTROLLER_ACTIVE_ISSUE_LIMIT
    )

    claim = subparsers.add_parser("claim", help="Claim an exact issue from its source workbook")
    addWorkbookArguments(claim)
    addFilters(claim)
    claim.add_argument("--owner", required=True)
    claim.add_argument("--issue")
    claim.add_argument("--lease-minutes", type=int, default=120)
    claim.add_argument("--format", choices=("json", "prompt"), default="json")

    prompt = subparsers.add_parser("prompt", help="Render a claimed issue prompt with workbook identity")
    addWorkbookArguments(prompt)
    prompt.add_argument("--issue", required=True)
    prompt.add_argument("--claim-id", required=True)
    prompt.add_argument("--owner", required=True)

    heartbeat = subparsers.add_parser("heartbeat", help="Update one active claim")
    addWorkbookArguments(heartbeat)
    heartbeat.add_argument("--issue", required=True)
    heartbeat.add_argument("--claim-id", required=True)
    heartbeat.add_argument("--owner", required=True)
    heartbeat.add_argument("--progress", type=int)
    heartbeat.add_argument("--note", default="")
    heartbeat.add_argument("--lease-minutes", type=int, default=120)

    complete = subparsers.add_parser("complete", help="Mark one active claim DONE")
    addWorkbookArguments(complete)
    complete.add_argument("--issue", required=True)
    complete.add_argument("--claim-id", required=True)
    complete.add_argument("--owner", required=True)
    complete.add_argument("--note", default="")
    complete.add_argument("--summary")
    complete.add_argument("--summary-file")
    complete.add_argument("--validation")
    complete.add_argument("--validation-file")

    for command, status in (
        ("block", issue_queue.STATUS_BLOCKED),
        ("fail", issue_queue.STATUS_FAILED),
        ("cancel", issue_queue.STATUS_CANCELLED),
    ):
        finish = subparsers.add_parser(command, help=f"Mark one active claim {status}")
        addWorkbookArguments(finish)
        finish.add_argument("--issue", required=True)
        finish.add_argument("--claim-id", required=True)
        finish.add_argument("--owner", required=True)
        finish.add_argument("--note", required=True)
        finish.add_argument("--summary")
        finish.add_argument("--summary-file")
        finish.add_argument("--validation")
        finish.add_argument("--validation-file")
        finish.set_defaults(targetStatus=status)

    release = subparsers.add_parser("release", help="Return one owned task to NOT_STARTED")
    addWorkbookArguments(release)
    release.add_argument("--issue", required=True)
    release.add_argument("--claim-id", required=True)
    release.add_argument("--owner", required=True)
    release.add_argument("--note", default="")

    reclaim = subparsers.add_parser("reclaim-stale", help="Inspect or release stale claims in all workbooks")
    addWorkbookArguments(reclaim)
    reclaim.add_argument("--older-than-minutes", type=int, default=issue_queue.DEFAULT_RECLAIM_AGE_MINUTES)
    reclaim.add_argument("--dry-run", action="store_true")
    return parser


def selectedIssueFromAggregate(state: issue_queue.QueueState, args: argparse.Namespace) -> str:
    priorities = {item.upper() for item in args.priority} or None
    eligible, rejected = issue_queue.eligibleTasks(
        state,
        priorities=priorities,
        epic=args.epic,
        component=args.component,
        allowFileOverlap=args.allow_file_overlap,
    )
    if not eligible:
        raise AggregateQueueError("No eligible task: " + json.dumps(rejected, ensure_ascii=False))
    return eligible[0].issueName


def main(argv: Sequence[str] | None = None) -> int:
    parser = buildParser()
    args = parser.parse_args(argv)

    if args.command == "controller-id":
        payload = issue_queue.controllerIdentityPayload(args.controller_id, args.worker)
        print(payload["controllerId"] if args.plain else json.dumps(payload, indent=2))
        return 0

    discovery = discoverQueues(args.workbook)
    try:
        if args.command == "workbooks":
            payload = workbookSummary(discovery)
            if args.json:
                printJson(payload)
            else:
                for record in payload["compatible"]:
                    print(f"QUEUE  {record['workbook']}  ({record['issues']} issues)")
                for record in payload["skipped"]:
                    print(f"SKIP   {record['workbook']}  ({record['reason']})")
            return 0 if discovery.queues else 1

        if not discovery.queues:
            printJson({"errors": ["No queue-compatible workbooks were discovered"], "skipped": discovery.skipped})
            return 1

        aggregate = aggregateState(discovery)
        errors, warnings = validateDiscovery(discovery)
        if args.command == "validate":
            printJson(
                {
                    "workbooks": [displayPath(queue.path) for queue in discovery.queues],
                    "skipped": discovery.skipped,
                    "errors": errors,
                    "warnings": warnings,
                }
            )
            return 1 if errors else 0

        if errors:
            raise AggregateQueueError("Aggregate queue validation failed:\n- " + "\n- ".join(errors))

        if args.command == "list":
            statuses = {issue_queue.normalizeStatus(item) for item in args.status} if args.status else None
            tasks = issue_queue.listTasks(aggregate, statuses, args.owner, args.epic)
            if args.json:
                printJson([issue_queue.taskPayload(task, state=aggregate) for task in tasks])
            else:
                issue_queue.printTable(tasks)
            return 0

        if args.command == "show":
            printJson(issue_queue.taskPayload(issue_queue.taskByName(aggregate, args.issue), state=aggregate))
            return 0

        if args.command == "next":
            priorities = {item.upper() for item in args.priority} or None
            eligible, rejected = issue_queue.eligibleTasks(
                aggregate,
                priorities=priorities,
                epic=args.epic,
                component=args.component,
                allowFileOverlap=args.allow_file_overlap,
            )
            if not eligible:
                printJson({"eligible": False, "reason": "No eligible task", "rejected": rejected})
                return 3
            task = eligible[0]
            printJson({"eligible": True, "task": issue_queue.taskPayload(task, state=aggregate)})
            return 0

        if args.command == "shortlist":
            priorities = {item.upper() for item in args.priority} or None
            payload = issue_queue.shortlistTasks(
                aggregate,
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
            printJson(annotateShortlist(payload, discovery))
            return 0

        if args.command == "claim":
            issueName = args.issue or selectedIssueFromAggregate(aggregate, args)
            queue = requireUniqueIssue(discovery, issueName)
            priorities = {item.upper() for item in args.priority} or None
            result = issue_queue.claimTask(
                queue.path,
                owner=args.owner,
                issueName=issueName,
                leaseMinutes=args.lease_minutes,
                priorities=priorities,
                epic=args.epic,
                component=args.component,
                allowFileOverlap=args.allow_file_overlap,
                lockTimeoutSeconds=args.lock_timeout_seconds,
            )
            if args.format == "prompt" and result.get("claimed"):
                refreshed = issue_queue.loadQueue(queue.path, writable=False)
                try:
                    print(f"Queue workbook: {displayPath(queue.path)}\n")
                    print(issue_queue.renderWorkerPrompt(issue_queue.taskByName(refreshed, issueName)))
                finally:
                    refreshed.workbook.close()
            else:
                printJson(addWorkbook(result, queue.path))
            return 0 if result.get("claimed") else 3

        if args.command == "prompt":
            queue = requireUniqueIssue(discovery, args.issue)
            task = issue_queue.requireClaim(queue.state, args.issue, args.claim_id, args.owner)
            print(f"Queue workbook: {displayPath(queue.path)}\n")
            print(issue_queue.renderWorkerPrompt(task))
            return 0

        queue = requireUniqueIssue(discovery, args.issue) if hasattr(args, "issue") else None
        assert queue is not None or args.command == "reclaim-stale"

        if args.command == "heartbeat":
            printJson(
                addWorkbook(
                    issue_queue.heartbeatTask(
                        queue.path,
                        issueName=args.issue,
                        claimId=args.claim_id,
                        owner=args.owner,
                        progress=args.progress,
                        note=args.note,
                        leaseMinutes=args.lease_minutes,
                        lockTimeoutSeconds=args.lock_timeout_seconds,
                    ),
                    queue.path,
                )
            )
            return 0

        if args.command == "complete":
            summary = issue_queue.readTextOption(args.summary, args.summary_file, "summary")
            validation = issue_queue.readTextOption(args.validation, args.validation_file, "validation")
            printJson(
                addWorkbook(
                    issue_queue.finishTask(
                        queue.path,
                        issueName=args.issue,
                        claimId=args.claim_id,
                        owner=args.owner,
                        status=issue_queue.STATUS_DONE,
                        note=args.note,
                        summary=summary,
                        validation=validation,
                        lockTimeoutSeconds=args.lock_timeout_seconds,
                    ),
                    queue.path,
                )
            )
            return 0

        if args.command in {"block", "fail", "cancel"}:
            summary = issue_queue.readTextOption(args.summary, args.summary_file, "summary")
            validation = issue_queue.readTextOption(args.validation, args.validation_file, "validation")
            printJson(
                addWorkbook(
                    issue_queue.finishTask(
                        queue.path,
                        issueName=args.issue,
                        claimId=args.claim_id,
                        owner=args.owner,
                        status=args.targetStatus,
                        note=args.note,
                        summary=summary,
                        validation=validation,
                        lockTimeoutSeconds=args.lock_timeout_seconds,
                    ),
                    queue.path,
                )
            )
            return 0

        if args.command == "release":
            printJson(
                addWorkbook(
                    issue_queue.releaseTask(
                        queue.path,
                        issueName=args.issue,
                        claimId=args.claim_id,
                        owner=args.owner,
                        note=args.note,
                        lockTimeoutSeconds=args.lock_timeout_seconds,
                    ),
                    queue.path,
                )
            )
            return 0

        if args.command == "reclaim-stale":
            records: list[dict[str, Any]] = []
            for item in discovery.queues:
                if args.dry_run:
                    stale = issue_queue.staleClaims(
                        item.state,
                        olderThanMinutes=args.older_than_minutes,
                    )
                    stale = issue_queue.markStaleClaimsForInspection(stale)
                else:
                    stale = issue_queue.reclaimStaleTasks(
                        item.path,
                        olderThanMinutes=args.older_than_minutes,
                        lockTimeoutSeconds=args.lock_timeout_seconds,
                    )
                records.extend(addWorkbook(record, item.path) for record in stale)
            printJson(records)
            return 0

        parser.error(f"Unsupported command: {args.command}")
        return 2
    except (issue_queue.QueueError, OSError, ValueError) as exc:
        print(f"workbook_queue: {exc}", file=sys.stderr)
        return 2
    finally:
        discovery.close()


if __name__ == "__main__":
    raise SystemExit(main())
