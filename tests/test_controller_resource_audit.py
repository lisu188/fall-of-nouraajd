from __future__ import annotations

import subprocess
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

    def test_discover_run_trees_includes_workflow_optimizer_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_tree = root / "fon-workflow-optimizer-demo"
            run_tree.mkdir()
            (run_tree / "artifact.txt").write_text("x" * 19, encoding="utf-8")

            records = controller_resource_audit.discoverRunTrees(
                [root],
                controller_resource_audit.DEFAULT_RUN_TREE_PATTERNS,
            )

        self.assertEqual(1, len(records))
        self.assertTrue(records[0].path.endswith("fon-workflow-optimizer-demo"))
        self.assertEqual(19, records[0].sizeBytes)
        self.assertTrue(records[0].sizeMeasured)

    def test_discover_run_trees_marks_skipped_size_measurements(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_tree = root / "fon-workflow-optimizer-demo"
            run_tree.mkdir()
            (run_tree / "artifact.txt").write_text("x" * 19, encoding="utf-8")

            records = controller_resource_audit.discoverRunTrees(
                [root],
                controller_resource_audit.DEFAULT_RUN_TREE_PATTERNS,
                includeSizes=False,
            )

        self.assertEqual(1, len(records))
        self.assertEqual(0, records[0].sizeBytes)
        self.assertFalse(records[0].sizeMeasured)

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

    def test_evaluate_git_health_warns_when_head_is_behind_origin_main(self) -> None:
        report = controller_resource_audit.GitHealthReport(
            statusExitCode=0,
            statusStdout="## main...origin/main [behind 1]",
            statusStderr="",
            head="old",
            originMain="new",
            gitCommonDir="/repo/.git",
            emptyLooseObjects=(),
            emptyRefs=(),
            headAheadOriginMainCount=0,
            headBehindOriginMainCount=1,
            headBehindOriginMain=True,
        )

        errors, warnings = controller_resource_audit.evaluateGitHealth(report)

        self.assertEqual([], errors)
        self.assertTrue(
            any("HEAD is missing refs/remotes/origin/main commit(s) by 1" in warning for warning in warnings),
            warnings,
        )

    def test_evaluate_git_health_falls_back_to_status_behind_marker(self) -> None:
        report = controller_resource_audit.GitHealthReport(
            statusExitCode=0,
            statusStdout="## main...origin/main [behind 2]",
            statusStderr="",
            head="old",
            originMain="new",
            gitCommonDir="/repo/.git",
            emptyLooseObjects=(),
            emptyRefs=(),
            headBehindOriginMain=None,
        )

        errors, warnings = controller_resource_audit.evaluateGitHealth(report)

        self.assertEqual([], errors)
        self.assertTrue(
            any("HEAD is missing refs/remotes/origin/main commit(s)" in warning for warning in warnings),
            warnings,
        )

    def test_evaluate_git_health_fallback_handles_diverged_status(self) -> None:
        report = controller_resource_audit.GitHealthReport(
            statusExitCode=0,
            statusStdout="## feature...origin/main [ahead 1, behind 2]",
            statusStderr="",
            head="feature",
            originMain="main",
            gitCommonDir="/repo/.git",
            emptyLooseObjects=(),
            emptyRefs=(),
            headBehindOriginMain=None,
        )

        errors, warnings = controller_resource_audit.evaluateGitHealth(report)

        self.assertEqual([], errors)
        self.assertTrue(
            any("HEAD is missing refs/remotes/origin/main commit(s)" in warning for warning in warnings),
            warnings,
        )

    def test_evaluate_git_health_does_not_warn_for_ahead_only_head(self) -> None:
        report = controller_resource_audit.GitHealthReport(
            statusExitCode=0,
            statusStdout="## feature...origin/main [ahead 1]",
            statusStderr="",
            head="feature",
            originMain="main",
            gitCommonDir="/repo/.git",
            emptyLooseObjects=(),
            emptyRefs=(),
            headAheadOriginMainCount=1,
            headBehindOriginMainCount=0,
            headBehindOriginMain=False,
        )

        errors, warnings = controller_resource_audit.evaluateGitHealth(report)

        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_evaluate_git_health_warns_for_diverged_head_missing_origin_commits(self) -> None:
        report = controller_resource_audit.GitHealthReport(
            statusExitCode=0,
            statusStdout="## feature...origin/main [ahead 1, behind 2]",
            statusStderr="",
            head="feature",
            originMain="main",
            gitCommonDir="/repo/.git",
            emptyLooseObjects=(),
            emptyRefs=(),
            headAheadOriginMainCount=1,
            headBehindOriginMainCount=2,
            headBehindOriginMain=True,
        )

        errors, warnings = controller_resource_audit.evaluateGitHealth(report)

        self.assertEqual([], errors)
        self.assertTrue(any("by 2 commit(s)" in warning for warning in warnings), warnings)

    def test_run_git_health_detects_head_behind_origin_main(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, stdout=subprocess.PIPE)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
            (repo / "file.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, stdout=subprocess.PIPE)
            base_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            ).stdout.strip()
            (repo / "file.txt").write_text("base\nnext\n", encoding="utf-8")
            subprocess.run(["git", "commit", "-am", "next"], cwd=repo, check=True, stdout=subprocess.PIPE)
            subprocess.run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], cwd=repo, check=True)
            subprocess.run(
                ["git", "checkout", "--detach", base_sha],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            report = controller_resource_audit.runGitHealth(repo)

        self.assertTrue(report.headBehindOriginMain)
        self.assertEqual(0, report.headAheadOriginMainCount)
        self.assertEqual(1, report.headBehindOriginMainCount)

    def test_run_git_health_warns_when_local_origin_main_is_stale_without_fetching(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            origin = root / "origin.git"
            seed = root / "seed"
            local = root / "local"
            subprocess.run(
                ["git", "init", "--bare", "-b", "main", str(origin)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                ["git", "init", "-b", "main", str(seed)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=seed, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=seed, check=True)
            (seed / "file.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "file.txt"], cwd=seed, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=seed, check=True, stdout=subprocess.PIPE)
            subprocess.run(["git", "remote", "add", "origin", str(origin)], cwd=seed, check=True)
            subprocess.run(
                ["git", "push", "-u", "origin", "main"],
                cwd=seed,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            base_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=seed,
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            ).stdout.strip()

            subprocess.run(
                ["git", "clone", str(origin), str(local)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            (seed / "file.txt").write_text("base\nnext\n", encoding="utf-8")
            subprocess.run(["git", "commit", "-am", "next"], cwd=seed, check=True, stdout=subprocess.PIPE)
            subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=seed,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            next_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=seed,
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            ).stdout.strip()
            local_origin_before = subprocess.run(
                ["git", "rev-parse", "refs/remotes/origin/main"],
                cwd=local,
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            ).stdout.strip()

            report = controller_resource_audit.runGitHealth(local)
            errors, warnings = controller_resource_audit.evaluateGitHealth(report)
            local_origin_after = subprocess.run(
                ["git", "rev-parse", "refs/remotes/origin/main"],
                cwd=local,
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            ).stdout.strip()

        self.assertEqual(base_sha, local_origin_before)
        self.assertEqual(base_sha, report.head)
        self.assertEqual(base_sha, report.originMain)
        self.assertEqual(next_sha, report.liveOriginMain)
        self.assertFalse(report.originMainMatchesLive)
        self.assertEqual(base_sha, local_origin_after)
        self.assertEqual([], errors)
        self.assertTrue(
            any("refs/remotes/origin/main differs from live origin/main" in warning for warning in warnings),
            warnings,
        )

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

    def test_merge_policy_report_flags_disabled_auto_merge(self) -> None:
        report = controller_resource_audit.mergePolicyReportFromPayload(
            "owner/repo",
            {"allow_auto_merge": False, "delete_branch_on_merge": True},
        )

        errors, warnings = controller_resource_audit.evaluateMergePolicy(report)

        self.assertEqual([], errors)
        self.assertFalse(report.allowAutoMerge)
        self.assertTrue(report.deleteBranchOnMerge)
        self.assertTrue(any("repository auto-merge is disabled" in warning for warning in warnings), warnings)

    def test_merge_policy_report_warns_when_auto_merge_field_is_missing(self) -> None:
        report = controller_resource_audit.mergePolicyReportFromPayload("owner/repo", {})

        errors, warnings = controller_resource_audit.evaluateMergePolicy(report)

        self.assertEqual([], errors)
        self.assertIsNone(report.allowAutoMerge)
        self.assertTrue(any("auto-merge setting is missing" in warning for warning in warnings), warnings)

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
            headAheadOriginMainCount=0,
            headBehindOriginMainCount=0,
            headBehindOriginMain=False,
            liveOriginMain="abc123",
            originMainMatchesLive=True,
        )
        branch = controller_resource_audit.BranchProtectionReport(
            repo="owner/repo",
            branch="main",
            protected=False,
            requiredChecks=(),
            expectedChecks=("linux",),
            missingRequiredChecks=("linux",),
        )
        merge_policy = controller_resource_audit.MergePolicyReport(
            repo="owner/repo",
            allowAutoMerge=False,
            deleteBranchOnMerge=True,
        )

        payload = controller_resource_audit.payload(
            Path("/repo"),
            git,
            [],
            [],
            [],
            True,
            branch,
            [],
            ["owner/repo:main: branch is not protected"],
            mergePolicy=merge_policy,
        )

        self.assertEqual(False, payload["branchProtection"]["protected"])
        self.assertEqual(["linux"], payload["branchProtection"]["missingRequiredChecks"])
        self.assertEqual(False, payload["mergePolicy"]["allowAutoMerge"])
        self.assertEqual(True, payload["mergePolicy"]["deleteBranchOnMerge"])
        self.assertEqual(False, payload["git"]["headBehindOriginMain"])
        self.assertEqual(0, payload["git"]["headAheadOriginMainCount"])
        self.assertEqual(0, payload["git"]["headBehindOriginMainCount"])
        self.assertEqual("abc123", payload["git"]["liveOriginMain"])
        self.assertTrue(payload["git"]["originMainMatchesLive"])

    def test_payload_marks_unmeasured_run_tree_sizes(self) -> None:
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

        payload = controller_resource_audit.payload(
            Path("/repo"),
            git,
            [],
            [],
            [controller_resource_audit.RunTreeRecord("/tmp/fon-workflow-optimizer-demo", 0, sizeMeasured=False)],
            False,
            None,
            [],
            [],
        )

        self.assertEqual(0, payload["runTrees"]["totalBytes"])
        self.assertFalse(payload["runTrees"]["sizesMeasured"])
        self.assertFalse(payload["runTrees"]["records"][0]["sizeMeasured"])
        self.assertEqual("0.0 MiB", payload["runTrees"]["records"][0]["sizeHuman"])

    def test_payload_preserves_skipped_size_mode_with_no_run_tree_records(self) -> None:
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

        payload = controller_resource_audit.payload(
            Path("/repo"),
            git,
            [],
            [],
            [],
            False,
            None,
            [],
            [],
        )

        self.assertEqual(0, payload["runTrees"]["total"])
        self.assertEqual(0, payload["runTrees"]["totalBytes"])
        self.assertFalse(payload["runTrees"]["sizesMeasured"])


if __name__ == "__main__":
    unittest.main()
