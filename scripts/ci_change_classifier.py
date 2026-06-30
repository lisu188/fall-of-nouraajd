#!/usr/bin/env python3
"""Classify changed paths for GitHub Actions validation routing."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

COVERAGE_PATH_PATTERNS = (
    "test.py",
    "tests/unit/*",
    "scripts/run_coverage.sh",
    "scripts/coverage_report.py",
    "native_plugins/*",
    "src/core/*",
    "src/gui/*",
    "src/handler/*",
    "src/object/*",
)

NATIVE_PATH_PATTERNS = (
    "CMakeLists.txt",
    "cmake/*",
    "configure.bat",
    "configure.sh",
    "native_plugins/*",
    "random-dungeon-generator/*",
    "res/*",
    "src/*",
    "test.py",
    "tests/fixtures/*",
    "tests/regression/*",
    "tests/unit/*",
    "vcpkg.json",
    "vstd/*",
)

LIGHTWEIGHT_PATH_PATTERNS = (
    ".github/multi-workbook-inspection.txt",
    ".github/multi-workbook-payload/*",
    ".github/workflows/*",
    "AGENTS.md",
    "docs/*",
    "planning/*.xlsx",
    "planning/workflow_observations/records/*.json",
    "planning/workflow_observations/resolutions/*.json",
    "prompts/*",
    "scripts/ci_change_classifier.py",
    "scripts/controller_resource_audit.py",
    "scripts/issue_queue.py",
    "scripts/poll_pr_checks.py",
    "scripts/pr_review_audit.py",
    "scripts/validate_content.py",
    "scripts/workbook_queue.py",
    "scripts/workflow_observations.py",
    "tests/security/test_configure_supply_chain.py",
    "tests/test_ci_change_classifier.py",
    "tests/test_content_validator.py",
    "tests/test_controller_resource_audit.py",
    "tests/test_coverage_report.py",
    "tests/test_issue_queue.py",
    "tests/test_poll_pr_checks.py",
    "tests/test_pr_review_audit.py",
    "tests/test_prompt_inventory.py",
    "tests/test_workbook_queue.py",
    "tests/test_workflow_observations.py",
)


@dataclass(frozen=True)
class ChangeClassification:
    paths: tuple[str, ...]
    coverageNeeded: bool
    nativeNeeded: bool
    nativeReasons: tuple[str, ...]


def matchesAny(path: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def normalizePath(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def uniquePaths(paths: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(dict.fromkeys(path for path in (normalizePath(item) for item in paths) if path)))


def classifyPaths(paths: Sequence[str], *, forceNative: bool = False) -> ChangeClassification:
    changed = uniquePaths(paths)
    coverageNeeded = any(matchesAny(path, COVERAGE_PATH_PATTERNS) for path in changed)
    nativeReasons: list[str] = []

    if forceNative:
        nativeReasons.append("forced")
    if coverageNeeded:
        nativeReasons.append("coverage-relevant paths")

    for path in changed:
        if matchesAny(path, NATIVE_PATH_PATTERNS):
            nativeReasons.append(path)
        elif not matchesAny(path, LIGHTWEIGHT_PATH_PATTERNS):
            nativeReasons.append(f"unclassified:{path}")

    return ChangeClassification(
        paths=changed,
        coverageNeeded=coverageNeeded,
        nativeNeeded=bool(nativeReasons),
        nativeReasons=tuple(dict.fromkeys(nativeReasons)),
    )


def changedPaths(base: str, head: str) -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "diff", "--name-only", base, head],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return uniquePaths(result.stdout.splitlines())


def writeGithubOutput(path: Path, classification: ChangeClassification) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"coverage-needed={str(classification.coverageNeeded).lower()}\n")
        handle.write(f"native-needed={str(classification.nativeNeeded).lower()}\n")


def parseArgs(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="Base Git revision for changed-path detection")
    parser.add_argument("--head", help="Head Git revision for changed-path detection")
    parser.add_argument("--path", action="append", default=[], help="Changed path; may be repeated")
    parser.add_argument("--paths-from-stdin", action="store_true", help="Read changed paths from stdin")
    parser.add_argument("--force-native", action="store_true", help="Force native validation to be required")
    parser.add_argument("--github-output", help="Append GitHub Actions output variables to this file")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parseArgs(argv or sys.argv[1:])
    paths = list(args.path)
    if args.base or args.head:
        if not args.base or not args.head:
            print("ci_change_classifier: --base and --head must be supplied together", file=sys.stderr)
            return 2
        try:
            paths.extend(changedPaths(args.base, args.head))
        except subprocess.CalledProcessError as exc:
            print(f"ci_change_classifier: git diff failed: {exc.stderr.strip()}", file=sys.stderr)
            return 2
        except FileNotFoundError:
            print("ci_change_classifier: git executable not found on PATH", file=sys.stderr)
            return 2
        except OSError as exc:
            print(f"ci_change_classifier: git diff could not be executed: {exc}", file=sys.stderr)
            return 2
    if args.paths_from_stdin:
        paths.extend(sys.stdin.read().splitlines())

    classification = classifyPaths(paths, forceNative=args.force_native)
    if args.github_output:
        try:
            writeGithubOutput(Path(args.github_output), classification)
        except OSError as exc:
            print(f"ci_change_classifier: {exc}", file=sys.stderr)
            return 2
    print(
        json.dumps(
            {
                "coverageNeeded": classification.coverageNeeded,
                "nativeNeeded": classification.nativeNeeded,
                "nativeReasons": list(classification.nativeReasons),
                "paths": list(classification.paths),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
