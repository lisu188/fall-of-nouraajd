# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Record bounded compile diagnostics without retaining build logs or command environments."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

CONFIGURATION_KEYS = {
    "CMAKE_BUILD_TYPE",
    "CMAKE_C_COMPILER",
    "CMAKE_CXX_COMPILER",
    "CMAKE_CXX_SCAN_FOR_MODULES",
    "GAME_ENABLE_UNITY_BUILD",
    "GAME_UNITY_BATCH_SIZE",
    "GAME_ENABLE_PCH",
    "GAME_CCACHE_DIR",
}


def readConfiguration(build_dir):
    cache = Path(build_dir) / "CMakeCache.txt"
    result = {}
    if cache.is_file():
        for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.match(r"([^:#]+):[^=]*=(.*)", line)
            if match and match.group(1) in CONFIGURATION_KEYS:
                result[match.group(1)] = match.group(2)
    policy = Path(build_dir) / "game-build-policy.json"
    if policy.is_file():
        effective = json.loads(policy.read_text(encoding="utf-8"))
        result.update({key: value for key, value in effective.items() if key in CONFIGURATION_KEYS})
    return result


def compilerIdentity(compiler):
    selected = Path(shutil.which(compiler) or compiler).resolve(strict=True)
    files = [selected]
    frontend = subprocess.run(
        [str(selected), "-print-prog-name=cc1plus"], capture_output=True, text=True, check=True, timeout=30
    ).stdout.strip()
    if Path(frontend).is_file():
        files.append(Path(frontend).resolve())
    if os.environ.get("GAME_REAL_CXX_COMPILER"):
        files.append(Path(os.environ["GAME_REAL_CXX_COMPILER"]).resolve(strict=True))
    digest = hashlib.sha256()
    for path in dict.fromkeys(files):
        digest.update(path.name.encode())
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    machine = subprocess.check_output([str(selected), "-dumpmachine"], text=True, timeout=30).strip()
    version = subprocess.check_output(
        [str(selected), "-dumpfullversion", "-dumpversion"], text=True, timeout=30
    ).strip()
    return re.sub(r"[^A-Za-z0-9_.-]", "-", f"{machine}-{version}-{digest.hexdigest()[:16]}")


def readNinjaLog(build_dir):
    path = Path(build_dir) / ".ninja_log"
    return path.read_bytes() if path.is_file() else b""


def summarizeNinjaLog(previous, current):
    reset = bool(previous) and not current.startswith(previous)
    data = current[len(previous) :] if current.startswith(previous) else current
    edges = {}
    for line in data.decode("utf-8", errors="replace").splitlines():
        fields = line.split("\t")
        if len(fields) != 5 or not fields[0].isdigit() or not fields[1].isdigit():
            continue
        start, end = int(fields[0]), int(fields[1])
        if end < start:
            continue
        # An edge may have multiple outputs (DLL, import library, PDB). Count its work once.
        key = (start, end, fields[4])
        edges.setdefault(key, {"milliseconds": end - start, "output": fields[3]})
    ordered = sorted(edges.values(), key=lambda edge: edge["milliseconds"], reverse=True)
    return {
        "log_rewritten": reset,
        "edge_count": len(ordered),
        "summed_edge_milliseconds": sum(edge["milliseconds"] for edge in ordered),
        "longest_edges": ordered[:12],
    }


def cacheStatistics(tool, configuration):
    if not tool:
        return {}
    executable = os.environ.get("SCCACHE_EXECUTABLE") if tool == "sccache" else None
    executable = executable or shutil.which(tool)
    if not executable:
        return {"tool": tool, "available": False}
    environment = os.environ.copy()
    if tool == "ccache":
        environment["CCACHE_DIR"] = configuration.get("GAME_CCACHE_DIR") or environment.get(
            "CCACHE_DIR", str(Path(__file__).resolve().parents[1] / ".cache" / "ccache")
        )
    arguments = [executable, "--show-stats"]
    if tool == "ccache":
        arguments.append("--verbose")
    result = subprocess.run(arguments, capture_output=True, text=True, env=environment, timeout=30)
    output = (result.stdout + result.stderr)[-16000:]
    print(output, end="" if output.endswith("\n") else "\n", flush=True)
    report = {"tool": tool, "available": True, "exit_code": result.returncode, "verbose_statistics": output}
    if tool == "ccache":
        counters = subprocess.run(
            [executable, "--print-stats"], capture_output=True, text=True, env=environment, timeout=30
        )
        report["counters"] = {
            fields[0]: int(fields[1])
            for line in counters.stdout.splitlines()
            if len(fields := line.split()) == 2 and fields[1].isdigit()
        }
    return report


def runBuild(arguments):
    build_dir = Path(arguments.build_dir)
    configuration = readConfiguration(build_dir)
    previous = readNinjaLog(build_dir)
    try:
        cache_before = cacheStatistics(arguments.cache_tool, configuration)
    except (OSError, subprocess.SubprocessError) as error:
        cache_before = {"diagnostic_error": str(error)}
    start = time.monotonic()
    return_code = 1
    try:
        return_code = subprocess.call(arguments.command)
        return return_code
    finally:
        wall_seconds = round(time.monotonic() - start, 3)
        configuration = readConfiguration(build_dir)
        report = {
            "phase": arguments.phase,
            "exit_code": return_code,
            "wall_seconds": wall_seconds,
            "configuration": configuration,
            "ninja": summarizeNinjaLog(previous, readNinjaLog(build_dir)),
        }
        try:
            report["cache"] = cacheStatistics(arguments.cache_tool, configuration)
            before = cache_before.get("counters", {})
            after = report["cache"].get("counters", {})
            report["cache"]["counter_delta"] = {
                key: value - before.get(key, 0)
                for key, value in after.items()
                if key not in {"stats_updated_timestamp", "stats_zeroed_timestamp"}
            }
        except (OSError, subprocess.SubprocessError) as error:
            report["cache"] = {"diagnostic_error": str(error)}
        output = Path(arguments.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Build phase {arguments.phase}: {wall_seconds:.3f}s; diagnostics: {output}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    identity = commands.add_parser("cache-key")
    identity.add_argument("--compiler", required=True)
    run = commands.add_parser("run")
    run.add_argument("--build-dir", required=True)
    run.add_argument("--output", required=True)
    run.add_argument("--phase", default="compile")
    run.add_argument("--cache-tool", choices=("ccache", "sccache"))
    run.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    if arguments.operation == "cache-key":
        print(compilerIdentity(arguments.compiler))
        return 0
    if arguments.command[:1] == ["--"]:
        arguments.command = arguments.command[1:]
    if not arguments.command:
        parser.error("run requires a command after --")
    return runBuild(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
