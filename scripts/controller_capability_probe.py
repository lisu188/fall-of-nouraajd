#!/usr/bin/env python3
"""Read-only controller capability snapshot for queue-controller runtimes.

The probe never mutates the repository, GitHub state, or the environment. It reports one field per capability with a
status of ``available``, ``unavailable``, ``unknown``, or ``unsupported`` plus short redacted evidence, so controller
prompts can branch on verified capabilities instead of assuming merge methods, auth, required checks, formatters,
build trees, or polling support. Missing tools are actionable field values, never tracebacks, and the process exits 0
even when capabilities are missing; only usage errors exit non-zero.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

STATUS_AVAILABLE = "available"
STATUS_UNAVAILABLE = "unavailable"
STATUS_UNKNOWN = "unknown"
STATUS_UNSUPPORTED = "unsupported"
ALLOWED_STATUSES = (STATUS_AVAILABLE, STATUS_UNAVAILABLE, STATUS_UNKNOWN, STATUS_UNSUPPORTED)

SECTION_NAMES = ("agent", "build", "ci", "github", "repository", "toolchain")

DEFAULT_COMMAND_TIMEOUT_SECONDS = 10.0
MAX_EVIDENCE_CHARS = 200
MAX_CAPTURED_OUTPUT_CHARS = 4000
BUILD_WORKFLOW_RELATIVE_PATH = Path(".github") / "workflows" / "build.yml"
EXTRA_TOOL_SEARCH_PATHS = ("/root/.local/bin",)
VERSIONED_TOOLS = ("black", "clang-format", "cmake", "ctest")
LINUX_ONLY_TOOLS = ("xauth", "xvfb-run")
AGENT_ENV_MARKERS = (
    "CI",
    "CLAUDECODE",
    "CODEX_PROXY_CERT",
    "GAME_BUILD_DIR",
    "GH_TOKEN",
    "GITHUB_ACTIONS",
    "GITHUB_TOKEN",
    "HTTPS_PROXY",
)

REDACTION_PATTERNS = (
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{4,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{4,}"),
    re.compile(r"(?i)\bbearer\s+\S+"),
    re.compile(r"(?i)\b(?:token|password|passwd|secret|authorization|api[_-]?key)\b\s*[:=]\s*\S+"),
)
CREDENTIAL_URL_PATTERN = re.compile(r"://[^/\s@]+@")


def redactText(text: str) -> str:
    """Collapse whitespace, strip credential-shaped substrings, and bound evidence length."""
    collapsed = " ".join(text.split())
    for pattern in REDACTION_PATTERNS:
        collapsed = pattern.sub("REDACTED", collapsed)
    collapsed = CREDENTIAL_URL_PATTERN.sub("://REDACTED@", collapsed)
    if len(collapsed) > MAX_EVIDENCE_CHARS:
        collapsed = collapsed[: MAX_EVIDENCE_CHARS - 3] + "..."
    return collapsed


def capabilityField(status: str, evidence: str) -> dict[str, str]:
    if status not in ALLOWED_STATUSES:
        status = STATUS_UNKNOWN
    return {"evidence": redactText(evidence), "status": status}


def firstLine(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def runCommand(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: float = DEFAULT_COMMAND_TIMEOUT_SECONDS,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Run a read-only command; degrade every failure mode to a result dict, never an exception."""
    try:
        completed = subprocess.run(
            list(args),
            cwd=str(cwd) if cwd is not None else None,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            env=dict(env) if env is not None else None,
        )
    except FileNotFoundError:
        return {"error": f"command not found: {args[0]}", "exitCode": None, "stderr": "", "stdout": ""}
    except subprocess.TimeoutExpired:
        return {
            "error": f"{args[0]} timed out after {timeout:.1f}s",
            "exitCode": None,
            "stderr": "",
            "stdout": "",
        }
    except OSError as exc:
        return {"error": f"{args[0]} could not be executed: {exc}", "exitCode": None, "stderr": "", "stdout": ""}
    stdout = (completed.stdout or "")[:MAX_CAPTURED_OUTPUT_CHARS]
    stderr = (completed.stderr or "")[:MAX_CAPTURED_OUTPUT_CHARS]
    return {"error": None, "exitCode": completed.returncode, "stderr": stderr, "stdout": stdout}


def commandFailureDetail(result: dict[str, Any], fallback: str) -> str:
    if result["error"]:
        return str(result["error"])
    detail = firstLine(result["stderr"]) or firstLine(result["stdout"])
    if detail:
        return f"exit code {result['exitCode']}: {detail}"
    return f"{fallback} (exit code {result['exitCode']})"


def statusForFailedCommand(result: dict[str, Any]) -> str:
    """Timeouts and unexecutable commands are unknown; a clean non-zero exit is unavailable."""
    if result["error"]:
        return STATUS_UNKNOWN
    return STATUS_UNAVAILABLE


def probeRepositorySection(repoRoot: Path, timeout: float) -> dict[str, Any]:
    section: dict[str, Any] = {}
    gitVersion = runCommand(["git", "--version"], cwd=repoRoot, timeout=timeout)
    if gitVersion["error"] or gitVersion["exitCode"] != 0:
        detail = commandFailureDetail(gitVersion, "git --version failed")
        section["gitPresent"] = capabilityField(
            STATUS_UNAVAILABLE if gitVersion["error"] else statusForFailedCommand(gitVersion),
            f"git not usable ({detail}); install git before controller git operations",
        )
        notProbed = capabilityField(STATUS_UNKNOWN, "git unavailable; not probed")
        section["defaultBranch"] = notProbed
        section["insideWorkTree"] = notProbed
        section["remoteReachable"] = notProbed
        section["worktreeSupport"] = notProbed
        return section
    section["gitPresent"] = capabilityField(STATUS_AVAILABLE, firstLine(gitVersion["stdout"]) or "git responded")

    insideTree = runCommand(["git", "rev-parse", "--is-inside-work-tree"], cwd=repoRoot, timeout=timeout)
    if insideTree["error"] is None and insideTree["exitCode"] == 0 and firstLine(insideTree["stdout"]) == "true":
        section["insideWorkTree"] = capabilityField(STATUS_AVAILABLE, f"{repoRoot} is inside a git work tree")
    else:
        section["insideWorkTree"] = capabilityField(
            statusForFailedCommand(insideTree),
            f"{repoRoot} is not a git work tree ({commandFailureDetail(insideTree, 'rev-parse failed')})",
        )

    originHead = runCommand(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=repoRoot, timeout=timeout
    )
    if originHead["error"] is None and originHead["exitCode"] == 0 and firstLine(originHead["stdout"]):
        section["defaultBranch"] = capabilityField(
            STATUS_AVAILABLE, f"origin default branch: {firstLine(originHead['stdout'])}"
        )
    else:
        originMain = runCommand(
            ["git", "rev-parse", "--verify", "refs/remotes/origin/main"], cwd=repoRoot, timeout=timeout
        )
        if originMain["error"] is None and originMain["exitCode"] == 0:
            section["defaultBranch"] = capabilityField(
                STATUS_AVAILABLE, "origin/HEAD unset; refs/remotes/origin/main resolves, assuming main"
            )
        else:
            section["defaultBranch"] = capabilityField(
                STATUS_UNKNOWN,
                "origin default branch unresolved; run git remote set-head origin --auto before branch-dependent steps",
            )

    lsRemote = runCommand(["git", "ls-remote", "--exit-code", "origin", "HEAD"], cwd=repoRoot, timeout=timeout)
    if lsRemote["error"] is None and lsRemote["exitCode"] == 0:
        section["remoteReachable"] = capabilityField(STATUS_AVAILABLE, "git ls-remote origin HEAD succeeded")
    else:
        section["remoteReachable"] = capabilityField(
            statusForFailedCommand(lsRemote),
            f"origin not reachable ({commandFailureDetail(lsRemote, 'git ls-remote failed')}); "
            "block fetch/push-dependent steps until the remote is verified",
        )

    worktreeList = runCommand(["git", "worktree", "list", "--porcelain"], cwd=repoRoot, timeout=timeout)
    if worktreeList["error"] is None and worktreeList["exitCode"] == 0:
        totalWorktrees = sum(1 for line in worktreeList["stdout"].splitlines() if line.startswith("worktree "))
        section["worktreeSupport"] = capabilityField(
            STATUS_AVAILABLE, f"git worktree list succeeded ({totalWorktrees} worktree(s))"
        )
    else:
        detail = commandFailureDetail(worktreeList, "git worktree list failed")
        status = statusForFailedCommand(worktreeList)
        if "is not a git command" in detail:
            status = STATUS_UNSUPPORTED
        section["worktreeSupport"] = capabilityField(status, f"git worktree unusable ({detail})")
    return section


def probeGithubSection(timeout: float) -> dict[str, Any]:
    section: dict[str, Any] = {}
    ghPath = shutil.which("gh")
    if not ghPath:
        section["ghCli"] = capabilityField(
            STATUS_UNAVAILABLE,
            "gh not found on PATH; gh-based merge, polling, and metadata probes are unavailable in this runtime",
        )
        notProbed = capabilityField(STATUS_UNKNOWN, "gh CLI absent; not probed, treat GitHub capability as unknown")
        section["apiReachable"] = notProbed
        section["ghAuth"] = notProbed
        return section

    ghVersion = runCommand(["gh", "--version"], timeout=timeout)
    if ghVersion["error"] or ghVersion["exitCode"] != 0:
        section["ghCli"] = capabilityField(
            statusForFailedCommand(ghVersion),
            f"gh found at {ghPath} but not usable ({commandFailureDetail(ghVersion, 'gh --version failed')})",
        )
    else:
        section["ghCli"] = capabilityField(STATUS_AVAILABLE, firstLine(ghVersion["stdout"]) or f"gh at {ghPath}")

    authStatus = runCommand(["gh", "auth", "status"], timeout=timeout)
    if authStatus["error"] is None and authStatus["exitCode"] == 0:
        detail = firstLine(authStatus["stdout"]) or firstLine(authStatus["stderr"]) or "gh auth status exit 0"
        section["ghAuth"] = capabilityField(STATUS_AVAILABLE, detail)
    else:
        section["ghAuth"] = capabilityField(
            statusForFailedCommand(authStatus),
            f"gh is not authenticated ({commandFailureDetail(authStatus, 'gh auth status failed')}); "
            "block gh mutations until auth is verified",
        )

    apiProbe = runCommand(["gh", "api", "rate_limit"], timeout=timeout)
    if apiProbe["error"] is None and apiProbe["exitCode"] == 0:
        section["apiReachable"] = capabilityField(STATUS_AVAILABLE, "gh api rate_limit succeeded")
    else:
        section["apiReachable"] = capabilityField(
            statusForFailedCommand(apiProbe),
            f"GitHub API not reachable via gh ({commandFailureDetail(apiProbe, 'gh api rate_limit failed')}); "
            "API calls may be proxied or blocked in this runtime",
        )
    return section


def parseWorkflowJobNames(text: str) -> list[str]:
    """Parse top-level job names from a GitHub Actions workflow without a YAML dependency."""
    names: list[str] = []
    inJobs = False
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            inJobs = line.split("#", 1)[0].rstrip() == "jobs:"
            continue
        if inJobs:
            match = re.match(r"^  ([A-Za-z0-9_-]+):", line)
            if match:
                names.append(match.group(1))
    return names


def probeCiSection(repoRoot: Path) -> dict[str, Any]:
    section: dict[str, Any] = {}
    workflowPath = repoRoot / BUILD_WORKFLOW_RELATIVE_PATH
    missingEvidence = (
        f"{BUILD_WORKFLOW_RELATIVE_PATH} is missing; CI polling has no build workflow to watch in this checkout"
    )
    if not workflowPath.is_file():
        section["buildWorkflowPresent"] = capabilityField(STATUS_UNAVAILABLE, missingEvidence)
        section["requiredJobs"] = capabilityField(STATUS_UNAVAILABLE, missingEvidence)
        return section
    section["buildWorkflowPresent"] = capabilityField(STATUS_AVAILABLE, f"{BUILD_WORKFLOW_RELATIVE_PATH} present")
    try:
        jobNames = parseWorkflowJobNames(workflowPath.read_text(encoding="utf-8"))
    except OSError as exc:
        section["requiredJobs"] = capabilityField(
            STATUS_UNKNOWN, f"{BUILD_WORKFLOW_RELATIVE_PATH} could not be read: {exc}"
        )
        return section
    if jobNames:
        section["requiredJobs"] = capabilityField(STATUS_AVAILABLE, "jobs: " + ", ".join(sorted(jobNames)))
    else:
        section["requiredJobs"] = capabilityField(
            STATUS_UNKNOWN,
            f"no jobs parsed from {BUILD_WORKFLOW_RELATIVE_PATH}; verify required check names manually",
        )
    return section


def resolveExecutable(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for extraDir in EXTRA_TOOL_SEARCH_PATHS:
        candidate = Path(extraDir) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def probeVersionedTool(name: str, timeout: float) -> dict[str, str]:
    toolPath = resolveExecutable(name)
    if not toolPath:
        searched = ", ".join(("PATH",) + EXTRA_TOOL_SEARCH_PATHS)
        return capabilityField(
            STATUS_UNAVAILABLE, f"{name} not found ({searched}); install it before steps that require {name}"
        )
    versionResult = runCommand([toolPath, "--version"], timeout=timeout)
    if versionResult["error"] is None and versionResult["exitCode"] == 0:
        detail = firstLine(versionResult["stdout"]) or f"{name} responded"
        return capabilityField(STATUS_AVAILABLE, f"{detail} ({toolPath})")
    return capabilityField(
        STATUS_UNKNOWN,
        f"{name} found at {toolPath} but version query failed "
        f"({commandFailureDetail(versionResult, '--version failed')})",
    )


def probeToolchainSection(timeout: float, platformName: str | None = None) -> dict[str, Any]:
    platformName = platformName if platformName is not None else sys.platform
    section: dict[str, Any] = {
        "pythonVersion": capabilityField(STATUS_AVAILABLE, f"python {sys.version.split()[0]} at {sys.executable}")
    }
    for tool_name in VERSIONED_TOOLS:
        section[tool_name] = probeVersionedTool(tool_name, timeout)
    for tool_name in LINUX_ONLY_TOOLS:
        if not platformName.startswith("linux"):
            section[tool_name] = capabilityField(
                STATUS_UNSUPPORTED, f"{tool_name} probe only supported on linux (platform: {platformName})"
            )
            continue
        toolPath = shutil.which(tool_name)
        if toolPath:
            section[tool_name] = capabilityField(STATUS_AVAILABLE, f"found at {toolPath}")
        else:
            section[tool_name] = capabilityField(
                STATUS_UNAVAILABLE, f"{tool_name} not found on PATH; headless UI (xvfb) test runs are unavailable"
            )
    return section


def probeBuildSection(repoRoot: Path, timeout: float) -> dict[str, Any]:
    section: dict[str, Any] = {}
    try:
        buildDirNames = sorted(path.name for path in repoRoot.glob("cmake-build-*") if path.is_dir())
    except OSError as exc:
        errorField = capabilityField(STATUS_UNKNOWN, f"build directories could not be listed: {exc}")
        section["buildDirs"] = errorField
        section["gameModuleImportable"] = errorField
        return section
    if not buildDirNames:
        section["buildDirs"] = capabilityField(
            STATUS_UNAVAILABLE, "no cmake-build-* directories; build the _game target before gameplay tests"
        )
        section["gameModuleImportable"] = capabilityField(
            STATUS_UNAVAILABLE, "no build directory; _game import not attempted"
        )
        return section
    section["buildDirs"] = capabilityField(STATUS_AVAILABLE, ", ".join(buildDirNames))

    preferredDir = "cmake-build-release" if "cmake-build-release" in buildDirNames else buildDirNames[0]
    importEnv = dict(os.environ)
    importEnv["PYTHONPATH"] = os.pathsep.join([str(repoRoot / preferredDir), str(repoRoot / "res")])
    importResult = runCommand([sys.executable, "-c", "import _game"], cwd=repoRoot, timeout=timeout, env=importEnv)
    if importResult["error"] is None and importResult["exitCode"] == 0:
        section["gameModuleImportable"] = capabilityField(
            STATUS_AVAILABLE, f"import _game succeeded via {preferredDir}"
        )
    else:
        section["gameModuleImportable"] = capabilityField(
            statusForFailedCommand(importResult),
            f"import _game failed via {preferredDir} "
            f"({commandFailureDetail(importResult, 'import failed')}); rebuild the _game target",
        )
    return section


def probeAgentSection(environ: Mapping[str, str] | None = None, platformName: str | None = None) -> dict[str, Any]:
    environ = os.environ if environ is None else environ
    platformName = platformName if platformName is not None else sys.platform
    envMarkers: dict[str, Any] = {}
    for marker in AGENT_ENV_MARKERS:
        if marker in environ:
            envMarkers[marker] = capabilityField(STATUS_AVAILABLE, "environment variable is set (value REDACTED)")
        else:
            envMarkers[marker] = capabilityField(STATUS_UNAVAILABLE, "environment variable is not set")
    return {
        "envMarkers": envMarkers,
        "platform": capabilityField(STATUS_AVAILABLE, platformName),
    }


def safeSection(builder: Callable[[], dict[str, Any]], sectionName: str) -> dict[str, Any]:
    """Last-resort guard: a section probe must degrade to an unknown field, never a traceback."""
    try:
        return builder()
    except Exception as exc:  # noqa: BLE001 - the snapshot itself is the error channel
        return {
            "probeError": capabilityField(STATUS_UNKNOWN, f"{sectionName} probe failed: {type(exc).__name__}: {exc}")
        }


def buildSnapshot(
    repoRoot: Path,
    sections: Sequence[str] | None = None,
    *,
    timeout: float = DEFAULT_COMMAND_TIMEOUT_SECONDS,
    now: str | None = None,
    environ: Mapping[str, str] | None = None,
    platformName: str | None = None,
) -> dict[str, Any]:
    selected = tuple(sections) if sections else SECTION_NAMES
    builders: dict[str, Callable[[], dict[str, Any]]] = {
        "agent": lambda: probeAgentSection(environ=environ, platformName=platformName),
        "build": lambda: probeBuildSection(repoRoot, timeout),
        "ci": lambda: probeCiSection(repoRoot),
        "github": lambda: probeGithubSection(timeout),
        "repository": lambda: probeRepositorySection(repoRoot, timeout),
        "toolchain": lambda: probeToolchainSection(timeout, platformName=platformName),
    }
    snapshot: dict[str, Any] = {
        "repoRoot": str(repoRoot),
        "sections": {name: safeSection(builders[name], name) for name in sorted(dict.fromkeys(selected))},
        "statusVocabulary": list(ALLOWED_STATUSES),
    }
    if now is not None:
        snapshot["generatedAt"] = now
    return snapshot


def printHumanFields(fields: Mapping[str, Any], prefix: str) -> None:
    for key in sorted(fields):
        value = fields[key]
        if isinstance(value, dict) and set(value) == {"evidence", "status"}:
            print(f"{prefix}{key}: {value['status']} - {value['evidence']}")
        elif isinstance(value, dict):
            printHumanFields(value, f"{prefix}{key}.")
        else:
            print(f"{prefix}{key}: {value}")


def printHuman(snapshot: Mapping[str, Any]) -> None:
    print(f"Repository root: {snapshot['repoRoot']}")
    for sectionName in sorted(snapshot["sections"]):
        print(f"[{sectionName}]")
        printHumanFields(snapshot["sections"][sectionName], "    ")


def buildParser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Repository root to inspect (read-only).")
    parser.add_argument(
        "--section",
        action="append",
        choices=SECTION_NAMES,
        default=None,
        help="Limit the snapshot to the given section(s). May be repeated. Defaults to all sections.",
    )
    parser.add_argument("--json", action="store_true", help="Print the machine-readable JSON snapshot.")
    parser.add_argument(
        "--now",
        default=None,
        help="Optional caller-supplied timestamp recorded verbatim as generatedAt (omitted for determinism).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_COMMAND_TIMEOUT_SECONDS,
        help=f"Per-command timeout in seconds. Defaults to {DEFAULT_COMMAND_TIMEOUT_SECONDS:.0f}.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = buildParser().parse_args(argv)
    repoRoot = Path(args.repo_root).resolve()
    snapshot = buildSnapshot(repoRoot, args.section, timeout=args.timeout, now=args.now)
    if args.json:
        print(json.dumps(snapshot, indent=2, sort_keys=True))
    else:
        printHuman(snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
