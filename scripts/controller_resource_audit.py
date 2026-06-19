#!/usr/bin/env python3
"""Read-only disk and worktree resource audit for controller workflows."""

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

DEFAULT_RUN_TREE_PATTERNS = ("nouraajd-*", "fall-of-nouraajd-codex")
DEFAULT_MIN_FREE_GIB = 5.0
DEFAULT_MAX_USED_PERCENT = 95.0


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
                size = directorySize(entry) if includeSizes else 0
                records.append(RunTreeRecord(path=str(entry), sizeBytes=size))
    return sorted(records, key=lambda record: record.path)


def payload(
    repoRoot: Path,
    diskReports: Sequence[DiskReport],
    worktrees: Sequence[WorktreeRecord],
    runTrees: Sequence[RunTreeRecord],
    errors: Sequence[str],
    warnings: Sequence[str],
) -> dict[str, Any]:
    return {
        "repoRoot": str(repoRoot),
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
            "records": [
                {"path": record.path, "sizeBytes": record.sizeBytes, "sizeHuman": formatBytes(record.sizeBytes)}
                for record in runTrees
            ],
        },
        "errors": list(errors),
        "warnings": list(warnings),
    }


def printHuman(report: dict[str, Any]) -> None:
    print(f"Repository: {report['repoRoot']}")
    print("Disk:")
    for item in report["disk"]:
        print(f"  {item['path']}: {item['freeHuman']} free, " f"{item['usedPercent']:.1f}% used")
    worktrees = report["worktrees"]
    print(f"Worktrees: {worktrees['active']} active, " f"{worktrees['prunable']} prunable, {worktrees['total']} total")
    runTrees = report["runTrees"]
    print(f"Run trees: {runTrees['total']} matching, " f"{formatBytes(runTrees['totalBytes'])} total")
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
            "nouraajd-* and fall-of-nouraajd-codex."
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = buildParser().parse_args(argv)
    repoRoot = Path(args.repo_root).resolve()
    diskPaths = [repoRoot, Path("/tmp"), *[Path(path).resolve() for path in args.disk_path]]
    uniqueDiskPaths = list(dict.fromkeys(path for path in diskPaths if path.exists()))
    runTreeRoots = [Path(path).resolve() for path in args.run_tree_root] or [Path("/tmp")]
    runTreePatterns = args.run_tree_pattern or list(DEFAULT_RUN_TREE_PATTERNS)

    try:
        diskReports = [diskReport(path) for path in uniqueDiskPaths]
        worktrees = runGitWorktreeList(repoRoot)
        runTrees = discoverRunTrees(runTreeRoots, runTreePatterns, includeSizes=not args.skip_run_tree_sizes)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"controller_resource_audit: {exc}", file=sys.stderr)
        return 2

    minFreeBytes = int(args.min_free_gib * 1024 * 1024 * 1024)
    errors, warnings = evaluateDiskReports(diskReports, minFreeBytes, args.max_used_percent)
    summary = worktreeSummary(worktrees)
    if summary["prunable"]:
        warnings.append(f"{summary['prunable']} prunable worktree registration(s); review and run git worktree prune")
    report = payload(repoRoot, diskReports, worktrees, runTrees, errors, warnings)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        printHuman(report)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
