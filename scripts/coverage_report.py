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
    parser.add_argument("--line-exclusions", type=Path, help="Reviewed root-relative line exclusion manifest.")
    parser.add_argument(
        "--include-prefix",
        action="append",
        default=[],
        help="Root-relative source path prefix to include. May be repeated. Defaults to the full repository.",
    )
    parser.add_argument(
        "--audit-exclusions",
        action="store_true",
        help="Write exclusion audit reports with raw hit counts and source snippets.",
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


def normalize_path(path_str: str, cwd: Path) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        path = cwd / path
    return path.resolve()


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
        include_path.relative_to(root)
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
        resolved.relative_to(root)
    except ValueError:
        return False
    if not include_prefixes:
        return True
    for include_prefix in include_prefixes:
        try:
            resolved.relative_to(include_prefix.resolve())
            return True
        except ValueError:
            pass
    return False


def validate_exclusion_path(root: Path, rel_path_str: str) -> Path:
    root = root.resolve()
    if not isinstance(rel_path_str, str) or not rel_path_str:
        raise ValueError("coverage exclusion paths must be non-empty strings")
    rel_path = Path(rel_path_str)
    if rel_path.is_absolute():
        raise ValueError(f"coverage exclusion path must be root-relative: {rel_path_str}")
    if any(part in {"", ".", ".."} for part in rel_path.parts):
        raise ValueError(f"coverage exclusion path must be normalized: {rel_path_str}")
    if any(char in rel_path_str for char in "*?[]"):
        raise ValueError(f"coverage exclusion path cannot use glob syntax: {rel_path_str}")

    source_path = (root / rel_path).resolve()
    try:
        source_path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"coverage exclusion path escapes repository root: {rel_path_str}") from exc
    if not source_path.exists():
        raise ValueError(f"coverage exclusion path does not exist: {rel_path_str}")
    return source_path


def load_line_exclusions(root: Path, manifest_path: Path | None):
    if manifest_path is None:
        return {}

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("coverage exclusion manifest must be an object with version 1")
    entries = data.get("exclusions")
    if not isinstance(entries, list):
        raise ValueError("coverage exclusion manifest must contain an exclusions list")

    exclusions = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"coverage exclusion entry {index} must be an object")
        source_path = validate_exclusion_path(root, entry.get("path"))

        reason = entry.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"coverage exclusion for {entry.get('path')} must include a reason")

        ranges = entry.get("ranges")
        if not isinstance(ranges, list) or not ranges:
            raise ValueError(f"coverage exclusion for {entry.get('path')} must include non-empty ranges")

        line_reasons = exclusions.setdefault(source_path, {})
        for range_index, line_range in enumerate(ranges):
            if isinstance(line_range, str):
                parts = line_range.split("-", maxsplit=1)
                if not parts[0] or len(parts) > 2 or (len(parts) == 2 and not parts[1]):
                    raise ValueError(f"coverage exclusion range {range_index} for {entry.get('path')} is invalid")
                try:
                    start = int(parts[0])
                    end = int(parts[1]) if len(parts) == 2 else start
                except ValueError as exc:
                    raise ValueError(
                        f"coverage exclusion range {range_index} for {entry.get('path')} is invalid"
                    ) from exc
            elif (
                isinstance(line_range, list)
                and len(line_range) == 2
                and all(isinstance(value, int) for value in line_range)
            ):
                start, end = line_range
            else:
                raise ValueError(
                    f"coverage exclusion range {range_index} for {entry.get('path')} must be [start, end] "
                    "or 'start-end'"
                )
            if start < 1 or end < start:
                raise ValueError(f"coverage exclusion range {range_index} for {entry.get('path')} is invalid")
            for line_number in range(start, end + 1):
                line_reasons.setdefault(line_number, reason.strip())

    return exclusions


def validate_line_exclusions(root: Path, merged, exclusions):
    root = root.resolve()
    for source_path, line_reasons in exclusions.items():
        source_path = source_path.resolve()
        rel_path = source_path.relative_to(root)
        if source_path not in merged:
            raise ValueError(f"coverage exclusion path is stale or was not instrumented: {rel_path}")

        instrumented_lines = {line_number for line_number in merged[source_path] if line_number > 0}
        stale_lines = sorted(set(line_reasons) - instrumented_lines)
        if stale_lines:
            preview = ", ".join(str(line) for line in stale_lines[:10])
            if len(stale_lines) > 10:
                preview += ", ..."
            raise ValueError(f"coverage exclusion for {rel_path} references non-instrumented line(s): {preview}")

        if instrumented_lines and instrumented_lines.issubset(line_reasons):
            raise ValueError(f"coverage exclusion for {rel_path} would exclude the entire instrumented file")


def scope_line_exclusions(root: Path, exclusions, include_prefixes=()):
    if not include_prefixes:
        return exclusions
    return {
        source_path: dict(line_reasons)
        for source_path, line_reasons in exclusions.items()
        if is_included(root, source_path, include_prefixes)
    }


def collect_reports_for_gcda(gcda: Path, output_dir: Path):
    output_dir.mkdir()
    subprocess.run(
        ["gcov", "-j", "-p", str(gcda)],
        cwd=output_dir,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    reports = []
    for report_path in sorted(output_dir.glob("*.gcov.json.gz")):
        with gzip.open(report_path, "rt", encoding="utf-8") as fh:
            reports.append(json.load(fh))
    return reports


def collect_gcov_reports(build_dir: Path, jobs: int):
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
                reports.extend(collect_reports_for_gcda(gcda, tmp_path / f"gcov-{index}"))
            return reports

        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
            futures = [
                executor.submit(collect_reports_for_gcda, gcda, tmp_path / f"gcov-{index}")
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


def summarize(root: Path, merged, exclusions=None):
    root = root.resolve()
    exclusions = exclusions or {}
    summary = []
    total_lines = 0
    covered_lines = 0
    excluded_lines = 0

    for source_path in sorted(merged):
        line_counts = merged[source_path]
        excluded = sorted(line for line in exclusions.get(source_path, {}) if line in line_counts and line > 0)
        excluded_set = set(excluded)
        instrumented = sum(1 for line_number in line_counts if line_number > 0 and line_number not in excluded_set)
        covered = sum(
            1
            for line_number, count in line_counts.items()
            if line_number > 0 and line_number not in excluded_set and count > 0
        )
        percentage = 100.0 if instrumented == 0 else (covered * 100.0 / instrumented)
        missing = [
            line for line, count in sorted(line_counts.items()) if line > 0 and line not in excluded_set and count == 0
        ]
        rel_path = source_path.resolve().relative_to(root)
        summary.append(
            {
                "path": rel_path,
                "lines": instrumented,
                "covered": covered,
                "excluded": excluded,
                "exclusion_reasons": exclusions.get(source_path, {}),
                "missing": missing,
                "percentage": percentage,
            }
        )
        total_lines += instrumented
        covered_lines += covered
        excluded_lines += len(excluded)

    total_percentage = 100.0 if total_lines == 0 else (covered_lines * 100.0 / total_lines)
    return summary, covered_lines, total_lines, total_percentage, excluded_lines


def preview_lines(lines):
    preview = ", ".join(str(line) for line in lines[:20])
    if len(lines) > 20:
        preview += ", ..."
    return preview or "-"


def write_text_report(
    report_path: Path, summary, covered_lines: int, total_lines: int, total_percentage: float, excluded_lines: int
):
    lines = [
        f"TOTAL {covered_lines}/{total_lines} eligible lines covered ({total_percentage:.2f}%), "
        f"{excluded_lines} excluded",
        "",
    ]
    for item in summary:
        lines.append(
            f"{item['path']}: {item['covered']}/{item['lines']} "
            f"({item['percentage']:.2f}%) excluded {len(item['excluded'])} "
            f"missing [{preview_lines(item['missing'])}] excluded_lines [{preview_lines(item['excluded'])}]"
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html_report(
    report_path: Path, summary, covered_lines: int, total_lines: int, total_percentage: float, excluded_lines: int
):
    rows = []
    for item in summary:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(item['path']))}</td>"
            f"<td>{item['covered']}/{item['lines']}</td>"
            f"<td>{item['percentage']:.2f}%</td>"
            f"<td>{len(item['excluded'])}</td>"
            f"<td>{html.escape(preview_lines(item['missing']))}</td>"
            f"<td>{html.escape(preview_lines(item['excluded']))}</td>"
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
                f"eligible lines covered ({total_percentage:.2f}%), {excluded_lines} excluded</p>",
                "<table><thead><tr><th>File</th><th>Covered</th><th>Percent</th><th>Excluded</th>"
                "<th>Missing lines</th><th>Excluded lines</th></tr></thead><tbody>",
                *rows,
                "</tbody></table></body></html>",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def build_exclusion_audit(root: Path, merged, exclusions):
    lines = []
    for source_path in sorted(exclusions):
        line_counts = merged.get(source_path, {})
        try:
            source_lines = source_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            source_lines = []
        for line_number, reason in sorted(exclusions[source_path].items()):
            if line_number <= 0 or line_number not in line_counts:
                continue
            count = line_counts[line_number]
            snippet = source_lines[line_number - 1].strip() if line_number <= len(source_lines) else ""
            lines.append(
                {
                    "path": source_path.relative_to(root).as_posix(),
                    "line": line_number,
                    "count": count,
                    "covered": count > 0,
                    "reason": reason,
                    "source": snippet,
                }
            )

    covered = sum(1 for line in lines if line["covered"])
    return {
        "total": len(lines),
        "covered": covered,
        "uncovered": len(lines) - covered,
        "lines": lines,
    }


def write_exclusion_audit_text(report_path: Path, audit):
    lines = [
        f"EXCLUDED LINES {audit['total']} total, {audit['covered']} covered, {audit['uncovered']} uncovered",
        "",
    ]
    for item in audit["lines"]:
        status = "covered" if item["covered"] else "uncovered"
        lines.append(
            f"{item['path']}:{item['line']} count={item['count']} {status} "
            f"reason={json.dumps(item['reason'])} source={json.dumps(item['source'])}"
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_exclusion_audit_json(report_path: Path, audit):
    report_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    args = parse_args()
    root = args.root.resolve()
    build_dir = args.build_dir.resolve()
    report_dir = args.report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    include_prefixes = load_include_prefixes(root, args.include_prefix)
    exclusions = load_line_exclusions(root, args.line_exclusions)
    reports = collect_gcov_reports(build_dir, args.jobs)
    merged = merge_line_counts(root, reports, include_prefixes)
    exclusions = scope_line_exclusions(root, exclusions, include_prefixes)
    validate_line_exclusions(root, merged, exclusions)
    summary, covered_lines, total_lines, total_percentage, excluded_lines = summarize(root, merged, exclusions)

    write_text_report(
        report_dir / "coverage.txt", summary, covered_lines, total_lines, total_percentage, excluded_lines
    )
    write_html_report(
        report_dir / "coverage.html", summary, covered_lines, total_lines, total_percentage, excluded_lines
    )
    if args.audit_exclusions:
        audit = build_exclusion_audit(root, merged, exclusions)
        write_exclusion_audit_text(report_dir / "exclusion_audit.txt", audit)
        write_exclusion_audit_json(report_dir / "exclusion_audit.json", audit)
        print("exclusions: " f"{audit['total']} total ({audit['covered']} covered, {audit['uncovered']} uncovered)")

    print(f"lines: {total_percentage:.2f}% ({covered_lines} out of {total_lines}, {excluded_lines} excluded)")
    if total_percentage < args.min_line:
        print(f"ERROR: line coverage {total_percentage:.2f}% is below required {args.min_line:.2f}%")
        return 2
    print(f"Coverage reports written to {report_dir / 'coverage.txt'} and {report_dir / 'coverage.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
