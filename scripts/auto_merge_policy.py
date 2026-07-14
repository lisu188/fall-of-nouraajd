#!/usr/bin/env python3
"""Fail-closed policy gate for enabling pull-request auto-merge.

This helper is intended to run from a trusted checkout of the repository's
default branch.  It treats the ``workflow_run`` webhook as a pointer only and
refetches every decision-bearing object from the explicitly named repository.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

try:
    from scripts.ci_change_classifier import CI_AUTHORITY_PATH_PATTERNS, matchesAny
except ModuleNotFoundError:  # Direct execution makes scripts/ the import root.
    from ci_change_classifier import CI_AUTHORITY_PATH_PATTERNS, matchesAny


REQUIRED_CONTEXTS = frozenset(("linux", "windows-deps", "windows"))
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
GH_API_TIMEOUT_SECONDS = 30


class EvidenceError(RuntimeError):
    """Evidence is malformed, ambiguous, or could not be verified."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason


class ApiError(EvidenceError):
    def __init__(self, path: str, detail: str) -> None:
        super().__init__("api_error", f"gh api {path}: {detail}")
        self.path = path
        self.detail = detail


@dataclass(frozen=True)
class PolicyResult:
    allow: bool
    prNumber: int | None
    reason: str


JsonGetter = Callable[[str], Any]


def _object(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise EvidenceError("malformed_evidence", f"{name} must be an object")
    return value


def _positiveInteger(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise EvidenceError("malformed_evidence", f"{name} must be a positive integer")
    return value


def _nonEmptyString(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceError("malformed_evidence", f"{name} must be a non-empty string")
    return value


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise EvidenceError("malformed_evidence", f"{name} must be a boolean")
    return value


def _repositoryName(payload: Mapping[str, Any], name: str) -> str:
    repository = _object(payload.get("repository"), f"{name}.repository")
    return _nonEmptyString(repository.get("full_name"), f"{name}.repository.full_name")


def _pullRepositoryName(payload: Mapping[str, Any], name: str) -> str:
    repository = _object(payload.get("repo"), f"{name}.repo")
    return _nonEmptyString(repository.get("full_name"), f"{name}.repo.full_name")


def _sameRepository(actual: str, expected: str) -> bool:
    return actual.casefold() == expected.casefold()


def _associationNumber(payload: Mapping[str, Any], name: str) -> int:
    associations = payload.get("pull_requests")
    if not isinstance(associations, list):
        raise EvidenceError("malformed_evidence", f"{name}.pull_requests must be an array")
    if len(associations) != 1:
        raise EvidenceError(
            "pr_association_count_not_one",
            f"{name}.pull_requests contains {len(associations)} associations",
        )
    association = _object(associations[0], f"{name}.pull_requests[0]")
    return _positiveInteger(association.get("number"), f"{name}.pull_requests[0].number")


def _deny(reason: str, prNumber: int | None = None) -> PolicyResult:
    return PolicyResult(False, prNumber, reason)


class GhApi:
    def get(self, path: str) -> Any:
        try:
            result = subprocess.run(
                ["gh", "api", "--method", "GET", path],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=GH_API_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise ApiError(path, f"timed out after {GH_API_TIMEOUT_SECONDS} seconds") from exc
        except OSError as exc:
            raise ApiError(path, str(exc)) from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            raise ApiError(path, detail)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ApiError(path, f"invalid JSON: {exc}") from exc


def _changedPaths(getJson: JsonGetter, repository: str, prNumber: int, expectedCount: int) -> tuple[str, ...]:
    """Fetch all changed paths and include both sides of renames."""
    if expectedCount < 0:
        raise EvidenceError("malformed_evidence", "pull_request.changed_files must not be negative")

    paths: list[str] = []
    fileCount = 0
    page = 1
    while True:
        payload = getJson(f"repos/{repository}/pulls/{prNumber}/files?per_page=100&page={page}")
        if not isinstance(payload, list):
            raise EvidenceError("malformed_evidence", "pull request files response must be an array")
        fileCount += len(payload)
        for index, item in enumerate(payload):
            changedFile = _object(item, f"pull request file {index}")
            paths.append(_nonEmptyString(changedFile.get("filename"), "pull request file filename"))
            previous = changedFile.get("previous_filename")
            if previous is not None:
                paths.append(_nonEmptyString(previous, "pull request file previous_filename"))
        if len(payload) < 100:
            break
        page += 1
        if page > 31:
            raise EvidenceError("changed_files_unverifiable", "pull request file pagination exceeded 3000 files")

    if fileCount != expectedCount:
        raise EvidenceError(
            "changed_files_count_mismatch",
            f"pull request reports {expectedCount} changed files but API returned {fileCount}",
        )
    return tuple(paths)


def _requiredContexts(protection: Mapping[str, Any]) -> frozenset[str]:
    statusChecks = protection.get("required_status_checks")
    if not isinstance(statusChecks, dict):
        return frozenset()
    contexts = statusChecks.get("contexts")
    checks = statusChecks.get("checks")
    if not isinstance(contexts, list) or not isinstance(checks, list):
        raise EvidenceError("malformed_evidence", "branch protection required status checks are malformed")

    required: set[str] = set()
    for context in contexts:
        required.add(_nonEmptyString(context, "required status context"))
    for index, check in enumerate(checks):
        item = _object(check, f"required status check {index}")
        required.add(_nonEmptyString(item.get("context"), f"required status check {index}.context"))
    return frozenset(required)


def evaluatePolicy(event: Mapping[str, Any], repository: str, getJson: JsonGetter) -> PolicyResult:
    if not REPOSITORY_PATTERN.fullmatch(repository):
        raise EvidenceError("invalid_repository", "--repository must be OWNER/REPO")

    eventAction = _nonEmptyString(event.get("action"), "event.action")
    if eventAction != "completed":
        return _deny("workflow_not_completed")
    eventRepository = _repositoryName(event, "event")
    if not _sameRepository(eventRepository, repository):
        return _deny("event_repository_mismatch")

    eventRun = _object(event.get("workflow_run"), "event.workflow_run")
    runId = _positiveInteger(eventRun.get("id"), "event.workflow_run.id")
    eventPrNumber = _associationNumber(eventRun, "event.workflow_run")
    eventHeadSha = _nonEmptyString(eventRun.get("head_sha"), "event.workflow_run.head_sha")
    if not _sameRepository(_repositoryName(eventRun, "event.workflow_run"), repository):
        return _deny("event_repository_mismatch", eventPrNumber)

    run = _object(getJson(f"repos/{repository}/actions/runs/{runId}"), "workflow run")
    if _positiveInteger(run.get("id"), "workflow_run.id") != runId:
        raise EvidenceError("workflow_identity_unverifiable", "refetched workflow run ID differs")
    if _associationNumber(run, "workflow_run") != eventPrNumber:
        raise EvidenceError("workflow_identity_unverifiable", "refetched pull request association differs")
    runHeadSha = _nonEmptyString(run.get("head_sha"), "workflow_run.head_sha")
    if runHeadSha != eventHeadSha:
        raise EvidenceError("workflow_identity_unverifiable", "refetched workflow head SHA differs")
    if not _sameRepository(_repositoryName(run, "workflow_run"), repository):
        return _deny("workflow_repository_mismatch", eventPrNumber)
    runName = _nonEmptyString(run.get("name"), "workflow_run.name")
    runPath = _nonEmptyString(run.get("path"), "workflow_run.path")
    if runName != "build" or runPath != ".github/workflows/build.yml":
        return _deny("workflow_identity_mismatch", eventPrNumber)
    runStatus = _nonEmptyString(run.get("status"), "workflow_run.status")
    if runStatus != "completed":
        return _deny("workflow_not_completed", eventPrNumber)
    runConclusion = _nonEmptyString(run.get("conclusion"), "workflow_run.conclusion")
    if runConclusion != "success":
        return _deny("workflow_not_successful", eventPrNumber)
    runEvent = _nonEmptyString(run.get("event"), "workflow_run.event")
    if runEvent != "pull_request":
        return _deny("workflow_event_not_pull_request", eventPrNumber)

    pr = _object(getJson(f"repos/{repository}/pulls/{eventPrNumber}"), "pull request")
    if _positiveInteger(pr.get("number"), "pull_request.number") != eventPrNumber:
        raise EvidenceError("pull_request_unverifiable", "refetched pull request number differs")
    prState = _nonEmptyString(pr.get("state"), "pull_request.state")
    if prState != "open":
        return _deny("pr_not_open", eventPrNumber)
    if _boolean(pr.get("draft"), "pull_request.draft"):
        return _deny("pr_is_draft", eventPrNumber)

    base = _object(pr.get("base"), "pull_request.base")
    head = _object(pr.get("head"), "pull_request.head")
    baseRef = _nonEmptyString(base.get("ref"), "pull_request.base.ref")
    if baseRef != "main":
        return _deny("pr_base_not_main", eventPrNumber)
    if not _sameRepository(_pullRepositoryName(base, "pull_request.base"), repository):
        return _deny("pr_base_repository_mismatch", eventPrNumber)
    if not _sameRepository(_pullRepositoryName(head, "pull_request.head"), repository):
        return _deny("pr_head_repository_mismatch", eventPrNumber)
    if _nonEmptyString(head.get("sha"), "pull_request.head.sha") != runHeadSha:
        return _deny("pr_head_sha_mismatch", eventPrNumber)

    changedFiles = pr.get("changed_files")
    if isinstance(changedFiles, bool) or not isinstance(changedFiles, int):
        raise EvidenceError("malformed_evidence", "pull_request.changed_files must be an integer")
    changedPaths = _changedPaths(getJson, repository, eventPrNumber, changedFiles)
    if any(matchesAny(path, CI_AUTHORITY_PATH_PATTERNS) for path in changedPaths):
        return _deny("authority_change", eventPrNumber)

    repositorySettings = _object(getJson(f"repos/{repository}"), "repository settings")
    if not _sameRepository(_nonEmptyString(repositorySettings.get("full_name"), "repository.full_name"), repository):
        raise EvidenceError("repository_settings_unverifiable", "repository settings identity differs")
    try:
        defaultBranch = _nonEmptyString(repositorySettings.get("default_branch"), "repository.default_branch")
    except EvidenceError as exc:
        raise EvidenceError("repository_settings_unverifiable", str(exc)) from exc
    if defaultBranch != "main":
        return _deny("default_branch_not_main", eventPrNumber)
    try:
        allowAutoMerge = _boolean(repositorySettings.get("allow_auto_merge"), "repository.allow_auto_merge")
    except EvidenceError as exc:
        raise EvidenceError("repository_settings_unverifiable", str(exc)) from exc
    if not allowAutoMerge:
        return _deny("auto_merge_disabled", eventPrNumber)

    branch = _object(getJson(f"repos/{repository}/branches/main"), "main branch")
    if branch.get("name") != "main":
        raise EvidenceError("branch_protection_unverifiable", "main branch identity differs")
    try:
        protected = _boolean(branch.get("protected"), "main.protected")
    except EvidenceError as exc:
        raise EvidenceError("branch_protection_unverifiable", str(exc)) from exc
    if not protected:
        return _deny("main_not_protected", eventPrNumber)

    protection = _object(getJson(f"repos/{repository}/branches/main/protection"), "main branch protection")
    if "required_status_checks" not in protection:
        raise EvidenceError("branch_protection_unverifiable", "required_status_checks is missing")
    statusChecks = protection["required_status_checks"]
    if statusChecks is None:
        return _deny("required_checks_not_strict", eventPrNumber)
    if not isinstance(statusChecks, dict):
        raise EvidenceError("branch_protection_unverifiable", "required_status_checks must be an object")
    try:
        strict = _boolean(statusChecks.get("strict"), "required_status_checks.strict")
    except EvidenceError as exc:
        raise EvidenceError("branch_protection_unverifiable", str(exc)) from exc
    if not strict:
        return _deny("required_checks_not_strict", eventPrNumber)
    missing = REQUIRED_CONTEXTS - _requiredContexts(protection)
    if missing:
        return _deny("required_contexts_missing", eventPrNumber)

    return PolicyResult(True, eventPrNumber, "allowed")


def writeGithubOutput(path: Path, result: PolicyResult) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"allow={str(result.allow).lower()}\n")
        handle.write(f"pr_number={result.prNumber or ''}\n")
        handle.write(f"reason={result.reason}\n")


def parseArgs(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", required=True, help="Path to the workflow_run event JSON")
    parser.add_argument("--repository", required=True, help="Explicit OWNER/REPO repository")
    parser.add_argument("--github-output", required=True, help="GitHub Actions output file")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parseArgs(argv or sys.argv[1:])
    result = PolicyResult(False, None, "malformed_event")
    exitCode = 2
    try:
        with Path(args.event).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise EvidenceError("malformed_event", "event must be an object")
        event = payload
        result = evaluatePolicy(event, args.repository, GhApi().get)
        exitCode = 0
    except (OSError, json.JSONDecodeError) as exc:
        print(f"auto_merge_policy: event could not be read: {exc}", file=sys.stderr)
    except EvidenceError as exc:
        result = PolicyResult(False, None, exc.reason)
        print(f"auto_merge_policy: {exc}", file=sys.stderr)

    try:
        writeGithubOutput(Path(args.github_output), result)
    except OSError as exc:
        print(f"auto_merge_policy: output could not be written: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"allow": result.allow, "pr_number": result.prNumber, "reason": result.reason}, sort_keys=True))
    return exitCode


if __name__ == "__main__":
    raise SystemExit(main())
