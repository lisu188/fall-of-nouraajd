from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import controller_resource_audit


class ControllerResourceAuditTest(unittest.TestCase):
    def test_parse_worktree_porcelain_counts_prunable_records(self) -> None:
        records = controller_resource_audit.parseWorktreePorcelain("""worktree /repo
HEAD abc123
branch refs/heads/main

worktree /tmp/missing
HEAD def456
branch refs/heads/codex/stale
prunable gitdir file points to non-existent location

worktree /tmp/detached
HEAD 123abc
detached
""")

        summary = controller_resource_audit.worktreeSummary(records)

        self.assertEqual(3, summary["total"])
        self.assertEqual(2, summary["active"])
        self.assertEqual(1, summary["prunable"])
        self.assertEqual("/tmp/missing", summary["prunableRecords"][0]["path"])
        self.assertTrue(records[2].detached)

    def test_evaluate_disk_reports_flags_threshold_failures_and_near_limit_warnings(self) -> None:
        reports = [
            controller_resource_audit.DiskReport(
                path="/healthy",
                totalBytes=1000,
                usedBytes=500,
                freeBytes=500,
            ),
            controller_resource_audit.DiskReport(
                path="/full",
                totalBytes=1000,
                usedBytes=970,
                freeBytes=30,
            ),
            controller_resource_audit.DiskReport(
                path="/nearly-full",
                totalBytes=1000,
                usedBytes=910,
                freeBytes=90,
            ),
        ]

        errors, warnings = controller_resource_audit.evaluateDiskReports(
            reports,
            minFreeBytes=50,
            maxUsedPercent=95.0,
        )

        self.assertTrue(any("/full: free disk" in error for error in errors), errors)
        self.assertTrue(any("/full: disk usage 97.0%" in error for error in errors), errors)
        self.assertTrue(any("/nearly-full: disk usage 91.0%" in warning for warning in warnings), warnings)

    def test_discover_run_trees_reports_matching_directory_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_tree = root / "nouraajd-controller-audit"
            run_tree.mkdir()
            (run_tree / "artifact.txt").write_text("x" * 17, encoding="utf-8")
            ignored = root / "other-worktree"
            ignored.mkdir()
            (ignored / "artifact.txt").write_text("x" * 100, encoding="utf-8")

            records = controller_resource_audit.discoverRunTrees([root], "nouraajd-*")

        self.assertEqual(1, len(records))
        self.assertTrue(records[0].path.endswith("nouraajd-controller-audit"))
        self.assertEqual(17, records[0].sizeBytes)

    def test_discover_run_trees_includes_documented_controller_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_tree = root / "fall-of-nouraajd-codex"
            nested_worktree = run_tree / "controller" / "purpose"
            nested_worktree.mkdir(parents=True)
            (nested_worktree / "artifact.txt").write_text("x" * 23, encoding="utf-8")

            records = controller_resource_audit.discoverRunTrees(
                [root],
                controller_resource_audit.DEFAULT_RUN_TREE_PATTERNS,
            )

        self.assertEqual(1, len(records))
        self.assertTrue(records[0].path.endswith("fall-of-nouraajd-codex"))
        self.assertEqual(23, records[0].sizeBytes)


if __name__ == "__main__":
    unittest.main()
