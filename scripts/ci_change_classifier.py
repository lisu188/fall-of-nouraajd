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

# Paths whose content can change how required validation or auto-merge is
# routed, polled, scored, or authorized.
# A pull request that edits these files must not be allowed to classify its own
# change as lightweight and thereby skip native/coverage validation. Touching any
# of these forces strict native + coverage validation and human review, so the
# authority for "what is required" never comes solely from PR-controlled logic.
CI_AUTHORITY_PATH_PATTERNS = (
    ".github/workflows/auto-merge.yml",
    ".github/workflows/build.yml",
    "scripts/auto_merge_policy.py",
    "scripts/ci_change_classifier.py",
)

LIGHTWEIGHT_PATH_PATTERNS = (
    ".github/workflows/*",
    "AGENTS.md",
    "docs/*",
    "scripts/ci_change_classifier.py",
    "scripts/validate_content.py",
    "tests/security/test_configure_supply_chain.py",
    "tests/test_ci_change_classifier.py",
    "tests/test_content_validator.py",
    "tests/test_coverage_report.py",
)


# Disjoint change-KIND taxonomy consumed by the workflow and poller. Each changed
# path is assigned exactly one primary kind by _path_kind() (first match wins, in
# the order below), so GUI C++ is never mis-bucketed as generic engine code and a
# res/ content change is never mis-bucketed as an engine change. The workflow can
# gate expensive jobs from the presence booleans; native/coverage need is still
# taken from the existing NATIVE/COVERAGE pattern sets (unchanged) for safety.
GUI_NATIVE_KIND_PATTERNS = ("src/gui/*",)
ENGINE_NATIVE_KIND_PATTERNS = (
    "src/*",
    "native_plugins/*",
    "random-dungeon-generator/*",
    "vstd/*",
    "CMakeLists.txt",
    "cmake/*",
    "configure.sh",
    "configure.bat",
    "vcpkg.json",
    "test.py",
    "tests/unit/*",
    "tests/fixtures/*",
    "tests/regression/*",
)
CONTENT_KIND_PATTERNS = ("res/*",)
WORKFLOW_PYTHON_KIND_PATTERNS = (
    ".github/*",
    "scripts/*.py",
    "scripts/*.sh",
    "tests/test_*.py",
    "tests/security/*.py",
)
PROMPTS_DOCS_KIND_PATTERNS = (
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "*.md",
    "docs/*",
)


def _path_kind(path: str) -> str:
    """Assign one primary KIND to a changed path (first match wins)."""
    if matchesAny(path, GUI_NATIVE_KIND_PATTERNS):
        return "native-gui"
    if matchesAny(path, ENGINE_NATIVE_KIND_PATTERNS):
        return "native-engine"
    if matchesAny(path, CONTENT_KIND_PATTERNS):
        return "content-json-python"
    if matchesAny(path, WORKFLOW_PYTHON_KIND_PATTERNS):
        return "workflow-python"
    if matchesAny(path, PROMPTS_DOCS_KIND_PATTERNS):
        return "prompts-docs"
    return "unclassified"


@dataclass(frozen=True)
class ChangeClassification:
    paths: tuple[str, ...]
    coverageNeeded: bool
    nativeNeeded: bool
    nativeReasons: tuple[str, ...]
    authorityChange: bool = False
    authorityPaths: tuple[str, ...] = ()
    # Additive KIND taxonomy (presence booleans over the changed set). These do
    # not alter native/coverage need; they let the workflow route jobs by change
    # kind and let tests pin the classification of each path category.
    coverageRelevant: bool = False
    nativeGui: bool = False
    nativeEngine: bool = False
    contentJsonPython: bool = False
    workflowPython: bool = False
    promptsDocs: bool = False

    @property
    def humanReviewRequired(self) -> bool:
        # Changes to validation or merge authority cannot be trusted solely from
        # PR-controlled logic.
        return self.authorityChange


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

    authorityPaths = tuple(path for path in changed if matchesAny(path, CI_AUTHORITY_PATH_PATTERNS))
    authorityChange = bool(authorityPaths)

    if forceNative:
        nativeReasons.append("forced")
    if authorityChange:
        # A PR that edits the routing/poller/classifier files cannot self-classify
        # as lightweight: force strict native + coverage validation so it cannot
        # skip its way out of required checks. Authority is taken from this fixed
        # rule rather than from the (PR-controlled) edited logic.
        coverageNeeded = True
        nativeReasons.append("ci-authority change")
    if coverageNeeded:
        nativeReasons.append("coverage-relevant paths")

    for path in changed:
        if matchesAny(path, NATIVE_PATH_PATTERNS):
            nativeReasons.append(path)
        elif not matchesAny(path, LIGHTWEIGHT_PATH_PATTERNS):
            nativeReasons.append(f"unclassified:{path}")

    kinds = [_path_kind(path) for path in changed]
    coverageRelevant = any(matchesAny(path, COVERAGE_PATH_PATTERNS) for path in changed)

    return ChangeClassification(
        paths=changed,
        coverageNeeded=coverageNeeded,
        nativeNeeded=bool(nativeReasons),
        nativeReasons=tuple(dict.fromkeys(nativeReasons)),
        authorityChange=authorityChange,
        authorityPaths=authorityPaths,
        coverageRelevant=coverageRelevant,
        nativeGui="native-gui" in kinds,
        nativeEngine="native-engine" in kinds,
        contentJsonPython="content-json-python" in kinds,
        workflowPython="workflow-python" in kinds,
        promptsDocs="prompts-docs" in kinds,
    )


def resolveDiffBase(base: str, head: str) -> str:
    """Resolve the changed-path diff base to the merge-base of ``base`` and ``head``.

    On a pull request the build workflow passes the base *branch tip*
    (``pull_request.base.sha``), which advances as other PRs merge into the base
    branch. Diffing ``base..head`` directly then reports every file merged into
    the base branch after this PR's branch point as changed, so a lightweight PR
    is misclassified as native/coverage-needed and incurs unnecessary heavy CI.
    Diffing from the merge-base restricts detection to the PR's own changes.
    Falls back to ``base`` when no merge-base can be computed (for example an
    unrelated or shallow history), preserving the previous behavior.
    """

    result = subprocess.run(
        ["git", "merge-base", base, head],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    mergeBase = result.stdout.strip()
    if result.returncode == 0 and mergeBase:
        return mergeBase
    return base


def changedPaths(base: str, head: str) -> tuple[str, ...]:
    diffBase = resolveDiffBase(base, head)
    result = subprocess.run(
        ["git", "diff", "--name-only", diffBase, head],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return uniquePaths(result.stdout.splitlines())


def writeGithubOutput(path: Path, classification: ChangeClassification) -> None:
    def line(key: str, value: bool) -> str:
        return f"{key}={str(value).lower()}\n"

    with path.open("a", encoding="utf-8") as handle:
        handle.write(line("coverage-needed", classification.coverageNeeded))
        handle.write(line("native-needed", classification.nativeNeeded))
        handle.write(line("authority-change", classification.authorityChange))
        handle.write(line("human-review-required", classification.humanReviewRequired))
        # Additive KIND taxonomy outputs (available to the workflow for finer job
        # routing; existing native-needed/coverage-needed gating is unchanged).
        handle.write(line("coverage-relevant", classification.coverageRelevant))
        handle.write(line("native-gui", classification.nativeGui))
        handle.write(line("native-engine", classification.nativeEngine))
        handle.write(line("content-json-python", classification.contentJsonPython))
        handle.write(line("workflow-python", classification.workflowPython))
        handle.write(line("prompts-docs", classification.promptsDocs))


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
                "authorityChange": classification.authorityChange,
                "authorityPaths": list(classification.authorityPaths),
                "contentJsonPython": classification.contentJsonPython,
                "coverageNeeded": classification.coverageNeeded,
                "coverageRelevant": classification.coverageRelevant,
                "humanReviewRequired": classification.humanReviewRequired,
                "nativeEngine": classification.nativeEngine,
                "nativeGui": classification.nativeGui,
                "nativeNeeded": classification.nativeNeeded,
                "nativeReasons": list(classification.nativeReasons),
                "paths": list(classification.paths),
                "promptsDocs": classification.promptsDocs,
                "workflowPython": classification.workflowPython,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
