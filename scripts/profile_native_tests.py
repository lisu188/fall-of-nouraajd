# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

"""Run complete native binaries under Callgrind; this is separate from CTest validation."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SUITE_BINARIES = {"handler": "handler_unit_tests", "map": "map_unit_tests"}
DISPLAY_ENVIRONMENT = {
    "SDL_VIDEODRIVER": "x11",
    "SDL_AUDIODRIVER": "dummy",
    "SDL_RENDER_DRIVER": "software",
    "LIBGL_ALWAYS_SOFTWARE": "1",
}
CACHE_KEYS = ("CMAKE_BUILD_TYPE", "CMAKE_CXX_COMPILER", "CMAKE_CXX_FLAGS", "CMAKE_CXX_FLAGS_RELWITHDEBINFO")


def projectPath(repo_root, value):
    path = Path(value)
    if not path.is_absolute():
        path = repo_root / path
    path = path.resolve()
    if path == repo_root or not path.is_relative_to(repo_root):
        raise ValueError("Profiling paths must be inside the selected repository: " + str(path))
    return path


def selectedTools():
    if not sys.platform.startswith("linux"):
        raise RuntimeError("Native Callgrind profiling requires Linux and a virtual X11 display")
    tools = {}
    for name in ("valgrind", "callgrind_annotate", "xvfb-run", "xauth"):
        tools[name] = shutil.which(name)
        if tools[name] is None:
            raise RuntimeError("Required profiling tool is unavailable: " + name)
    return tools


def commandInfo(command, cwd):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=15)
    lines = (result.stdout + result.stderr).splitlines()
    return {"command": command, "returnCode": result.returncode, "firstLine": lines[0] if lines else ""}


def buildMetadata(repo_root, build_dir, tools):
    cache_path = build_dir / "CMakeCache.txt"
    cache = {}
    if cache_path.is_file():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"([^:]+):[^=]+=(.*)$", line)
            if match and match.group(1) in CACHE_KEYS:
                cache[match.group(1)] = match.group(2)
    compiler = cache.get("CMAKE_CXX_COMPILER", "c++")
    return {
        "checkout": commandInfo(["git", "rev-parse", "HEAD"], repo_root),
        "parents": commandInfo(["git", "show", "-s", "--format=%P", "HEAD"], repo_root),
        "cmake": cache,
        "compiler": commandInfo([compiler, "--version"], repo_root),
        "valgrind": commandInfo([tools["valgrind"], "--version"], repo_root),
        "callgrindAnnotate": commandInfo([tools["callgrind_annotate"], "--version"], repo_root),
        "display": DISPLAY_ENVIRONMENT,
    }


def profileCommand(binary, profile_path, valgrind_log, tools):
    return [
        tools["xvfb-run"],
        "-a",
        "--server-args=-screen 0 1920x1080x24",
        tools["valgrind"],
        "--tool=callgrind",
        "--callgrind-out-file=" + str(profile_path),
        "--log-file=" + str(valgrind_log),
        str(binary),
    ]


def validProfile(profile_path):
    if not profile_path.is_file() or profile_path.stat().st_size == 0:
        return False
    events = []
    counts = []
    with profile_path.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            if line.startswith("events:"):
                events = line.split()[1:]
            elif line.startswith("summary:"):
                counts = line.split()[1:]
            if (
                "Ir" in events
                and len(counts) == len(events)
                and all(value.isdecimal() for value in counts)
                and int(counts[events.index("Ir")]) > 0
            ):
                return True
    return False


def annotateProfile(profile_path, output_dir, tools):
    summaries = []
    for kind in ("exclusive", "inclusive"):
        command = [
            tools["callgrind_annotate"],
            "--auto=no",
            "--show=Ir",
            "--inclusive=" + ("yes" if kind == "inclusive" else "no"),
            "--tree=both",
            str(profile_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        target = output_dir / (kind + ".txt")
        target.write_text(result.stdout + result.stderr, encoding="utf-8")
        summaries.append({"kind": kind, "command": command, "returnCode": result.returncode, "file": str(target)})
    return summaries


def runProfile(suite, binary, build_dir, output_dir, tools, timeout_seconds):
    output_dir.mkdir()
    profile_path = output_dir / "callgrind.out"
    command = profileCommand(binary, profile_path, output_dir / "valgrind.log", tools)
    environment = os.environ.copy()
    environment.update(DISPLAY_ENVIRONMENT)
    started = time.monotonic()
    timed_out = False
    record = {"suite": suite, "command": command, "diagnosticTimeoutSeconds": timeout_seconds}
    with (output_dir / "native.stdout.log").open("w") as stdout, (output_dir / "native.stderr.log").open("w") as stderr:
        process = subprocess.Popen(
            command, cwd=build_dir, env=environment, stdout=stdout, stderr=stderr, start_new_session=True
        )
        try:
            return_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            # Give Callgrind a chance to retain its partial counters before forcing termination.
            try:
                os.killpg(process.pid, signal.SIGINT)
            except ProcessLookupError:
                pass
            try:
                return_code = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                return_code = process.wait(timeout=10)
    record.update(
        {
            "nativeReturnCode": return_code,
            "timedOut": timed_out,
            "wallSeconds": time.monotonic() - started,
            "profile": str(profile_path),
            "profileReadable": validProfile(profile_path),
        }
    )
    record["status"] = "timeout" if timed_out else "native-failure" if return_code else "completed"
    record["complete"] = not timed_out and return_code == 0 and record["profileReadable"]
    if not record["profileReadable"] and record["status"] == "completed":
        record["status"] = "missing-profile"
    if record["profileReadable"]:
        try:
            record["summaries"] = annotateProfile(profile_path, output_dir, tools)
            annotation_succeeded = all(item["returnCode"] == 0 for item in record["summaries"])
            record["complete"] = record["complete"] and annotation_succeeded
            if not annotation_succeeded and record["status"] == "completed":
                record["status"] = "annotation-failure"
        except (OSError, subprocess.TimeoutExpired) as error:
            record["annotationError"] = str(error)
            record["complete"] = False
            if record["status"] == "completed":
                record["status"] = "annotation-failure"
    (output_dir / "result.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def run(args):
    repo_root = args.repo_root.resolve()
    build_dir = projectPath(repo_root, args.build_dir)
    output_dir = projectPath(repo_root, args.output_dir)
    if not 1 <= args.timeout_seconds <= 3600:
        raise ValueError("The diagnostic timeout must be between 1 and 3600 seconds")
    tools = selectedTools()
    suites = tuple(SUITE_BINARIES) if args.suite == "both" else (args.suite,)
    binaries = {suite: projectPath(repo_root, build_dir / SUITE_BINARIES[suite]) for suite in suites}
    native_timing_files = {
        suite: projectPath(repo_root, Path("coverage/native-test-profiles") / (suite + ".tsv")) for suite in suites
    }
    if not args.metadata_only:
        for binary in binaries.values():
            if not binary.is_file():
                raise RuntimeError("Build the complete native test target before profiling: " + str(binary))
        for timing_file in native_timing_files.values():
            if timing_file.exists():
                raise ValueError("Preserve earlier native timing evidence before profiling: " + str(timing_file))
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(
            "Preserve existing profiling evidence and choose an empty output directory: " + str(output_dir)
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schemaVersion": 1,
        "startedUtc": datetime.now(timezone.utc).isoformat(),
        "kind": "diagnostic-callgrind-setup" if args.metadata_only else "diagnostic-callgrind",
        "normalCTestTimeoutUnchanged": 60,
        "nativeTimingFiles": {suite: str(path) for suite, path in native_timing_files.items()},
        "metadata": buildMetadata(repo_root, build_dir, tools),
        "results": [],
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if args.metadata_only:
        return 0
    for suite, binary in binaries.items():
        try:
            record = runProfile(suite, binary, build_dir, output_dir / suite, tools, args.timeout_seconds)
        except (OSError, subprocess.TimeoutExpired) as error:
            record = {"suite": suite, "status": "runner-failure", "complete": False, "error": str(error)}
        manifest["results"].append(record)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(suite + ": " + record["status"], flush=True)
    return 0 if all(record["complete"] for record in manifest["results"]) else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--build-dir", type=Path, default=Path("cmake-build-relwithdebinfo"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--suite", choices=("handler", "map", "both"), default="both")
    parser.add_argument("--metadata-only", action="store_true", help="Record selected metadata without running tests")
    parser.add_argument(
        "--timeout-seconds", type=int, default=1800, help="Diagnostic limit; does not change CTest gates"
    )
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
