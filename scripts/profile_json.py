#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis. Licensed under GPL-3.0-or-later.
"""Opt-in, reproducible baseline/candidate JSON parsing comparison; no game build required."""

import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import tempfile
from pathlib import Path


def corpusFiles(repo_root):
    paths = set()
    for relative in ("res/config", "res/maps", "tests/fixtures"):
        directory = repo_root / relative
        if directory.exists():
            for path in directory.rglob("*.json"):
                if relative != "tests/fixtures" or "save" in str(path.relative_to(directory)).lower():
                    paths.add(path)
    return sorted(paths)


def runBenchmark(binary, file_list, mode, rounds, samples, cold=False):
    command = [
        str(binary),
        "--file-list",
        str(file_list),
        "--mode",
        mode,
        "--rounds",
        str(rounds),
        "--samples",
        str(samples),
    ]
    if cold:
        command.append("--cold")
    result = json.loads(subprocess.check_output(command, text=True))
    result["command"] = command
    result["median_ms"] = statistics.median(result["sample_ms"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--baseline-benchmark", type=Path, help="Optional earlier-stage benchmark executable")
    parser.add_argument("--baseline-mode", choices=("baseline", "candidate"), default="baseline")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--comparisons", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scratch-dir", type=Path, default=Path(tempfile.gettempdir()))
    parser.add_argument("--manifest-only", action="store_true")
    arguments = parser.parse_args()
    if min(arguments.rounds, arguments.samples, arguments.comparisons) <= 0:
        parser.error("rounds, samples and comparisons must be positive")
    repo_root = arguments.repo_root.resolve()
    paths = corpusFiles(repo_root)
    if not paths:
        parser.error("no configuration, map or save-fixture JSON inputs found")
    manifest = []
    for path in paths:
        content = path.read_bytes()
        manifest.append(
            {
                "path": str(path.relative_to(repo_root)),
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    try:
        revision = subprocess.check_output(["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        revision = "unavailable"
    report = {
        "revision": revision,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "corpus": manifest,
        "corpus_bytes": sum(row["bytes"] for row in manifest),
        "allocation_scope": "C++ new/new[] requests during parse and result destruction; excludes direct malloc",
        "cold": {},
        "comparisons": [],
    }
    if not arguments.manifest_only:
        binary = arguments.benchmark.resolve()
        binaries = {"baseline": (arguments.baseline_benchmark or binary).resolve(), "candidate": binary}
        modes = {"baseline": arguments.baseline_mode, "candidate": "candidate"}
        report["binaries"] = {
            name: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "mode": modes[name]}
            for name, path in binaries.items()
        }
        with tempfile.TemporaryDirectory(prefix="nouraajd-json-profile-", dir=arguments.scratch_dir) as directory:
            file_list = Path(directory) / "corpus-files.txt"
            file_list.write_text("\n".join(str(path) for path in paths) + "\n")
            # Each cold result is a fresh process and excludes file I/O and corpus allocation.
            for mode in ("baseline", "candidate"):
                report["cold"][mode] = runBenchmark(binaries[mode], file_list, modes[mode], 1, 1, cold=True)
            for row, outcome in zip(report["corpus"], report["cold"]["baseline"]["corpus_results"]):
                row.update(outcome)
            if report["cold"]["baseline"]["corpus_results"] != report["cold"]["candidate"]["corpus_results"]:
                raise RuntimeError("cold baseline/candidate corpus acceptance or tree differs")
            for comparison in range(arguments.comparisons):
                order = ("baseline", "candidate") if comparison % 2 == 0 else ("candidate", "baseline")
                pair = {
                    mode: runBenchmark(binaries[mode], file_list, modes[mode], arguments.rounds, arguments.samples)
                    for mode in order
                }
                for field in ("accepted_per_round", "rejected_per_round", "checksum", "corpus_results"):
                    if pair["baseline"][field] != pair["candidate"][field]:
                        raise RuntimeError(f"baseline/candidate {field} differs")
                pair["speedup_percent"] = 100 * (1 - pair["candidate"]["median_ms"] / pair["baseline"]["median_ms"])
                report["comparisons"].append(pair)
                print(
                    f"comparison {comparison + 1}: baseline={pair['baseline']['median_ms']:.3f} ms "
                    f"candidate={pair['candidate']['median_ms']:.3f} ms gain={pair['speedup_percent']:.2f}%",
                    flush=True,
                )
            report["meets_parse_gate"] = all(pair["speedup_percent"] >= 5 for pair in report["comparisons"])
    arguments.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"saved {len(paths)} corpus hashes and benchmark results to {arguments.output}")


if __name__ == "__main__":
    main()
