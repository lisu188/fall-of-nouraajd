# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Plan exhaustive MCP routes and transfer the current build's runtime to CI shards."""

import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET_SECONDS = 20 * 60
MAX_MATRIX_SHARDS = 256
MAX_JOB_MINUTES = 360
RESOURCE_DIRS = ("campaigns", "config", "fonts", "images", "maps", "plugins")
ROOT_RESOURCE_FILES = ("game.py", "ui.py", "campaign.py", "narrative.py", "game_diagnostics.py", "quest_state.py")
CONFIG_DIRS = ("Release", "Debug", "RelWithDebInfo", "MinSizeRel")
MANIFEST_NAME = "mcp-branch-runtime.json"
REVIEWED_TIMINGS_FILE = ROOT / "tests/fixtures/mcp_branch_timings.json"


@lru_cache(maxsize=1)
def reviewedDurations(path=REVIEWED_TIMINGS_FILE):
    path = Path(path)
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "mcp_branch_timings.v1" or value.get("reviewed") is not True:
        raise ValueError("Scheduling timings must be explicitly reviewed measured evidence")
    platforms = value.get("platforms", {})
    if set(platforms) != {"linux", "windows"}:
        raise ValueError("Reviewed timings require both platform measurements")
    linux = platforms["linux"]["routeDurationsSeconds"]
    windows = platforms["windows"]["routeDurationsSeconds"]
    if set(linux) != set(windows):
        raise ValueError("Reviewed platform timings must cover the same routes")
    result = {}
    for case_id in linux:
        samples = (float(linux[case_id]), float(windows[case_id]))
        if any(not math.isfinite(sample) or sample <= 0 for sample in samples):
            raise ValueError(f"Invalid measured duration for route {case_id}")
        result[case_id] = max(samples)
    return result


def caseWeights(cases):
    from tests.gameplay_branch_types import testName

    weights = {}
    measured = reviewedDurations()
    for case in cases:
        duration = float(measured.get(case.id, case.duration_seconds))
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError(f"Invalid duration for route {case.id}: {duration}")
        for class_id in case.classes:
            name = testName(case, class_id)
            if name in weights:
                raise ValueError(f"Duplicate route test: {name}")
            weights[name] = duration
    if not weights:
        raise ValueError("The authored branch matrix is empty")
    return weights


def validatePartition(expected, shards):
    expected_counts = Counter(iter(expected))
    actual_counts = Counter(name for shard in shards for name in shard)
    if any(count != 1 for count in expected_counts.values()) or actual_counts != expected_counts:
        raise ValueError("Branch shards must contain every selected route exactly once")
    if any(not shard for shard in shards):
        raise ValueError("Branch shards cannot be empty")


def planShards(cases, target_seconds=TARGET_SECONDS, shard_count=None):
    weights = caseWeights(cases)
    if not math.isfinite(target_seconds) or target_seconds <= 0:
        raise ValueError("The shard target must be positive and finite")
    if shard_count is None:
        shard_count = min(len(weights), MAX_MATRIX_SHARDS, max(1, math.ceil(sum(weights.values()) / target_seconds)))
    if not isinstance(shard_count, int) or not 1 <= shard_count <= len(weights):
        raise ValueError("Shard count must be between one and the selected test count")
    shards = [[] for _ in range(shard_count)]
    totals = [0.0] * shard_count
    for name in sorted(weights, key=lambda name: (-weights[name], name)):
        index = min(range(shard_count), key=lambda index: (totals[index], index))
        shards[index].append(name)
        totals[index] += weights[name]
    validatePartition(weights, shards)
    return shards


def selectedCases(class_id=None, group=None):
    from dataclasses import replace
    from tests.gameplay_branch_catalog import getCases
    from tests.gameplay_branch_types import PLAYER_CLASSES

    if class_id is not None and class_id not in PLAYER_CLASSES:
        raise ValueError(f"Unknown player class: {class_id}")
    cases = tuple(getCases())
    if group is not None and group not in {case.group for case in cases}:
        raise ValueError(f"Unknown branch group: {group}")
    return tuple(
        replace(case, classes=(class_id,)) if class_id else case
        for case in cases
        if (group is None or case.group == group) and (class_id is None or class_id in case.classes)
    )


def matrix(cases):
    weights = caseWeights(cases)
    shards = planShards(cases)
    result = {
        "include": [
            {
                "shard": index,
                "count": len(shards),
                "tests": len(names),
                "estimated-seconds": math.ceil(sum(weights[name] for name in names)),
                "timeout-minutes": max(20, math.ceil(sum(weights[name] for name in names) * 3 / 60) + 10),
            }
            for index, names in enumerate(shards)
        ]
    }
    if any(row["timeout-minutes"] > MAX_JOB_MINUTES for row in result["include"]):
        raise ValueError("A branch shard exceeds the hosted job timeout; split the long route before scheduling it")
    return result


def catalogSnapshot(cases):
    from tests.gameplay_branch_catalog import auditCatalog, branchCatalog

    measured = reviewedDurations()
    cases = tuple(cases)
    covered = sum(case.id in measured for case in cases)
    source = "reviewed measurements" if covered == len(cases) else "mixed" if covered else "bootstrap estimates"
    return {
        "schema": "mcp_branch_catalog.v1",
        "proof": "planning only; successful exact receipts are required for gameplay acceptance",
        "weightSource": source,
        "audit": auditCatalog(),
        "branches": branchCatalog(),
        "cases": [
            {
                "id": case.id,
                "group": case.group,
                "maps": case.maps,
                "branches": case.branches,
                "classes": case.classes,
                "race": case.race,
                "campaign": case.campaign,
                "initialReputation": case.initial_reputation,
                "sources": case.sources,
                "durationSeconds": measured.get(case.id, case.duration_seconds),
                "durationSource": "reviewed measurement" if case.id in measured else "bootstrap estimate",
            }
            for case in cases
        ],
    }


def rejectDuplicateKeys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate receipt JSON key: {key}")
        result[key] = value
    return result


def auditReceipts(cases, receipts_dir, platform, head, pr_head, catalog_audit=None):
    from tests.gameplay_branch_driver import caseSeed
    from tests.gameplay_branch_types import testName

    if platform not in {"linux", "windows"}:
        raise ValueError("Receipt platform must be linux or windows")
    if any(not isinstance(value, str) or not value.strip() for value in (head, pr_head)):
        raise ValueError("Receipt audit requires both expected checkout and PR heads")
    if catalog_audit is not None and (catalog_audit.get("issues") or catalog_audit.get("pendingGameplay")):
        raise ValueError("Authored gameplay catalog still contains structural issues or pending branches")
    cases = tuple(cases)
    expected = {(case.id, class_id): case for case in cases for class_id in case.classes}
    if len(expected) != len(caseWeights(cases)):
        raise ValueError("Receipt catalog contains duplicate executions")
    paths = sorted(Path(receipts_dir).rglob("*.receipt.json"))
    found = {}
    timings = {}
    route_maxima = {}
    for path in paths:
        receipt = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=rejectDuplicateKeys)
        identity = (receipt.get("case"), receipt.get("class"))
        if identity not in expected:
            raise ValueError(f"Unexpected case/class receipt: {identity}")
        if identity in found:
            raise ValueError(f"Duplicate case/class receipt: {identity}")
        if receipt.get("status") != "passed":
            raise ValueError(f"Non-passing receipt ({receipt.get('status')}): {identity}")
        if receipt.get("platform") != platform or receipt.get("prHead") != pr_head:
            raise ValueError(f"Receipt platform or PR head differs from the scheduled execution: {identity}")
        if receipt.get("head") != head or receipt.get("seed") != caseSeed(*identity):
            raise ValueError(f"Receipt head or random seed differs from the scheduled case: {identity}")
        case = expected[identity]
        if Counter(receipt.get("requiredBranches", ())) != Counter(case.branches):
            raise ValueError(f"Receipt required branches differ from the current catalog: {identity}")
        if any(count != 1 for count in Counter(case.branches).values()):
            raise ValueError(f"Catalog route repeats a branch obligation: {case.id}")
        witnessed = receipt.get("branches", {})
        if not isinstance(witnessed, dict) or set(witnessed) != set(case.branches):
            raise ValueError(f"Receipt contains missing or unexpected witnessed branches: {identity}")
        if any(
            not isinstance(value, dict) or "state" not in value or "evidence" not in value
            for value in witnessed.values()
        ):
            raise ValueError(f"Receipt branch lacks state and assertion evidence: {identity}")
        seconds = receipt.get("seconds")
        if (
            not isinstance(seconds, (int, float))
            or isinstance(seconds, bool)
            or not math.isfinite(seconds)
            or seconds <= 0
        ):
            raise ValueError(f"Invalid measured receipt duration: {identity}")
        if receipt.get("race") != case.race or receipt.get("initialReputation") != case.initial_reputation:
            raise ValueError(f"Receipt starting context differs from the catalog: {identity}")
        found[identity] = str(path)
        timings[testName(case, identity[1])] = seconds
        route_maxima[case.id] = max(route_maxima.get(case.id, 0), seconds)
    missing = set(expected) - set(found)
    if missing:
        raise ValueError(f"Missing case/class receipts: {sorted(missing)}")
    return {
        "schema": "mcp_branch_timings.v1",
        "platform": platform,
        "head": head,
        "prHead": pr_head,
        "reviewed": False,
        "proof": "all current case/class receipts passed; durations require review before scheduling use",
        "executionCount": len(found),
        "routeDurationsSeconds": dict(sorted(route_maxima.items())),
        "testDurationsSeconds": dict(sorted(timings.items())),
        "receipts": {testName(expected[identity], identity[1]): path for identity, path in sorted(found.items())},
    }


def isNativeLibrary(path):
    name = path.name.lower()
    return name.endswith((".dll", ".pyd", ".dylib")) or name.endswith(".so") or ".so." in name


def runtimeFiles(build_dir):
    build_dir = Path(build_dir).resolve(strict=True)
    files = set()
    found_modules = set()
    for base in (build_dir, *(build_dir / config for config in CONFIG_DIRS)):
        if not base.is_dir():
            continue
        files.update(path for path in base.iterdir() if path.is_file() and isNativeLibrary(path))
        for name in ROOT_RESOURCE_FILES:
            path = base / name
            if path.is_file():
                files.add(path)
                found_modules.add(name)
        for resource in RESOURCE_DIRS:
            directory = base / resource
            if directory.is_dir():
                files.update(
                    path for path in directory.rglob("*") if path.is_file() and "__pycache__" not in path.parts
                )
    missing_modules = sorted(set(ROOT_RESOURCE_FILES) - found_modules)
    if missing_modules:
        raise ValueError(f"Required copied runtime modules are missing: {', '.join(missing_modules)}")
    for path in files:
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(build_dir):
            raise ValueError(f"Runtime file escapes its build directory: {path}")
    if not any(path.name.startswith("_game") and isNativeLibrary(path) for path in files):
        raise ValueError("The current _game extension is missing from the runtime")
    for resource in ("config", "maps", "plugins"):
        if not any((base / resource).is_dir() for base in (build_dir, build_dir / "Release")):
            raise ValueError(f"The copied runtime resource directory is missing: {resource}")
    return sorted(files)


def bundleRuntime(build_dir, output, head):
    build_dir = Path(build_dir).resolve(strict=True)
    files = runtimeFiles(build_dir)
    manifest = {
        "head": head,
        "files": {
            path.relative_to(build_dir).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in files
        },
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "w:gz") as archive:
        for path in files:
            archive.add(path, arcname=path.relative_to(build_dir).as_posix(), recursive=False)
        data = json.dumps(manifest, sort_keys=True).encode("utf-8")
        info = tarfile.TarInfo(MANIFEST_NAME)
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))


def unpackRuntime(archive_path, build_dir, head):
    build_dir = Path(build_dir).resolve()
    build_dir.mkdir(parents=True, exist_ok=True)
    if any(build_dir.iterdir()):
        raise ValueError("Runtime extraction requires an empty build directory")
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(set(names)) != len(names):
            raise ValueError("Runtime archive contains duplicate members")
        for member in members:
            path = PurePosixPath(member.name)
            if (
                not member.isfile()
                or path.is_absolute()
                or path.as_posix() != member.name
                or ".." in path.parts
                or "\\" in member.name
                or ":" in member.name
            ):
                raise ValueError(f"Unsafe runtime archive member: {member.name}")
        manifest_file = archive.extractfile(MANIFEST_NAME)
        if manifest_file is None:
            raise ValueError("Runtime archive has no provenance manifest")
        manifest = json.load(manifest_file)
        if manifest.get("head") != head:
            raise ValueError("Runtime artifact was not built from this workflow checkout")
        hashes = manifest["files"]
        if set(names) != set(hashes) | {MANIFEST_NAME}:
            raise ValueError("Runtime archive does not match its manifest")
        for member in members:
            if member.name == MANIFEST_NAME:
                continue
            source = archive.extractfile(member)
            data = source.read()
            if hashlib.sha256(data).hexdigest() != hashes[member.name]:
                raise ValueError(f"Runtime artifact checksum mismatch: {member.name}")
            destination = build_dir / member.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            destination.chmod(member.mode & 0o777)
    (build_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    planner = commands.add_parser("matrix")
    planner.add_argument("--github-output", type=Path)
    planner.add_argument("--catalog-output", type=Path)
    auditor = commands.add_parser("audit-receipts")
    auditor.add_argument("--receipts-dir", type=Path, required=True)
    auditor.add_argument("--platform", choices=("linux", "windows"), required=True)
    auditor.add_argument("--head", required=True)
    auditor.add_argument("--pr-head", required=True)
    auditor.add_argument("--output", type=Path, required=True)
    auditor.add_argument("--audit-root", type=Path, default=ROOT)
    runner = commands.add_parser("run")
    runner.add_argument("--shard-index", type=int, required=True)
    runner.add_argument("--shard-count", type=int, required=True)
    runner.add_argument("--branch-class")
    runner.add_argument("--branch-group")
    for command in ("bundle", "unpack"):
        transfer = commands.add_parser(command)
        transfer.add_argument("--build-dir", type=Path, required=True)
        transfer.add_argument("--archive", type=Path, required=True)
        transfer.add_argument("--head", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "bundle":
            bundleRuntime(args.build_dir, args.archive, args.head)
        elif args.command == "unpack":
            unpackRuntime(args.archive, args.build_dir, args.head)
        elif args.command == "matrix":
            cases = selectedCases()
            value = json.dumps(matrix(cases), separators=(",", ":"))
            print(value)
            if args.github_output:
                with args.github_output.open("a", encoding="utf-8") as output:
                    output.write(f"mcp-branch-matrix={value}\n")
            if args.catalog_output:
                args.catalog_output.parent.mkdir(parents=True, exist_ok=True)
                args.catalog_output.write_text(json.dumps(catalogSnapshot(cases), indent=2) + "\n", encoding="utf-8")
        elif args.command == "audit-receipts":
            from tests.gameplay_branch_catalog import auditCatalog

            result = auditReceipts(
                selectedCases(),
                args.receipts_dir,
                args.platform,
                args.head,
                args.pr_head,
                auditCatalog(args.audit_root),
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print(f"{args.platform}: {result['executionCount']} exact passing receipts; measured timings await review")
        else:
            shards = planShards(selectedCases(args.branch_class, args.branch_group), shard_count=args.shard_count)
            if not 0 <= args.shard_index < len(shards):
                raise ValueError("Shard index must be zero-based and smaller than the shard count")
            names = shards[args.shard_index]
            print(f"MCP branch shard {args.shard_index + 1}/{len(shards)}: {len(names)} routes", flush=True)
            environment = os.environ.copy()
            environment["GAME_MCP_BRANCH_REQUIRED"] = "1"
            return subprocess.call(
                [sys.executable, str(ROOT / "test.py"), "--jobs", "1", *names], cwd=ROOT, env=environment
            )
    except (ValueError, OSError, KeyError, tarfile.TarError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
