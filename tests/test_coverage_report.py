from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from scripts import coverage_report


class CoverageReportTest(unittest.TestCase):
    def test_positive_int_rejects_non_integer_and_below_one(self) -> None:
        self.assertEqual(4, coverage_report.positive_int("4"))
        with self.assertRaises(argparse.ArgumentTypeError):
            coverage_report.positive_int("0")
        with self.assertRaises(argparse.ArgumentTypeError):
            coverage_report.positive_int("nope")

    def test_positive_float_rejects_non_number_and_non_positive(self) -> None:
        self.assertEqual(1.5, coverage_report.positive_float("1.5"))
        with self.assertRaises(argparse.ArgumentTypeError):
            coverage_report.positive_float("0")
        with self.assertRaises(argparse.ArgumentTypeError):
            coverage_report.positive_float("-3")
        with self.assertRaises(argparse.ArgumentTypeError):
            coverage_report.positive_float("x")

    def test_normalize_path_resolves_relative_against_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            self.assertEqual(root / "src" / "a.cpp", coverage_report.normalize_path("src/a.cpp", root))
            self.assertEqual(root / "src" / "a.cpp", coverage_report.normalize_path(str(root / "src/a.cpp"), root))

    def test_filesystem_relative_path_uses_matching_ancestor_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            nested = root / "src" / "core"
            nested.mkdir(parents=True)
            self.assertEqual(Path("src/core"), coverage_report.filesystem_relative_path(root, nested))
            self.assertEqual(Path("."), coverage_report.filesystem_relative_path(root, root))

    def test_filesystem_relative_path_raises_for_unrelated_path(self) -> None:
        with tempfile.TemporaryDirectory() as a_dir, tempfile.TemporaryDirectory() as b_dir:
            with self.assertRaises(ValueError):
                coverage_report.filesystem_relative_path(Path(a_dir).resolve(), Path(b_dir).resolve())

    def test_is_included_respects_root_and_prefixes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            (root / "src").mkdir()
            (root / "third_party").mkdir()
            in_src = root / "src" / "a.cpp"
            in_tp = root / "third_party" / "b.cpp"
            outside = Path(tempfile.gettempdir()).resolve() / "definitely-not-under-root.cpp"

            self.assertTrue(coverage_report.is_included(root, in_src))
            self.assertFalse(coverage_report.is_included(root, outside))

            prefixes = coverage_report.load_include_prefixes(root, ["src"])
            self.assertTrue(coverage_report.is_included(root, in_src, prefixes))
            self.assertFalse(coverage_report.is_included(root, in_tp, prefixes))

    def test_validate_include_prefix_rejects_bad_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            (root / "src").mkdir()
            self.assertEqual(root / "src", coverage_report.validate_include_prefix(root, "src"))
            for bad in ["", "/abs/path", "../escape", "src/*", "missing_dir"]:
                with self.assertRaises(ValueError):
                    coverage_report.validate_include_prefix(root, bad)

    def test_merge_line_counts_takes_max_count_per_line_and_filters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            (root / "src").mkdir()
            (root / "other").mkdir()
            reports = [
                {
                    "current_working_directory": str(root),
                    "files": [
                        {
                            "file": "src/a.cpp",
                            "lines": [
                                {"line_number": 1, "count": 0},
                                {"line_number": 2, "count": 3},
                            ],
                        },
                        {
                            "file": "other/b.cpp",
                            "lines": [{"line_number": 1, "count": 5}],
                        },
                    ],
                },
                {
                    "current_working_directory": str(root),
                    "files": [
                        {
                            "file": "src/a.cpp",
                            "lines": [
                                {"line_number": 1, "count": 4},  # higher count wins
                                {"line_number": 2, "count": 1},  # lower count loses
                            ],
                        }
                    ],
                },
            ]
            prefixes = coverage_report.load_include_prefixes(root, ["src"])
            merged = coverage_report.merge_line_counts(root, reports, prefixes)

            self.assertEqual({root / "src" / "a.cpp"}, set(merged))  # other/ filtered out
            self.assertEqual({1: 4, 2: 3}, merged[root / "src" / "a.cpp"])

    def test_summarize_computes_percentages_and_missing_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            merged = {
                root / "src" / "a.cpp": {1: 4, 2: 0, 3: 7},
                root / "src" / "b.cpp": {10: 0, 11: 0},
            }
            summary, covered, total, pct = coverage_report.summarize(root, merged)

            # a.cpp instrumented=3 covered=2 (lines 1,3); b.cpp instrumented=2 covered=0
            self.assertEqual(5, total)
            self.assertEqual(2, covered)
            self.assertAlmostEqual(40.0, pct)
            by_path = {str(item["path"]): item for item in summary}
            self.assertEqual([2], by_path["src/a.cpp"]["missing"])
            self.assertEqual([10, 11], by_path["src/b.cpp"]["missing"])
            self.assertAlmostEqual(100.0 * 2 / 3, by_path["src/a.cpp"]["percentage"])

    def test_summarize_treats_empty_file_as_full_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            summary, covered, total, pct = coverage_report.summarize(root, {root / "src" / "empty.cpp": {}})
            self.assertEqual(0, total)
            self.assertEqual(0, covered)
            self.assertAlmostEqual(100.0, pct)
            self.assertAlmostEqual(100.0, summary[0]["percentage"])

    def test_preview_lines_truncates_after_twenty(self) -> None:
        self.assertEqual("-", coverage_report.preview_lines([]))
        self.assertEqual("1, 2, 3", coverage_report.preview_lines([1, 2, 3]))
        many = coverage_report.preview_lines(list(range(1, 30)))
        self.assertTrue(many.endswith(", ..."))
        self.assertEqual("1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, ...", many)

    def test_write_text_report_emits_total_and_per_file_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "coverage.txt"
            summary = [{"path": Path("src/a.cpp"), "lines": 3, "covered": 2, "missing": [2], "percentage": 66.67}]
            coverage_report.write_text_report(report_path, summary, 2, 3, 66.67)
            text = report_path.read_text(encoding="utf-8")
            self.assertIn("TOTAL 2/3 eligible lines covered (66.67%)", text)
            self.assertIn("src/a.cpp: 2/3 (66.67%) missing [2]", text)

    def test_write_html_report_escapes_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "coverage.html"
            summary = [{"path": Path("src/<x>.cpp"), "lines": 1, "covered": 1, "missing": [], "percentage": 100.0}]
            coverage_report.write_html_report(report_path, summary, 1, 1, 100.0)
            html_text = report_path.read_text(encoding="utf-8")
            self.assertIn("src/&lt;x&gt;.cpp", html_text)
            self.assertNotIn("<x>.cpp", html_text)


if __name__ == "__main__":
    unittest.main()
