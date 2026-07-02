#!/usr/bin/env python3
"""Read-only repository, disk, and worktree resource audit for controller workflows.

The default invocation stays a read-only audit and its JSON fields are stable; the shared
local-resource broker (``scripts/resource_broker.py``) is exposed through the additive
``probe``/``reserve``/``renew``/``release``/``recover``/``list`` subcommands and through
the additive ``resources`` key in the audit JSON payload.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

try:
    from scripts import resource_broker
except ModuleNotFoundError:  # Support `python3 scripts/controller_resource_audit.py`.
    import resource_broker

BROKER_COMMANDS = ("probe", "reserve", "renew", "release", "recover", "list")
DEFAULT_RUN_TREE_PATTERNS = ("nouraajd-*", "fall-of-nouraajd-codex", "fon-workflow-optimizer-*")
DEFAULT_MIN_FREE_GIB = 5.0
DEFAULT_MAX_USED_PERCENT = 95.0
DEFAULT_PROTECTED_BRANCH = "main"
DEFAULT_REQUIRED_STATUS_CHECKS = ("linux", "windows-deps", "windows")
DEFAULT_LIVE_REMOTE_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class DiskReport:
    path: str
    totalBytes: int
    usedBytes: int
    freeBytes: int

    @property
    def usedPercent(self) -> float:
        if self.totalBytes <= 0:
            return 0.0
        return self.usedBytes * 100.0 / self.totalBytes


@dataclass(frozen=True)
class WorktreeRecord:
    path: str
    head: str | None = None
    branch: str | None = None
    detached: bool = False
    prunable: str | None = None


@dataclass(frozen=True)
class RunTreeRecord:
    path: str
    sizeBytes: int
    sizeMeasured: bool = True


@dataclass(frozen=True)
class GitHealthReport:
    statusExitCode: int
    statusStdout: str
    statusStderr: str
    head: str | None
    originMain: str | None
    gitCommonDir: str | None
    emptyLooseObjects: tuple[str, ...]
    emptyRefs: tuple[str, ...]
    headAheadOriginMainCount: int | None = None
    headBehindOriginMainCount: int | None = None
    headBehindOriginMain: bool | None = None
    liveOriginMain: str | None = None
    liveOriginMainError: str | None = None
    originMainMatchesLive: bool | None = None


@dataclass(frozen=True)
class BranchProtectionReport:
    repo: str
    branch: str
    protected: bool | None
    requiredChecks: tuple[str, ...]
    expectedChecks: tuple[str, ...]
    missingRequiredChecks: tuple[str, ...]
    error: str | None = None


@dataclass(frozen=True)
class MergePolicyReport:
    repo: str
    allowAutoMerge: bool | None
    deleteBranchOnMerge: bool | None
    error: str | None = None


def bytesToGib(value: int) -> float:
    return value / (1024.0**3)


def formatBytes(value: int) -> str:
    gib = bytesToGib(value)
    if gib >= 1.0:
        return f"{gib:.1f} GiB"
    mib = value / (1024.0**2)
    return f"{mib:.1f} MiB"


def diskReport(path: Path) -> DiskReport:
    usage = shutil.disk_usage(path)
    return DiskReport(
        path=str(path),
        totalBytes=usage.total,
        usedBytes=usage.used,
        freeBytes=usage.free,
    )


def evaluateDiskReports(
    reports: Sequence[DiskReport],
    minFreeBytes: int,
    maxUsedPercent: float,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for report in reports:
        if report.freeBytes < minFreeBytes:
            errors.append(
                f"{report.path}: free disk {formatBytes(report.freeBytes)} is below required "
                f"{formatBytes(minFreeBytes)}"
            )
        if report.usedPercent > maxUsedPercent:
            errors.append(f"{report.path}: disk usage {report.usedPercent:.1f}% exceeds limit {maxUsedPercent:.1f}%")
        elif report.usedPercent > maxUsedPercent - 5:
            warnings.append(f"{report.path}: disk usage {report.usedPercent:.1f}% is near limit {maxUsedPercent:.1f}%")
    return errors, warnings


def parseWorktreePorcelain(text: str) -> list[WorktreeRecord]:
    records: list[WorktreeRecord] = []
    current: dict[str, Any] | None = None

    def flushCurrent() -> None:
        nonlocal current
        if current is None:
            return
        records.append(
            WorktreeRecord(
                path=current["path"],
                head=current.get("head"),
                branch=current.get("branch"),
                detached=bool(current.get("detached")),
                prunable=current.get("prunable"),
            )
        )
        current = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            flushCurrent()
            current = {"path": value}
        elif current is None:
            continue
        elif key == "HEAD":
            current["head"] = value
        elif key == "branch":
            current["branch"] = value
        elif key == "detached":
            current["detached"] = True
        elif key == "prunable":
            current["prunable"] = value
    flushCurrent()
    return records


def worktreeSummary(records: Sequence[WorktreeRecord]) -> dict[str, Any]:
    prunable = [record for record in records if record.prunable]
    active = [record for record in records if not record.prunable]
    return {
        "total": len(records),
        "active": len(active),
        "prunable": len(prunable),
        "prunableRecords": [worktreePayload(record) for record in prunable],
    }


def worktreePayload(record: WorktreeRecord) -> dict[str, Any]:
    return {
        "path": record.path,
        "head": record.head,
        "branch": record.branch,
        "detached": record.detached,
        "prunable": record.prunable,
    }


def runGitWorktreeList(repoRoot: Path) -> list[WorktreeRecord]:
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repoRoot,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return parseWorktreePorcelain(result.stdout)


def runGit(
    repoRoot: Path,
    args: Sequence[str],
    *,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "--no-optional-locks", *args],
        cwd=repoRoot,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )


def runGitLiveOriginMain(
    repoRoot: Path, timeoutSeconds: float = DEFAULT_LIVE_REMOTE_TIMEOUT_SECONDS
) -> tuple[str | None, str | None]:
    remote = runGit(repoRoot, ["remote", "get-url", "origin"])
    if remote.returncode != 0:
        return None, None
    try:
        result = runGit(
            repoRoot,
            ["ls-remote", "--exit-code", "origin", "refs/heads/main"],
            timeout=timeoutSeconds,
        )
    except subprocess.TimeoutExpired:
        return None, f"git ls-remote origin refs/heads/main timed out after {timeoutSeconds:.1f}s"
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "git ls-remote failed"
        return None, detail

    parts = result.stdout.strip().split()
    if len(parts) < 2 or parts[1] != "refs/heads/main":
        return None, "git ls-remote origin refs/heads/main returned unexpected output"
    return parts[0], None


def resolveGitPath(repoRoot: Path, pathText: str | None) -> Path | None:
    if not pathText:
        return None
    path = Path(pathText.strip())
    if not path.is_absolute():
        path = repoRoot / path
    return path.resolve()


def findEmptyLooseObjects(gitCommonDir: Path | None) -> tuple[str, ...]:
    if gitCommonDir is None:
        return ()
    objectsDir = gitCommonDir / "objects"
    if not objectsDir.is_dir():
        return ()

    emptyObjects: list[str] = []
    for prefixDir in objectsDir.iterdir():
        if not prefixDir.is_dir() or len(prefixDir.name) != 2:
            continue
        for objectPath in prefixDir.iterdir():
            try:
                if objectPath.is_file() and objectPath.stat().st_size == 0:
                    emptyObjects.append(str(objectPath.relative_to(objectsDir)))
            except OSError:
                continue
    return tuple(sorted(emptyObjects))


def findEmptyRefs(gitCommonDir: Path | None) -> tuple[str, ...]:
    if gitCommonDir is None:
        return ()
    refsDir = gitCommonDir / "refs"
    if not refsDir.is_dir():
        return ()

    emptyRefs: list[str] = []
    for refPath in refsDir.rglob("*"):
        try:
            if refPath.is_file() and refPath.stat().st_size == 0:
                emptyRefs.append(str(refPath.relative_to(gitCommonDir)))
        except OSError:
            continue
    return tuple(sorted(emptyRefs))


def runGitHealth(repoRoot: Path) -> GitHealthReport:
    status = runGit(repoRoot, ["status", "--short", "--branch"])
    head = runGit(repoRoot, ["rev-parse", "--verify", "HEAD"])
    originMain = runGit(repoRoot, ["rev-parse", "--verify", "refs/remotes/origin/main"])
    commonDir = runGit(repoRoot, ["rev-parse", "--git-common-dir"])
    gitCommonDir = resolveGitPath(repoRoot, commonDir.stdout.strip()) if commonDir.returncode == 0 else None
    headText = head.stdout.strip() if head.returncode == 0 else None
    originMainText = originMain.stdout.strip() if originMain.returncode == 0 else None
    headAheadOriginMainCount: int | None = None
    headBehindOriginMainCount: int | None = None
    headBehindOriginMain: bool | None = None
    liveOriginMainText, liveOriginMainError = runGitLiveOriginMain(repoRoot)
    originMainMatchesLive: bool | None = None
    if liveOriginMainText and originMainText:
        originMainMatchesLive = originMainText == liveOriginMainText
    if headText and originMainText:
        if headText == originMainText:
            headAheadOriginMainCount = 0
            headBehindOriginMainCount = 0
            headBehindOriginMain = False
        else:
            revList = runGit(repoRoot, ["rev-list", "--left-right", "--count", "HEAD...refs/remotes/origin/main"])
            if revList.returncode == 0:
                parts = revList.stdout.strip().split()
                if len(parts) == 2:
                    try:
                        headAheadOriginMainCount = int(parts[0])
                        headBehindOriginMainCount = int(parts[1])
                        headBehindOriginMain = headBehindOriginMainCount > 0
                    except ValueError:
                        pass

    return GitHealthReport(
        statusExitCode=status.returncode,
        statusStdout=status.stdout.strip(),
        statusStderr=status.stderr.strip(),
        head=headText,
        originMain=originMainText,
        liveOriginMain=liveOriginMainText,
        liveOriginMainError=liveOriginMainError,
        originMainMatchesLive=originMainMatchesLive,
        gitCommonDir=str(gitCommonDir) if gitCommonDir is not None else None,
        emptyLooseObjects=findEmptyLooseObjects(gitCommonDir),
        emptyRefs=findEmptyRefs(gitCommonDir),
        headAheadOriginMainCount=headAheadOriginMainCount,
        headBehindOriginMainCount=headBehindOriginMainCount,
        headBehindOriginMain=headBehindOriginMain,
    )


def statusReportsBehindOriginMain(statusStdout: str) -> bool:
    _, marker, remainder = statusStdout.partition("[")
    if not marker:
        return False
    details, _, _ = remainder.partition("]")
    return any(part.strip().startswith("behind ") for part in details.split(","))


def evaluateGitHealth(report: GitHealthReport) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if report.statusExitCode != 0:
        detail = report.statusStderr or report.statusStdout or "no git status output"
        errors.append(f"git status failed with exit code {report.statusExitCode}: {detail}")
    if not report.head:
        errors.append("HEAD could not be resolved")
    if not report.originMain:
        errors.append("refs/remotes/origin/main could not be resolved")
    if report.emptyLooseObjects:
        errors.append(f"{len(report.emptyLooseObjects)} zero-byte loose git object(s) found")
    if report.emptyRefs:
        errors.append(f"{len(report.emptyRefs)} zero-byte git ref file(s) found")
    if report.liveOriginMainError:
        warnings.append(f"live origin/main could not be inspected: {report.liveOriginMainError}")
    if report.originMainMatchesLive is False:
        warnings.append(
            "refs/remotes/origin/main differs from live origin/main; fetch before continuing because local "
            "remote-tracking refs may be stale"
        )
    if report.headBehindOriginMain or (
        report.headBehindOriginMain is None
        and report.head
        and report.originMain
        and report.head != report.originMain
        and statusReportsBehindOriginMain(report.statusStdout)
    ):
        detail = ""
        if report.headBehindOriginMainCount is not None:
            detail = f" by {report.headBehindOriginMainCount} commit(s)"
        warnings.append(
            f"HEAD is missing refs/remotes/origin/main commit(s){detail}; "
            "fetch/rebase or recreate the controller checkout from latest origin/main before continuing"
        )
    return errors, warnings


def runGhApiJson(path: str) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["gh", "api", path],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("gh CLI not found on PATH; cannot query GitHub metadata") from exc
    except OSError as exc:
        raise RuntimeError(f"gh api {path} could not be executed: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "gh api failed"
        raise RuntimeError(detail)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"gh api {path} returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"gh api {path} returned unexpected JSON")
    return payload


def requiredChecksFromProtectionPayload(payload: dict[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(payload, dict):
        return ()
    statusChecks = payload.get("required_status_checks")
    if not isinstance(statusChecks, dict):
        return ()

    checks: list[str] = []
    contexts = statusChecks.get("contexts")
    if isinstance(contexts, list):
        checks.extend(str(item) for item in contexts if item)

    richChecks = statusChecks.get("checks")
    if isinstance(richChecks, list):
        for item in richChecks:
            if isinstance(item, dict) and item.get("context"):
                checks.append(str(item["context"]))
    return tuple(sorted(dict.fromkeys(checks)))


def branchProtectionReportFromPayloads(
    repo: str,
    branch: str,
    expectedChecks: Sequence[str],
    branchPayload: dict[str, Any],
    protectionPayload: dict[str, Any] | None,
) -> BranchProtectionReport:
    protected = bool(branchPayload.get("protected"))
    requiredChecks = requiredChecksFromProtectionPayload(protectionPayload) if protected else ()
    missingChecks = tuple(check for check in expectedChecks if check not in requiredChecks)
    return BranchProtectionReport(
        repo=repo,
        branch=branch,
        protected=protected,
        requiredChecks=requiredChecks,
        expectedChecks=tuple(expectedChecks),
        missingRequiredChecks=missingChecks,
    )


def auditBranchProtection(repo: str, branch: str, expectedChecks: Sequence[str]) -> BranchProtectionReport:
    try:
        branchPayload = runGhApiJson(f"repos/{repo}/branches/{branch}")
    except RuntimeError as exc:
        return BranchProtectionReport(
            repo=repo,
            branch=branch,
            protected=None,
            requiredChecks=(),
            expectedChecks=tuple(expectedChecks),
            missingRequiredChecks=tuple(expectedChecks),
            error=str(exc),
        )

    protectionPayload: dict[str, Any] | None = None
    if branchPayload.get("protected"):
        try:
            protectionPayload = runGhApiJson(f"repos/{repo}/branches/{branch}/protection")
        except RuntimeError as exc:
            return BranchProtectionReport(
                repo=repo,
                branch=branch,
                protected=True,
                requiredChecks=(),
                expectedChecks=tuple(expectedChecks),
                missingRequiredChecks=tuple(expectedChecks),
                error=str(exc),
            )
    return branchProtectionReportFromPayloads(repo, branch, expectedChecks, branchPayload, protectionPayload)


def evaluateBranchProtection(report: BranchProtectionReport | None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if report is None:
        return errors, warnings
    if report.error:
        warnings.append(f"{report.repo}:{report.branch}: branch protection could not be inspected: {report.error}")
        return errors, warnings
    if report.protected is False:
        warnings.append(
            f"{report.repo}:{report.branch}: branch is not protected; expected required checks "
            f"{', '.join(report.expectedChecks)}"
        )
    elif report.missingRequiredChecks:
        warnings.append(
            f"{report.repo}:{report.branch}: branch protection missing required check(s): "
            f"{', '.join(report.missingRequiredChecks)}"
        )
    return errors, warnings


def mergePolicyReportFromPayload(repo: str, payload: dict[str, Any]) -> MergePolicyReport:
    allowAutoMerge = payload.get("allow_auto_merge")
    deleteBranchOnMerge = payload.get("delete_branch_on_merge")
    return MergePolicyReport(
        repo=repo,
        allowAutoMerge=allowAutoMerge if isinstance(allowAutoMerge, bool) else None,
        deleteBranchOnMerge=deleteBranchOnMerge if isinstance(deleteBranchOnMerge, bool) else None,
    )


def auditMergePolicy(repo: str) -> MergePolicyReport:
    try:
        return mergePolicyReportFromPayload(repo, runGhApiJson(f"repos/{repo}"))
    except RuntimeError as exc:
        return MergePolicyReport(repo=repo, allowAutoMerge=None, deleteBranchOnMerge=None, error=str(exc))


def evaluateMergePolicy(report: MergePolicyReport | None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if report is None:
        return errors, warnings
    if report.error:
        warnings.append(f"{report.repo}: repository merge policy could not be inspected: {report.error}")
        return errors, warnings
    if report.allowAutoMerge is False:
        warnings.append(
            f"{report.repo}: repository auto-merge is disabled; gh pr merge --auto will fail until settings change "
            "or explicit alternate merge authorization is recorded"
        )
    elif report.allowAutoMerge is None:
        warnings.append(f"{report.repo}: repository auto-merge setting is missing from GitHub metadata")
    return errors, warnings


def branchProtectionPayload(report: BranchProtectionReport | None) -> dict[str, Any] | None:
    if report is None:
        return None
    return {
        "repo": report.repo,
        "branch": report.branch,
        "protected": report.protected,
        "requiredChecks": list(report.requiredChecks),
        "expectedChecks": list(report.expectedChecks),
        "missingRequiredChecks": list(report.missingRequiredChecks),
        "error": report.error,
    }


def mergePolicyPayload(report: MergePolicyReport | None) -> dict[str, Any] | None:
    if report is None:
        return None
    return {
        "repo": report.repo,
        "allowAutoMerge": report.allowAutoMerge,
        "deleteBranchOnMerge": report.deleteBranchOnMerge,
        "error": report.error,
    }


def directorySize(path: Path) -> int:
    total = 0
    for root, dirs, files in os.walk(path, topdown=True):
        dirs[:] = [name for name in dirs if not Path(root, name).is_symlink()]
        for name in files:
            file_path = Path(root, name)
            try:
                if not file_path.is_symlink():
                    total += file_path.stat().st_size
            except OSError:
                continue
    return total


def matchesRunTreePattern(name: str, patterns: Sequence[str] | str) -> bool:
    if isinstance(patterns, str):
        patterns = [patterns]
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def discoverRunTrees(
    roots: Sequence[Path], patterns: Sequence[str] | str, includeSizes: bool = True
) -> list[RunTreeRecord]:
    records: list[RunTreeRecord] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for entry in root.iterdir():
            try:
                resolved = entry.resolve()
            except OSError:
                continue
            if resolved in seen or not entry.is_dir() or entry.is_symlink():
                continue
            if matchesRunTreePattern(entry.name, patterns):
                seen.add(resolved)
                if includeSizes:
                    records.append(RunTreeRecord(path=str(entry), sizeBytes=directorySize(entry)))
                else:
                    records.append(RunTreeRecord(path=str(entry), sizeBytes=0, sizeMeasured=False))
    return sorted(records, key=lambda record: record.path)


def payload(
    repoRoot: Path,
    gitHealth: GitHealthReport,
    diskReports: Sequence[DiskReport],
    worktrees: Sequence[WorktreeRecord],
    runTrees: Sequence[RunTreeRecord],
    runTreeSizesMeasured: bool,
    branchProtection: BranchProtectionReport | None,
    errors: Sequence[str],
    warnings: Sequence[str],
    mergePolicy: MergePolicyReport | None = None,
    resources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "repoRoot": str(repoRoot),
        "git": {
            "statusExitCode": gitHealth.statusExitCode,
            "statusStdout": gitHealth.statusStdout,
            "statusStderr": gitHealth.statusStderr,
            "head": gitHealth.head,
            "originMain": gitHealth.originMain,
            "liveOriginMain": gitHealth.liveOriginMain,
            "liveOriginMainError": gitHealth.liveOriginMainError,
            "originMainMatchesLive": gitHealth.originMainMatchesLive,
            "headAheadOriginMainCount": gitHealth.headAheadOriginMainCount,
            "headBehindOriginMainCount": gitHealth.headBehindOriginMainCount,
            "headBehindOriginMain": gitHealth.headBehindOriginMain,
            "gitCommonDir": gitHealth.gitCommonDir,
            "emptyLooseObjects": {
                "total": len(gitHealth.emptyLooseObjects),
                "records": list(gitHealth.emptyLooseObjects),
            },
            "emptyRefs": {
                "total": len(gitHealth.emptyRefs),
                "records": list(gitHealth.emptyRefs),
            },
        },
        "disk": [
            {
                "path": report.path,
                "totalBytes": report.totalBytes,
                "usedBytes": report.usedBytes,
                "freeBytes": report.freeBytes,
                "usedPercent": round(report.usedPercent, 1),
                "freeHuman": formatBytes(report.freeBytes),
            }
            for report in diskReports
        ],
        "worktrees": worktreeSummary(worktrees),
        "runTrees": {
            "total": len(runTrees),
            "totalBytes": sum(record.sizeBytes for record in runTrees),
            "sizesMeasured": runTreeSizesMeasured,
            "records": [
                {
                    "path": record.path,
                    "sizeBytes": record.sizeBytes,
                    "sizeHuman": formatBytes(record.sizeBytes),
                    "sizeMeasured": record.sizeMeasured,
                }
                for record in runTrees
            ],
        },
        "branchProtection": branchProtectionPayload(branchProtection),
        "mergePolicy": mergePolicyPayload(mergePolicy),
        "resources": resources,
        "errors": list(errors),
        "warnings": list(warnings),
    }


def evaluateResourceObservation(resources: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not resources:
        return errors, warnings
    reservations = resources.get("reservations") or {}
    if reservations.get("error"):
        warnings.append(f"resource reservation store could not be inspected: {reservations['error']}")
    elif reservations.get("expiredActive"):
        warnings.append(
            f"{reservations['expiredActive']} expired ACTIVE resource reservation(s); recover them with "
            "controller_resource_audit.py recover (record-lifecycle-only; nothing is deleted or killed)"
        )
    return errors, warnings


def printHuman(report: dict[str, Any]) -> None:
    print(f"Repository: {report['repoRoot']}")
    git = report["git"]
    print("Git:")
    print(f"  status exit code: {git['statusExitCode']}")
    print(f"  HEAD: {git['head'] or 'unresolved'}")
    print(f"  origin/main: {git['originMain'] or 'unresolved'}")
    print(f"  live origin/main: {git['liveOriginMain'] or 'unavailable'}")
    print(f"  zero-byte loose objects: {git['emptyLooseObjects']['total']}")
    print(f"  zero-byte refs: {git['emptyRefs']['total']}")
    print("Disk:")
    for item in report["disk"]:
        print(f"  {item['path']}: {item['freeHuman']} free, " f"{item['usedPercent']:.1f}% used")
    worktrees = report["worktrees"]
    print(f"Worktrees: {worktrees['active']} active, " f"{worktrees['prunable']} prunable, {worktrees['total']} total")
    runTrees = report["runTrees"]
    if runTrees["sizesMeasured"]:
        print(f"Run trees: {runTrees['total']} matching, " f"{formatBytes(runTrees['totalBytes'])} total")
    else:
        print(f"Run trees: {runTrees['total']} matching, sizes not measured")
    resources = report.get("resources")
    if resources:
        reservations = resources.get("reservations") or {}
        print(
            f"Resources: {len(resources.get('probes') or [])} probe(s), "
            f"{reservations.get('active')} active reservation(s), {reservations.get('expiredActive')} expired"
        )
    branchProtection = report.get("branchProtection")
    if branchProtection:
        protected = branchProtection["protected"]
        protectedText = "unknown" if protected is None else str(protected).lower()
        print(
            f"Branch protection: {branchProtection['repo']}:{branchProtection['branch']} "
            f"protected={protectedText}, missing checks={branchProtection['missingRequiredChecks']}"
        )
    mergePolicy = report.get("mergePolicy")
    if mergePolicy:
        allowAutoMerge = mergePolicy["allowAutoMerge"]
        allowText = "unknown" if allowAutoMerge is None else str(allowAutoMerge).lower()
        print(f"Merge policy: {mergePolicy['repo']} allow_auto_merge={allowText}")
    for warning in report["warnings"]:
        print(f"WARNING: {warning}")
    for error in report["errors"]:
        print(f"ERROR: {error}", file=sys.stderr)


def buildParser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Repository root to inspect.")
    parser.add_argument(
        "--disk-path",
        action="append",
        default=[],
        help="Additional path whose filesystem usage should be audited.",
    )
    parser.add_argument(
        "--run-tree-root",
        action="append",
        default=[],
        help="Directory containing controller run/worktrees. Defaults to /tmp.",
    )
    parser.add_argument(
        "--run-tree-pattern",
        action="append",
        default=None,
        help=(
            "Glob for controller run/worktree directory names. May be repeated. Defaults to "
            f"{', '.join(DEFAULT_RUN_TREE_PATTERNS)}."
        ),
    )
    parser.add_argument("--min-free-gib", type=float, default=DEFAULT_MIN_FREE_GIB)
    parser.add_argument("--max-used-percent", type=float, default=DEFAULT_MAX_USED_PERCENT)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--skip-run-tree-sizes",
        action="store_true",
        help="List matching run/worktrees without recursively sizing them.",
    )
    parser.add_argument(
        "--github-repo",
        help="Optional OWNER/REPO repository whose branch protection should be audited with gh api.",
    )
    parser.add_argument(
        "--protected-branch",
        default=DEFAULT_PROTECTED_BRANCH,
        help=f"Branch to inspect with --github-repo. Defaults to {DEFAULT_PROTECTED_BRANCH}.",
    )
    parser.add_argument(
        "--required-status-check",
        action="append",
        default=None,
        help=(
            "Expected required status check for --github-repo. May be repeated. Defaults to "
            f"{', '.join(DEFAULT_REQUIRED_STATUS_CHECKS)}."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] in BROKER_COMMANDS:
        return resource_broker.main(arguments)
    args = buildParser().parse_args(arguments)
    repoRoot = Path(args.repo_root).resolve()
    diskPaths = [repoRoot, Path("/tmp"), *[Path(path).resolve() for path in args.disk_path]]
    uniqueDiskPaths = list(dict.fromkeys(path for path in diskPaths if path.exists()))
    runTreeRoots = [Path(path).resolve() for path in args.run_tree_root] or [Path("/tmp")]
    runTreePatterns = args.run_tree_pattern or list(DEFAULT_RUN_TREE_PATTERNS)

    try:
        gitHealth = runGitHealth(repoRoot)
        diskReports = [diskReport(path) for path in uniqueDiskPaths]
        worktrees = runGitWorktreeList(repoRoot)
        runTrees = discoverRunTrees(runTreeRoots, runTreePatterns, includeSizes=not args.skip_run_tree_sizes)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"controller_resource_audit: {exc}", file=sys.stderr)
        return 2

    branchProtection = None
    mergePolicy = None
    if args.github_repo:
        expectedChecks = tuple(args.required_status_check or DEFAULT_REQUIRED_STATUS_CHECKS)
        branchProtection = auditBranchProtection(args.github_repo, args.protected_branch, expectedChecks)
        mergePolicy = auditMergePolicy(args.github_repo)

    minFreeBytes = int(args.min_free_gib * 1024 * 1024 * 1024)
    errors, warnings = evaluateDiskReports(diskReports, minFreeBytes, args.max_used_percent)
    gitErrors, gitWarnings = evaluateGitHealth(gitHealth)
    errors.extend(gitErrors)
    warnings.extend(gitWarnings)
    branchErrors, branchWarnings = evaluateBranchProtection(branchProtection)
    errors.extend(branchErrors)
    warnings.extend(branchWarnings)
    mergePolicyErrors, mergePolicyWarnings = evaluateMergePolicy(mergePolicy)
    errors.extend(mergePolicyErrors)
    warnings.extend(mergePolicyWarnings)
    resources = resource_broker.observeResources(repoRoot)
    resourceErrors, resourceWarnings = evaluateResourceObservation(resources)
    errors.extend(resourceErrors)
    warnings.extend(resourceWarnings)
    summary = worktreeSummary(worktrees)
    if summary["prunable"]:
        warnings.append(f"{summary['prunable']} prunable worktree registration(s); review and run git worktree prune")
    report = payload(
        repoRoot,
        gitHealth,
        diskReports,
        worktrees,
        runTrees,
        not args.skip_run_tree_sizes,
        branchProtection,
        errors,
        warnings,
        mergePolicy=mergePolicy,
        resources=resources,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        printHuman(report)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
