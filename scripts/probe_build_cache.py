# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Replay three existing Linux compile objects to verify real-project ccache hits."""

import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time

try:
    from scripts.build_metrics import cacheStatistics, readConfiguration
except ModuleNotFoundError:
    from build_metrics import cacheStatistics, readConfiguration


def selectObjects(log):
    latest = {}
    for line in log.splitlines():
        fields = line.split("\t")
        if len(fields) != 5 or not fields[0].isdigit() or not fields[1].isdigit():
            continue
        start, end = int(fields[0]), int(fields[1])
        if end >= start and fields[3].endswith(".o"):
            latest[fields[3]] = {"object": fields[3], "prior_edge_seconds": (end - start) / 1000}
    unity_objects = [
        value for path, value in latest.items() if path.startswith("CMakeFiles/game_core_objects.dir/Unity/")
    ]
    core_role = "unity" if unity_objects else "core"
    core_objects = unity_objects or [
        value for path, value in latest.items() if path.startswith("CMakeFiles/game_core_objects.dir/src/")
    ]
    candidates = {
        "binding": [value for path, value in latest.items() if path.startswith("CMakeFiles/game_binding_objects.dir/")],
        core_role: core_objects,
        "test": [value for path, value in latest.items() if "/tests/unit/" in path],
    }
    selected = []
    for role, values in candidates.items():
        if not values:
            raise ValueError(f"No completed {role} object exists in the Ninja log")
        selected.append({"role": role, **max(values, key=lambda value: (value["prior_edge_seconds"], value["object"]))})
        if role in {"unity", "core"}:
            selected[-1]["unity"] = role == "unity"
    return selected


def objectPath(build, relative):
    path = build / relative
    canonical = path.resolve(strict=True)
    if not canonical.is_relative_to(build) or not canonical.is_file():
        raise ValueError("Selected object escapes the build directory or is not a regular file")
    if any(component.is_symlink() for component in (path, *path.parents) if component != build):
        raise ValueError("Selected object has a symbolic-link path")
    metadata = canonical.stat()
    if metadata.st_uid != os.getuid():
        raise ValueError("Selected object belongs to another user")
    if metadata.st_dev != build.stat().st_dev or metadata.st_nlink != 1:
        raise ValueError("Selected object crosses a mount or has shared hard links")
    return canonical


def compileArguments(command, build, selected):
    if "\n" in command or "\r" in command:
        raise ValueError("Compile replay requires exactly one command")
    arguments = shlex.split(command)
    if not arguments or any(any(character in token for character in ";|&<>`$\n\r") for token in arguments):
        raise ValueError("Compile replay refuses shell operators and expansions")
    if "-c" not in arguments or arguments.count("-o") != 1:
        raise ValueError("Compile replay requires one explicit compile output")
    output_index = arguments.index("-o") + 1
    if output_index >= len(arguments) or (build / arguments[output_index]).resolve() != selected:
        raise ValueError("Compile replay output does not match the selected object")
    return arguments


def hashObject(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cacheCounters(configuration):
    with contextlib.redirect_stdout(io.StringIO()):
        statistics = cacheStatistics("ccache", configuration)
    counters = statistics.get("counters", {})
    required = {"direct_cache_hit", "preprocessed_cache_hit", "cache_miss"}
    if not required.issubset(counters):
        raise ValueError("ccache counters are unavailable")
    return {key: counters[key] for key in sorted(required)}


def runCommand(arguments, build, timeout):
    process = subprocess.Popen(arguments, cwd=build, start_new_session=True)
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        raise


def runProbe(arguments):
    report = {
        "kind": "representative-compile-cache-replay",
        "status": "failed",
        "samples": [],
        "timing_note": "Ratios compare earlier parallel build edges with serial replays; whole-build speedup is unproven.",
    }
    try:
        if sys.platform != "linux" or not arguments.replay_objects:
            raise ValueError("Replay requires Linux and explicit --replay-objects authorization")
        build = Path(arguments.build_dir).resolve(strict=True)
        configuration = readConfiguration(build)
        selected = selectObjects((build / ".ninja_log").read_text(encoding="utf-8"))
        for sample in selected:
            path = objectPath(build, sample["object"])
            command = subprocess.check_output(
                ["ninja", "-C", str(build), "-t", "commands", "-s", sample["object"]], text=True, timeout=10
            ).strip()
            command_arguments = compileArguments(command, build, path)
            sample["sha256_before"] = hashObject(path)
            before = cacheCounters(configuration)
            report["samples"].append(sample)
            start = time.monotonic()
            try:
                sample["exit_code"] = runCommand(command_arguments, build, arguments.timeout)
            finally:
                sample["replay_seconds"] = round(time.monotonic() - start, 6)
                sample["sha256_after"] = hashObject(path) if path.is_file() else None
                after = cacheCounters(configuration)
                sample["counter_delta"] = {key: after[key] - before[key] for key in before}
            delta = sample["counter_delta"]
            hits = delta["direct_cache_hit"] + delta["preprocessed_cache_hit"]
            if sample["exit_code"] != 0:
                raise ValueError("Representative compiler replay failed")
            if sample["sha256_before"] != sample["sha256_after"]:
                raise ValueError("Representative object bytes changed")
            if hits != 1 or delta["cache_miss"] != 0:
                raise ValueError("Representative compile was not exactly one cache hit; remaining replays stopped")
        report["status"] = "passed"
    except subprocess.TimeoutExpired:
        report["error"] = f"Compile replay exceeded its {arguments.timeout}-second timeout"
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        report["error"] = str(error) if not isinstance(error, subprocess.SubprocessError) else type(error).__name__
    finally:
        prior_seconds = sum(sample["prior_edge_seconds"] for sample in report["samples"])
        replay_seconds = sum(sample.get("replay_seconds", 0) for sample in report["samples"])
        ratio = replay_seconds / prior_seconds if prior_seconds > 0 else None
        report["aggregate_observed_ratio"] = round(ratio, 6) if ratio is not None else None
        report["observed_80_percent_reduction"] = (
            ratio <= 0.2 if ratio is not None and report["status"] == "passed" else None
        )
        output = Path(arguments.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": report["status"], "samples": len(report["samples"]), "report": str(output)}))
    return 0 if report["status"] == "passed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--replay-objects", action="store_true", help="Allow overwriting the three reproducible objects"
    )
    parser.add_argument("--timeout", type=float, default=60)
    arguments = parser.parse_args()
    if not 0 < arguments.timeout <= 60:
        parser.error("--timeout must be greater than zero and at most 60 seconds")
    return runProbe(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
