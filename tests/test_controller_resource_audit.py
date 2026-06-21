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

    def test_find_empty_loose_objects_reports_relative_object_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            git_common_dir = Path(temp_dir)
            empty_object = git_common_dir / "objects" / "ab" / "1234"
            empty_object.parent.mkdir(parents=True)
            empty_object.touch()
            non_empty_object = git_common_dir / "objects" / "cd" / "5678"
            non_empty_object.parent.mkdir(parents=True)
            non_empty_object.write_text("not empty", encoding="utf-8")

            records = controller_resource_audit.findEmptyLooseObjects(git_common_dir)

        self.assertEqual(("ab/1234",), records)

    def test_find_empty_refs_reports_relative_ref_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            git_common_dir = Path(temp_dir)
            empty_ref = git_common_dir / "refs" / "remotes" / "origin" / "broken"
            empty_ref.parent.mkdir(parents=True)
            empty_ref.touch()
            non_empty_ref = git_common_dir / "refs" / "heads" / "main"
            non_empty_ref.parent.mkdir(parents=True)
            non_empty_ref.write_text("abc123\n", encoding="utf-8")

            records = controller_resource_audit.findEmptyRefs(git_common_dir)

        self.assertEqual(("refs/remotes/origin/broken",), records)

    def test_evaluate_git_health_flags_unreadable_repository_state(self) -> None:
        report = controller_resource_audit.GitHealthReport(
            statusExitCode=128,
            statusStdout="",
            statusStderr="fatal: bad object HEAD",
            head=None,
            originMain=None,
            gitCommonDir="/repo/.git",
            emptyLooseObjects=("48/6a2ad72f8ff03edd3bca9ec9ff76cb2c81b612",),
            emptyRefs=("refs/remotes/origin/broken",),
        )

        errors, warnings = controller_resource_audit.evaluateGitHealth(report)

        self.assertEqual([], warnings)
        self.assertTrue(any("git status failed with exit code 128" in error for error in errors), errors)
        self.assertIn("HEAD could not be resolved", errors)
        self.assertIn("refs/remotes/origin/main could not be resolved", errors)
        self.assertIn("1 zero-byte loose git object(s) found", errors)
        self.assertIn("1 zero-byte git ref file(s) found", errors)

    def test_required_checks_support_contexts_and_rich_check_payloads(self) -> None:
        checks = controller_resource_audit.requiredChecksFromProtectionPayload(
            {
                "required_status_checks": {
                    "contexts": ["linux", "windows-deps"],
                    "checks": [{"context": "windows"}, {"context": "linux"}],
                }
            }
        )

        self.assertEqual(("linux", "windows", "windows-deps"), checks)

    def test_branch_protection_report_flags_unprotected_branch(self) -> None:
        report = controller_resource_audit.branchProtectionReportFromPayloads(
            "owner/repo",
            "main",
            ("linux", "windows-deps", "windows"),
            {"protected": False},
            None,
        )

        errors, warnings = controller_resource_audit.evaluateBranchProtection(report)

        self.assertEqual([], errors)
        self.assertEqual(("linux", "windows-deps", "windows"), report.missingRequiredChecks)
        self.assertTrue(any("branch is not protected" in warning for warning in warnings), warnings)

    def test_branch_protection_report_flags_missing_required_checks(self) -> None:
        report = controller_resource_audit.branchProtectionReportFromPayloads(
            "owner/repo",
            "main",
            ("linux", "windows-deps", "windows"),
            {"protected": True},
            {"required_status_checks": {"contexts": ["linux"], "checks": [{"context": "windows"}]}},
        )

        errors, warnings = controller_resource_audit.evaluateBranchProtection(report)

        self.assertEqual([], errors)
        self.assertEqual(("windows-deps",), report.missingRequiredChecks)
        self.assertTrue(any("missing required check(s): windows-deps" in warning for warning in warnings), warnings)

    def test_branch_protection_report_accepts_expected_checks(self) -> None:
        report = controller_resource_audit.branchProtectionReportFromPayloads(
            "owner/repo",
            "main",
            ("linux", "windows-deps", "windows"),
            {"protected": True},
            {
                "required_status_checks": {
                    "checks": [
                        {"context": "linux"},
                        {"context": "windows-deps"},
                        {"context": "windows"},
                    ]
                }
            },
        )

        errors, warnings = controller_resource_audit.evaluateBranchProtection(report)

        self.assertEqual([], errors)
        self.assertEqual([], warnings)
        self.assertEqual((), report.missingRequiredChecks)

    def test_payload_includes_optional_branch_protection_report(self) -> None:
        git = controller_resource_audit.GitHealthReport(
            statusExitCode=0,
            statusStdout="",
            statusStderr="",
            head="abc123",
            originMain="abc123",
            gitCommonDir="/repo/.git",
            emptyLooseObjects=(),
            emptyRefs=(),
        )
        branch = controller_resource_audit.BranchProtectionReport(
            repo="owner/repo",
            branch="main",
            protected=False,
            requiredChecks=(),
            expectedChecks=("linux",),
            missingRequiredChecks=("linux",),
        )

        payload = controller_resource_audit.payload(
            Path("/repo"),
            git,
            [],
            [],
            [],
            branch,
            [],
            ["owner/repo:main: branch is not protected"],
        )

        self.assertEqual(False, payload["branchProtection"]["protected"])
        self.assertEqual(["linux"], payload["branchProtection"]["missingRequiredChecks"])


if __name__ == "__main__":
    unittest.main()
