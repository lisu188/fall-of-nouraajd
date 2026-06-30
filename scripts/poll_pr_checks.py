#!/usr/bin/env python3
"""Poll selected GitHub Actions jobs for a pull request."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Sequence

try:
    from ci_change_classifier import COVERAGE_PATH_PATTERNS, classifyPaths
except ImportError:  # pragma: no cover - used when imported as scripts.poll_pr_checks
    from scripts.ci_change_classifier import COVERAGE_PATH_PATTERNS, classifyPaths

DEFAULT_LIGHTWEIGHT_JOBS = ("linux",)
DEFAULT_NATIVE_JOBS = ("linux", "windows-deps", "windows")
DEFAULT_WORKFLOW = "build.yml"
DEFAULT_INTERVAL_SECONDS = 30
DEFAULT_TIMEOUT_SECONDS = 7200
SUCCESS_CONCLUSION = "SUCCESS"
COVERAGE_STEP = "coverage"


@dataclass(frozen=True)
class StepRun:
    name: str
    status: str
    conclusion: str


@dataclass(frozen=True)
class JobRun:
    name: str
    status: str
    conclusion: str
    url: str
    steps: tuple[StepRun, ...]


@dataclass(frozen=True)
class CheckEvaluation:
    state: str
    jobs: tuple[JobRun, ...]
    missingJobs: tuple[str, ...]
    missingSteps: tuple[str, ...]
    message: str

    @property
    def succeeded(self) -> bool:
        return self.state == "success"

    @property
    def failed(self) -> bool:
        return self.state == "failure"


class PollError(RuntimeError):
    pass


def normalizeStatus(value: object) -> str:
    return str(value or "").strip().upper()


def stepFromPayload(payload: dict[str, Any]) -> StepRun:
    return StepRun(
        name=str(payload.get("name") or ""),
        status=normalizeStatus(payload.get("status")),
        conclusion=normalizeStatus(payload.get("conclusion")),
    )


def jobFromPayload(payload: dict[str, Any]) -> JobRun:
    steps = tuple(
        stepFromPayload(item) for item in payload.get("steps") or [] if isinstance(item, dict) and item.get("name")
    )
    return JobRun(
        name=str(payload.get("name") or ""),
        status=normalizeStatus(payload.get("status")),
        conclusion=normalizeStatus(payload.get("conclusion")),
        url=str(payload.get("url") or payload.get("html_url") or ""),
        steps=steps,
    )


def jobsFromRunPayload(payload: dict[str, Any]) -> list[JobRun]:
    return [jobFromPayload(item) for item in payload.get("jobs") or [] if isinstance(item, dict) and item.get("name")]


def runStatus(runPayload: dict[str, Any]) -> str:
    return normalizeStatus(runPayload.get("status"))


def selectRunForHead(runs: Sequence[dict[str, Any]], headSha: str) -> dict[str, Any] | None:
    for run in runs:
        if str(run.get("headSha") or "") == headSha:
            return run
    return None


def appendUniqueJob(jobs: list[JobRun], job: JobRun) -> None:
    if not any(existing.name == job.name for existing in jobs):
        jobs.append(job)


def changedPathRequiresCoverage(path: str) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in COVERAGE_PATH_PATTERNS)


def changedFilesRequireCoverage(paths: Sequence[str]) -> bool:
    return any(changedPathRequiresCoverage(path) for path in paths)


def defaultJobsForChangedFiles(paths: Sequence[str]) -> tuple[str, ...]:
    if classifyPaths(paths).nativeNeeded:
        return DEFAULT_NATIVE_JOBS
    return DEFAULT_LIGHTWEIGHT_JOBS


def appendUniqueStep(steps: Sequence[str], step: str) -> tuple[str, ...]:
    normalized = tuple(steps)
    if step in normalized:
        return normalized
    return (*normalized, step)


def evaluateRun(
    runPayload: dict[str, Any] | None,
    requiredJobs: Sequence[str],
    requiredSteps: Sequence[str],
) -> CheckEvaluation:
    if runPayload is None:
        return CheckEvaluation(
            state="pending",
            jobs=(),
            missingJobs=tuple(requiredJobs),
            missingSteps=(),
            message="no matching pull_request workflow run found yet",
        )

    all_jobs = jobsFromRunPayload(runPayload)
    jobs_by_name = {job.name: job for job in all_jobs}
    selected_jobs: list[JobRun] = []
    missing_jobs: list[str] = []
    missing_steps: list[str] = []

    for name in requiredJobs:
        job = jobs_by_name.get(name)
        if job is None:
            missing_jobs.append(name)
        else:
            selected_jobs.append(job)

    if missing_jobs:
        return CheckEvaluation(
            state="pending",
            jobs=tuple(selected_jobs),
            missingJobs=tuple(missing_jobs),
            missingSteps=(),
            message=f"missing job(s): {', '.join(missing_jobs)}",
        )

    failed_jobs = [job for job in selected_jobs if job.status == "COMPLETED" and job.conclusion != SUCCESS_CONCLUSION]
    if failed_jobs:
        names = ", ".join(f"{job.name}={job.conclusion or 'UNKNOWN'}" for job in failed_jobs)
        return CheckEvaluation(
            state="failure",
            jobs=tuple(selected_jobs),
            missingJobs=(),
            missingSteps=(),
            message=f"failed job(s): {names}",
        )

    pending_jobs = [job for job in selected_jobs if job.status != "COMPLETED"]
    if pending_jobs:
        names = ", ".join(f"{job.name}={job.status or 'UNKNOWN'}" for job in pending_jobs)
        return CheckEvaluation(
            state="pending",
            jobs=tuple(selected_jobs),
            missingJobs=(),
            missingSteps=(),
            message=f"pending job(s): {names}",
        )

    display_jobs = list(selected_jobs)
    for step_name in requiredSteps:
        matches = [(job, step) for job in all_jobs for step in job.steps if step.name == step_name]
        if not matches:
            missing_steps.append(step_name)
            continue
        for job, step in matches:
            appendUniqueJob(display_jobs, job)
            if step.status != "COMPLETED":
                return CheckEvaluation(
                    state="pending",
                    jobs=tuple(display_jobs),
                    missingJobs=(),
                    missingSteps=(),
                    message=f"pending step: {job.name}/{step.name}={step.status or 'UNKNOWN'}",
                )
            if step.conclusion != SUCCESS_CONCLUSION:
                return CheckEvaluation(
                    state="failure",
                    jobs=tuple(display_jobs),
                    missingJobs=(),
                    missingSteps=(),
                    message=f"failed step: {job.name}/{step.name}={step.conclusion or 'UNKNOWN'}",
                )
            if job.status != "COMPLETED":
                return CheckEvaluation(
                    state="pending",
                    jobs=tuple(display_jobs),
                    missingJobs=(),
                    missingSteps=(),
                    message=f"pending job with required step: {job.name}={job.status or 'UNKNOWN'}",
                )
            if job.conclusion != SUCCESS_CONCLUSION:
                return CheckEvaluation(
                    state="failure",
                    jobs=tuple(display_jobs),
                    missingJobs=(),
                    missingSteps=(),
                    message=f"failed job with required step: {job.name}={job.conclusion or 'UNKNOWN'}",
                )

    if missing_steps:
        if runStatus(runPayload) != "COMPLETED":
            return CheckEvaluation(
                state="pending",
                jobs=tuple(display_jobs),
                missingJobs=(),
                missingSteps=tuple(missing_steps),
                message=f"missing required step(s) so far: {', '.join(missing_steps)}",
            )
        return CheckEvaluation(
            state="failure",
            jobs=tuple(display_jobs),
            missingJobs=(),
            missingSteps=tuple(missing_steps),
            message=f"missing required step(s): {', '.join(missing_steps)}",
        )

    return CheckEvaluation(
        state="success",
        jobs=tuple(display_jobs),
        missingJobs=(),
        missingSteps=(),
        message=f"successful job(s): {', '.join(requiredJobs)}",
    )


def evaluatePrState(prPayload: dict[str, Any]) -> CheckEvaluation | None:
    state = normalizeStatus(prPayload.get("state"))
    if state == "MERGED":
        merged_at = prPayload.get("mergedAt") or "unknown time"
        merge_commit = prPayload.get("mergeCommit") or {}
        merge_oid = merge_commit.get("oid") if isinstance(merge_commit, dict) else None
        suffix = f" with merge commit {merge_oid}" if merge_oid else ""
        return CheckEvaluation(
            state="success",
            jobs=(),
            missingJobs=(),
            missingSteps=(),
            message=f"pull request already merged at {merged_at}{suffix}",
        )
    if state == "CLOSED":
        return CheckEvaluation(
            state="failure",
            jobs=(),
            missingJobs=(),
            missingSteps=(),
            message="pull request is closed without merge",
        )
    return None


def runGhJson(command: Sequence[str]) -> Any:
    try:
        result = subprocess.run(
            list(command),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise PollError("gh CLI not found on PATH; cannot poll GitHub checks") from exc
    except OSError as exc:
        raise PollError(f"{' '.join(command)} could not be executed: {exc}") from exc
    if result.returncode != 0:
        raise PollError(result.stderr.strip() or result.stdout.strip() or f"{' '.join(command)} failed")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PollError(f"{' '.join(command)} returned invalid JSON: {exc}") from exc


def ghCommandWithRepo(command: list[str], repo: str | None) -> list[str]:
    if repo:
        command.extend(["--repo", repo])
    return command


def runGhPrView(pr: str, repo: str | None) -> dict[str, Any]:
    command = ghCommandWithRepo(
        ["gh", "pr", "view", pr, "--json", "headRefOid,headRefName,number,url,state,mergedAt,mergeCommit"],
        repo,
    )
    payload = runGhJson(command)
    if not isinstance(payload, dict):
        raise PollError("gh pr view returned unexpected JSON")
    if not payload.get("headRefOid"):
        raise PollError("gh pr view did not return headRefOid")
    return payload


def runGhPrFiles(pr: str, repo: str | None) -> tuple[str, ...]:
    command = ghCommandWithRepo(["gh", "pr", "diff", pr, "--name-only"], repo)
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise PollError("gh CLI not found on PATH; cannot poll GitHub checks") from exc
    except OSError as exc:
        raise PollError(f"{' '.join(command)} could not be executed: {exc}") from exc
    if result.returncode != 0:
        raise PollError(result.stderr.strip() or result.stdout.strip() or f"{' '.join(command)} failed")
    return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())


def runGhRunList(headSha: str, workflow: str, repo: str | None) -> list[dict[str, Any]]:
    command = ghCommandWithRepo(
        [
            "gh",
            "run",
            "list",
            "--workflow",
            workflow,
            "--event",
            "pull_request",
            "--commit",
            headSha,
            "--json",
            "databaseId,headSha,status,conclusion,workflowName,url,createdAt,updatedAt",
            "--limit",
            "20",
        ],
        repo,
    )
    payload = runGhJson(command)
    if not isinstance(payload, list):
        raise PollError("gh run list returned unexpected JSON")
    return [item for item in payload if isinstance(item, dict)]


def runGhRunView(runId: object, repo: str | None) -> dict[str, Any]:
    command = ghCommandWithRepo(
        ["gh", "run", "view", str(runId), "--json", "jobs,status,conclusion,url,headSha,workflowName"],
        repo,
    )
    payload = runGhJson(command)
    if not isinstance(payload, dict):
        raise PollError("gh run view returned unexpected JSON")
    return payload


def formatJob(job: JobRun, requiredSteps: Sequence[str]) -> list[str]:
    conclusion = f"/{job.conclusion}" if job.conclusion else ""
    suffix = f" {job.url}" if job.url else ""
    lines = [f"{job.name}: {job.status}{conclusion}{suffix}"]
    if requiredSteps:
        steps_by_name = {step.name: step for step in job.steps}
        for step_name in requiredSteps:
            step = steps_by_name.get(step_name)
            if step is not None:
                step_conclusion = f"/{step.conclusion}" if step.conclusion else ""
                lines.append(f"  {step.name}: {step.status}{step_conclusion}")
    return lines


def printEvaluation(
    prPayload: dict[str, Any],
    runPayload: dict[str, Any] | None,
    evaluation: CheckEvaluation,
    requiredSteps: Sequence[str],
) -> None:
    head = prPayload.get("headRefOid") or "unknown"
    pr_url = prPayload.get("url") or ""
    run_url = (runPayload or {}).get("url") or ""
    print(f"PR head {head} {pr_url}".rstrip())
    if run_url:
        print(f"workflow run {run_url}")
    for job in evaluation.jobs:
        for line in formatJob(job, requiredSteps):
            print(line)
    if evaluation.missingJobs:
        print(f"missing jobs: {', '.join(evaluation.missingJobs)}")
    if evaluation.missingSteps:
        print(f"missing steps: {', '.join(evaluation.missingSteps)}")
    print(evaluation.message)
    sys.stdout.flush()


def pollChecks(
    pr: str,
    repo: str | None,
    workflow: str,
    requiredJobs: Sequence[str] | None,
    requiredSteps: Sequence[str],
    intervalSeconds: int,
    timeoutSeconds: int,
    autoRequireCoverage: bool = True,
) -> CheckEvaluation:
    started = time.monotonic()
    pr_payload = runGhPrView(pr, repo)
    pr_state_evaluation = evaluatePrState(pr_payload)
    if pr_state_evaluation is not None:
        printEvaluation(pr_payload, None, pr_state_evaluation, requiredSteps)
        return pr_state_evaluation
    head_sha = str(pr_payload["headRefOid"])
    effective_steps = tuple(requiredSteps)
    changed_files: tuple[str, ...] = ()
    if requiredJobs is None or (autoRequireCoverage and COVERAGE_STEP not in effective_steps):
        changed_files = runGhPrFiles(pr, repo)
    effective_jobs = tuple(requiredJobs) if requiredJobs is not None else defaultJobsForChangedFiles(changed_files)
    if autoRequireCoverage and COVERAGE_STEP not in effective_steps:
        if changedFilesRequireCoverage(changed_files):
            effective_steps = appendUniqueStep(effective_steps, COVERAGE_STEP)

    while True:
        runs = runGhRunList(head_sha, workflow, repo)
        run_summary = selectRunForHead(runs, head_sha)
        run_payload = runGhRunView(run_summary["databaseId"], repo) if run_summary else None
        evaluation = evaluateRun(run_payload, effective_jobs, effective_steps)
        printEvaluation(pr_payload, run_payload, evaluation, effective_steps)
        if evaluation.succeeded or evaluation.failed:
            return evaluation
        if time.monotonic() - started >= timeoutSeconds:
            return CheckEvaluation(
                state="timeout",
                jobs=evaluation.jobs,
                missingJobs=evaluation.missingJobs,
                missingSteps=evaluation.missingSteps,
                message=f"timed out after {timeoutSeconds}s: {evaluation.message}",
            )
        time.sleep(intervalSeconds)
        latest_pr_payload = runGhPrView(pr, repo)
        pr_state_evaluation = evaluatePrState(latest_pr_payload)
        if pr_state_evaluation is not None:
            printEvaluation(latest_pr_payload, None, pr_state_evaluation, effective_steps)
            return pr_state_evaluation


def positiveInt(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def parseArgs(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pr", help="Pull request number, URL, or branch accepted by gh pr view.")
    parser.add_argument("--repo", help="Repository in OWNER/REPO form. Defaults to the current gh repository.")
    parser.add_argument(
        "--workflow",
        default=DEFAULT_WORKFLOW,
        help=f"Workflow file or name to poll. Defaults to {DEFAULT_WORKFLOW}.",
    )
    parser.add_argument(
        "--check",
        action="append",
        dest="jobs",
        help=(
            "Required job/check name to poll. May be repeated. Defaults to an automatic path-based set: "
            "linux for lightweight PRs, linux/windows-deps/windows for native validation PRs."
        ),
    )
    parser.add_argument(
        "--require-step",
        action="append",
        dest="steps",
        default=[],
        help=(
            "Required step name that must pass somewhere in the selected workflow run. May be repeated. "
            "Coverage is auto-required when PR paths match the build workflow coverage rule."
        ),
    )
    parser.add_argument(
        "--no-auto-require-coverage",
        action="store_true",
        help="Do not auto-require the coverage step when PR paths match the workflow coverage rule.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=positiveInt,
        default=DEFAULT_INTERVAL_SECONDS,
        help=f"Polling interval. Defaults to {DEFAULT_INTERVAL_SECONDS}.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=positiveInt,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Maximum wait. Defaults to {DEFAULT_TIMEOUT_SECONDS}.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parseArgs(sys.argv[1:] if argv is None else argv)
    jobs = tuple(args.jobs) if args.jobs is not None else None
    steps = tuple(args.steps or ())
    try:
        evaluation = pollChecks(
            pr=args.pr,
            repo=args.repo,
            workflow=args.workflow,
            requiredJobs=jobs,
            requiredSteps=steps,
            intervalSeconds=args.interval_seconds,
            timeoutSeconds=args.timeout_seconds,
            autoRequireCoverage=not args.no_auto_require_coverage,
        )
    except PollError as exc:
        print(f"poll_pr_checks: {exc}", file=sys.stderr)
        return 3
    if evaluation.succeeded:
        return 0
    if evaluation.failed:
        return 1
    print(evaluation.message, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
