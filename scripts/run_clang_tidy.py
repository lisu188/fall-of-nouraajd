#!/usr/bin/env python3
"""Run clang-tidy only on first-party translation units in a CMake compilation database."""

from __future__ import annotations

import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Sequence

SOURCE_ROOTS = frozenset({"src", "native_plugins"})
SOURCE_EXTENSIONS = frozenset({".cc", ".cpp", ".cxx"})
HEADER_EXTENSIONS = frozenset({".h", ".hh", ".hpp", ".hxx", ".inl", ".ipp", ".tpp"})


def projectSources(database: Path, repository: Path, changed: set[str] | None = None) -> list[Path]:
    rows: object = json.loads(database.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("compile_commands.json must contain an array")

    sources: set[Path] = set()
    root = repository.resolve()
    if changed is not None and any(Path(path).suffix.lower() in HEADER_EXTENSIONS for path in changed):
        changed = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        directory, filename = row.get("directory"), row.get("file")
        if not isinstance(directory, str) or not isinstance(filename, str):
            continue
        source = (Path(directory) / filename).resolve()
        try:
            relative = source.relative_to(root)
        except ValueError:
            continue
        if not relative.parts or relative.parts[0] not in SOURCE_ROOTS:
            continue
        if source.suffix not in SOURCE_EXTENSIONS or not source.is_file():
            continue
        if changed is None or relative.as_posix() in changed:
            sources.add(source)
    return sorted(sources)


def changedSources(repository: Path, base: str) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD", "--", "src", "native_plugins"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return set(result.stdout.splitlines())


def analyze(source: Path, repository: Path, build_dir: Path, report_dir: Path, executable: str) -> int:
    relative = source.relative_to(repository)
    result = subprocess.run(
        [executable, "--quiet", "-p", str(build_dir), str(source)],
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    destination = (report_dir / relative).with_suffix(".txt")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(output or "No findings.\n", encoding="utf-8")
    print(f"{relative}: {'FAILED' if result.returncode else 'scanned'}", flush=True)
    if result.returncode:
        print(output[-5000:], flush=True)
    return result.returncode


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--report-dir", type=Path, default=Path("analysis-reports/clang-tidy"))
    parser.add_argument("--changed-base")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--executable", default="clang-tidy-20")
    args = parser.parse_args(argv)

    if args.jobs < 1:
        parser.error("--jobs must be positive")

    repository = args.repo_root.resolve()
    build_dir = args.build_dir.resolve()
    database = build_dir / "compile_commands.json"
    changed = changedSources(repository, args.changed_base) if args.changed_base else None
    sources = projectSources(database, repository, changed)
    print(f"clang-tidy selected {len(sources)} first-party translation units", flush=True)
    if not sources:
        return 0

    report_dir = args.report_dir.resolve()
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        results = list(
            executor.map(lambda source: analyze(source, repository, build_dir, report_dir, args.executable), sources)
        )

    failures = sum(status != 0 for status in results)
    print(f"clang-tidy completed {len(sources)} files; {failures} failed", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
