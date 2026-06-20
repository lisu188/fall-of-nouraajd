#!/usr/bin/env python3
import argparse
import concurrent.futures
import gzip
import html
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Generate coverage reports from gcov JSON output.")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--report-dir", required=True, type=Path)
    parser.add_argument("--min-line", required=True, type=float)
    parser.add_argument("--jobs", default=max(1, os.cpu_count() or 1), type=positive_int)
    parser.add_argument(
        "--gcov-timeout",
        default=positive_float(os.environ.get("COVERAGE_GCOV_TIMEOUT_SECONDS", "120")),
        type=positive_float,
        help="Seconds allowed for each gcov JSON extraction command.",
    )
    parser.add_argument(
        "--include-prefix",
        action="append",
        default=[],
        help="Root-relative source path prefix to include. May be repeated. Defaults to the full repository.",
    )
    return parser.parse_args()


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("--jobs must be at least 1")
    return parsed


def positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("--gcov-timeout must be greater than 0")
    return parsed


def normalize_path(path_str: str, cwd: Path) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        path = cwd / path
    return path.resolve()


def filesystem_relative_path(root: Path, path: Path) -> Path:
    root = root.resolve()
    path = path.resolve()
    try:
        return path.relative_to(root)
    except ValueError:
        matching_relative_path = relative_path_from_matching_ancestor(root, path)
        if matching_relative_path is not None:
            return matching_relative_path
        raise


def relative_path_from_matching_ancestor(root: Path, path: Path) -> Path | None:
    suffix = []
    current = path
    while True:
        try:
            if current.samefile(root):
                return Path(*reversed(suffix)) if suffix else Path(".")
        except OSError:
            return None
        if current.parent == current:
            return None
        suffix.append(current.name)
        current = current.parent


def validate_include_prefix(root: Path, prefix_str: str) -> Path:
    root = root.resolve()
    if not isinstance(prefix_str, str) or not prefix_str:
        raise ValueError("coverage include prefixes must be non-empty strings")
    prefix = Path(prefix_str)
    if prefix.is_absolute():
        raise ValueError(f"coverage include prefix must be root-relative: {prefix_str}")
    if any(part in {"", ".", ".."} for part in prefix.parts):
        raise ValueError(f"coverage include prefix must be normalized: {prefix_str}")
    if any(char in prefix_str for char in "*?[]"):
        raise ValueError(f"coverage include prefix cannot use glob syntax: {prefix_str}")

    include_path = (root / prefix).resolve()
    try:
        filesystem_relative_path(root, include_path)
    except ValueError as exc:
        raise ValueError(f"coverage include prefix escapes repository root: {prefix_str}") from exc
    if not include_path.exists():
        raise ValueError(f"coverage include prefix does not exist: {prefix_str}")
    return include_path


def load_include_prefixes(root: Path, include_prefixes):
    return tuple(validate_include_prefix(root, prefix) for prefix in include_prefixes)


def is_included(root: Path, source_path: Path, include_prefixes=()) -> bool:
    root = root.resolve()
    try:
        resolved = source_path.resolve()
        filesystem_relative_path(root, resolved)
    except ValueError:
        return False
    if not include_prefixes:
        return True
    for include_prefix in include_prefixes:
        try:
            filesystem_relative_path(include_prefix, resolved)
            return True
        except ValueError:
            pass
    return False


def collect_reports_for_gcda(gcda: Path, output_dir: Path, timeout_seconds: float):
    output_dir.mkdir()
    try:
        subprocess.run(
            ["gcov", "-j", "-p", str(gcda)],
            cwd=output_dir,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"gcov timed out after {timeout_seconds:g}s for {gcda}") from exc

    reports = []
    for report_path in sorted(output_dir.glob("*.gcov.json.gz")):
        with gzip.open(report_path, "rt", encoding="utf-8") as fh:
            reports.append(json.load(fh))
    return reports


def collect_gcov_reports(build_dir: Path, jobs: int, timeout_seconds: float):
    gcda_files = sorted(build_dir.rglob("*.gcda"))
    if not gcda_files:
        raise RuntimeError(f"No .gcda files found under {build_dir}")

    with tempfile.TemporaryDirectory(prefix="game-gcov-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        reports = []
        jobs = min(jobs, len(gcda_files))
        print(f"Collecting gcov reports from {len(gcda_files)} data files with {jobs} job(s)")

        if jobs == 1:
            for index, gcda in enumerate(gcda_files):
                reports.extend(collect_reports_for_gcda(gcda, tmp_path / f"gcov-{index}", timeout_seconds))
            return reports

        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
            futures = [
                executor.submit(collect_reports_for_gcda, gcda, tmp_path / f"gcov-{index}", timeout_seconds)
                for index, gcda in enumerate(gcda_files)
            ]
            for future in concurrent.futures.as_completed(futures):
                reports.extend(future.result())
        return reports


def merge_line_counts(root: Path, reports, include_prefixes=()):
    merged = {}
    for report in reports:
        cwd = Path(report.get("current_working_directory", root))
        for file_data in report.get("files", []):
            source_path = normalize_path(file_data["file"], cwd)
            if not is_included(root, source_path, include_prefixes):
                continue

            file_lines = merged.setdefault(source_path, {})
            for line_data in file_data.get("lines", []):
                line_number = int(line_data["line_number"])
                count = int(line_data["count"])
                file_lines[line_number] = max(file_lines.get(line_number, 0), count)
    return merged


def summarize(root: Path, merged):
    root = root.resolve()
    summary = []
    total_lines = 0
    covered_lines = 0

    for source_path in sorted(merged):
        line_counts = merged[source_path]
        instrumented = sum(1 for line_number in line_counts if line_number > 0)
        covered = sum(1 for line_number, count in line_counts.items() if line_number > 0 and count > 0)
        percentage = 100.0 if instrumented == 0 else (covered * 100.0 / instrumented)
        missing = [line for line, count in sorted(line_counts.items()) if line > 0 and count == 0]
        rel_path = filesystem_relative_path(root, source_path)
        summary.append(
            {
                "path": rel_path,
                "lines": instrumented,
                "covered": covered,
                "missing": missing,
                "percentage": percentage,
            }
        )
        total_lines += instrumented
        covered_lines += covered

    total_percentage = 100.0 if total_lines == 0 else (covered_lines * 100.0 / total_lines)
    return summary, covered_lines, total_lines, total_percentage


def preview_lines(lines):
    preview = ", ".join(str(line) for line in lines[:20])
    if len(lines) > 20:
        preview += ", ..."
    return preview or "-"


def write_text_report(report_path: Path, summary, covered_lines: int, total_lines: int, total_percentage: float):
    lines = [
        f"TOTAL {covered_lines}/{total_lines} eligible lines covered ({total_percentage:.2f}%)",
        "",
    ]
    for item in summary:
        lines.append(
            f"{item['path']}: {item['covered']}/{item['lines']} "
            f"({item['percentage']:.2f}%) missing [{preview_lines(item['missing'])}]"
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html_report(report_path: Path, summary, covered_lines: int, total_lines: int, total_percentage: float):
    rows = []
    for item in summary:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(item['path']))}</td>"
            f"<td>{item['covered']}/{item['lines']}</td>"
            f"<td>{item['percentage']:.2f}%</td>"
            f"<td>{html.escape(preview_lines(item['missing']))}</td>"
            "</tr>"
        )

    report_path.write_text(
        "\n".join(
            [
                "<!doctype html>",
                "<html><head><meta charset='utf-8'><title>Coverage Report</title>",
                "<style>body{font-family:sans-serif;margin:24px}table{border-collapse:collapse;width:100%}"
                "th,td{border:1px solid #ccc;padding:6px 8px;text-align:left}th{background:#f5f5f5}"
                "</style></head><body>",
                f"<h1>Coverage Report</h1><p><strong>Total:</strong> {covered_lines}/{total_lines} "
                f"eligible lines covered ({total_percentage:.2f}%)</p>",
                "<table><thead><tr><th>File</th><th>Covered</th><th>Percent</th>"
                "<th>Missing lines</th></tr></thead><tbody>",
                *rows,
                "</tbody></table></body></html>",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main():
    args = parse_args()
    root = args.root.resolve()
    build_dir = args.build_dir.resolve()
    report_dir = args.report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    include_prefixes = load_include_prefixes(root, args.include_prefix)
    reports = collect_gcov_reports(build_dir, args.jobs, args.gcov_timeout)
    merged = merge_line_counts(root, reports, include_prefixes)
    summary, covered_lines, total_lines, total_percentage = summarize(root, merged)

    write_text_report(report_dir / "coverage.txt", summary, covered_lines, total_lines, total_percentage)
    write_html_report(report_dir / "coverage.html", summary, covered_lines, total_lines, total_percentage)

    print(f"lines: {total_percentage:.2f}% ({covered_lines} out of {total_lines})")
    if total_percentage < args.min_line:
        print(f"ERROR: line coverage {total_percentage:.2f}% is below required {args.min_line:.2f}%")
        return 2
    print(f"Coverage reports written to {report_dir / 'coverage.txt'} and {report_dir / 'coverage.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
