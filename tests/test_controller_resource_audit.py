from __future__ import annotations

import contextlib
import io
import json
import socket
import subprocess
import tempfile
import unittest
import unittest.mock
from datetime import timedelta
from pathlib import Path

from scripts import controller_resource_audit, issue_queue, resource_broker


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

    def test_run_gh_api_json_reports_missing_cli_as_runtime_error(self) -> None:
        def raise_missing_gh(*_args: object, **_kwargs: object) -> None:
            raise FileNotFoundError(2, "No such file or directory", "gh")

        with unittest.mock.patch.object(controller_resource_audit.subprocess, "run", side_effect=raise_missing_gh):
            with self.assertRaises(RuntimeError) as caught:
                controller_resource_audit.runGhApiJson("repos/owner/repo")

        self.assertIn("gh CLI not found on PATH", str(caught.exception))

    def test_audit_branch_protection_degrades_when_gh_cli_is_missing(self) -> None:
        def raise_missing_gh(*_args: object, **_kwargs: object) -> None:
            raise FileNotFoundError(2, "No such file or directory", "gh")

        with unittest.mock.patch.object(controller_resource_audit.subprocess, "run", side_effect=raise_missing_gh):
            report = controller_resource_audit.auditBranchProtection("owner/repo", "main", ("linux",))

        self.assertIsNone(report.protected)
        self.assertIn("gh CLI not found on PATH", report.error or "")
        errors, warnings = controller_resource_audit.evaluateBranchProtection(report)
        self.assertEqual([], errors)
        self.assertTrue(
            any("branch protection could not be inspected" in warning for warning in warnings),
            warnings,
        )

    def test_audit_merge_policy_degrades_when_gh_cli_is_missing(self) -> None:
        def raise_missing_gh(*_args: object, **_kwargs: object) -> None:
            raise FileNotFoundError(2, "No such file or directory", "gh")

        with unittest.mock.patch.object(controller_resource_audit.subprocess, "run", side_effect=raise_missing_gh):
            report = controller_resource_audit.auditMergePolicy("owner/repo")

        self.assertIsNone(report.allowAutoMerge)
        self.assertIn("gh CLI not found on PATH", report.error or "")
        errors, warnings = controller_resource_audit.evaluateMergePolicy(report)
        self.assertEqual([], errors)
        self.assertTrue(
            any("repository merge policy could not be inspected" in warning for warning in warnings),
            warnings,
        )


class ResourceBrokerProbeTest(unittest.TestCase):
    def test_probe_memory_reports_available_from_mocked_meminfo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            meminfo = Path(temp_dir) / "meminfo"
            meminfo.write_text("MemTotal: 16000000 kB\nMemAvailable: 8000000 kB\n", encoding="utf-8")

            probe = resource_broker.probeMemory(min_available_mib=2048.0, meminfo_path=meminfo)

        self.assertEqual(resource_broker.STATUS_AVAILABLE, probe["status"])
        self.assertEqual("memory", probe["resource"])
        self.assertTrue(probe["advisory"])
        self.assertAlmostEqual(8000000 / 1024.0, probe["availableMib"], places=1)

    def test_probe_memory_reports_unavailable_below_advisory_floor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            meminfo = Path(temp_dir) / "meminfo"
            meminfo.write_text("MemTotal: 16000000 kB\nMemAvailable: 100000 kB\n", encoding="utf-8")

            probe = resource_broker.probeMemory(min_available_mib=2048.0, meminfo_path=meminfo)

        self.assertEqual(resource_broker.STATUS_UNAVAILABLE, probe["status"])

    def test_probe_memory_reports_unsupported_platform_without_raising(self) -> None:
        probe = resource_broker.probeMemory(meminfo_path=Path("/nonexistent/meminfo"))

        self.assertEqual(resource_broker.STATUS_UNSUPPORTED, probe["status"])

    def test_probe_memory_reports_unknown_for_malformed_meminfo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            meminfo = Path(temp_dir) / "meminfo"
            meminfo.write_text("garbage\n", encoding="utf-8")

            probe = resource_broker.probeMemory(meminfo_path=meminfo)

        self.assertEqual(resource_broker.STATUS_UNKNOWN, probe["status"])

    def test_probe_heavy_jobs_detects_build_processes_from_mocked_proc(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proc_root = Path(temp_dir)
            build_process = proc_root / "4242"
            build_process.mkdir()
            (build_process / "cmdline").write_bytes(b"cmake\0--build\0cmake-build-release\0")
            idle_process = proc_root / "4243"
            idle_process.mkdir()
            (idle_process / "cmdline").write_bytes(b"bash\0")

            probe = resource_broker.probeHeavyJobs(proc_root=proc_root)

        self.assertEqual(resource_broker.STATUS_UNAVAILABLE, probe["status"])
        self.assertEqual([4242], [job["pid"] for job in probe["runningJobs"]])

    def test_probe_heavy_jobs_reports_available_when_no_heavy_process_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proc_root = Path(temp_dir)
            idle_process = proc_root / "77"
            idle_process.mkdir()
            (idle_process / "cmdline").write_bytes(b"bash\0")

            probe = resource_broker.probeHeavyJobs(proc_root=proc_root)

        self.assertEqual(resource_broker.STATUS_AVAILABLE, probe["status"])
        self.assertEqual([], probe["runningJobs"])

    def test_probe_heavy_jobs_reports_unsupported_platform_without_raising(self) -> None:
        probe = resource_broker.probeHeavyJobs(proc_root=Path("/nonexistent/proc"))

        self.assertEqual(resource_broker.STATUS_UNSUPPORTED, probe["status"])

    def test_probe_xvfb_displays_reports_used_displays_from_sockets_and_locks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_dir = Path(temp_dir)
            socket_dir = lock_dir / ".X11-unix"
            socket_dir.mkdir()
            (socket_dir / "X0").touch()
            (lock_dir / ".X99-lock").touch()

            pool = resource_broker.probeXvfbDisplays(x11_socket_dir=socket_dir, lock_dir=lock_dir)
            busy = resource_broker.probeXvfbDisplays(display=":99", x11_socket_dir=socket_dir, lock_dir=lock_dir)
            free = resource_broker.probeXvfbDisplays(display="100", x11_socket_dir=socket_dir, lock_dir=lock_dir)

        self.assertEqual([":0", ":99"], pool["usedDisplays"])
        self.assertEqual(resource_broker.STATUS_UNAVAILABLE, busy["status"])
        self.assertEqual(resource_broker.STATUS_AVAILABLE, free["status"])
        self.assertEqual(":100", free["key"])

    def test_probe_tcp_port_reports_bound_and_free_ports(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            bound_port = listener.getsockname()[1]

            bound_probe = resource_broker.probeTcpPort(bound_port)

        free_probe = resource_broker.probeTcpPort(bound_port)

        self.assertEqual(resource_broker.STATUS_UNAVAILABLE, bound_probe["status"])
        self.assertEqual(resource_broker.STATUS_AVAILABLE, free_probe["status"])
        self.assertEqual(str(bound_port), bound_probe["key"])

    def test_probe_build_dir_reports_reservation_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            (repo_root / "cmake-build-release").mkdir()
            holders = [
                {"resource": "build-dir", "key": "cmake-build-release", "owner": "controller/ctrl-a/sub-1"},
            ]

            probes = resource_broker.probeBuildDirOwnership(repo_root, active_reservations=holders)

        by_key = {probe["key"]: probe for probe in probes}
        self.assertEqual(resource_broker.STATUS_UNAVAILABLE, by_key["cmake-build-release"]["status"])
        self.assertEqual(["controller/ctrl-a/sub-1"], by_key["cmake-build-release"]["reservedBy"])
        self.assertTrue(by_key["cmake-build-release"]["exists"])
        self.assertEqual(resource_broker.STATUS_AVAILABLE, by_key["cmake-build-debug"]["status"])
        self.assertFalse(by_key["cmake-build-debug"]["exists"])

    def test_probe_mcp_server_reports_reserved_slot(self) -> None:
        holders = [{"resource": "mcp-server", "key": "default", "owner": "controller/ctrl-a/sub-1"}]

        probe = resource_broker.probeMcpServer(active_reservations=holders)

        self.assertEqual(resource_broker.STATUS_UNAVAILABLE, probe["status"])
        self.assertEqual(["controller/ctrl-a/sub-1"], probe["reservedBy"])

    def test_guarded_probe_reports_unknown_instead_of_raising(self) -> None:
        def broken_probe() -> dict[str, object]:
            raise OSError("probe backend exploded")

        probe = resource_broker.guardedProbe("memory", broken_probe)

        self.assertEqual(resource_broker.STATUS_UNKNOWN, probe["status"])
        self.assertIn("probe backend exploded", probe["detail"])

    def test_observe_resources_never_raises_when_a_probe_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = Path(temp_dir) / "reservations.json"
            with unittest.mock.patch.object(resource_broker, "probeMemory", side_effect=RuntimeError("mocked failure")):
                observed = resource_broker.observeResources(Path(temp_dir), store_path=store)

        memory_probes = [probe for probe in observed["probes"] if probe["resource"] == "memory"]
        self.assertEqual(resource_broker.STATUS_UNKNOWN, memory_probes[0]["status"])
        self.assertIn("mocked failure", memory_probes[0]["detail"])
        self.assertEqual(0, observed["reservations"]["total"])


class ResourceBrokerReservationTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)
        self.store = Path(self._temp_dir.name) / "resource_reservations.json"
        self.now = issue_queue.utcNow()

    def _request(self, resource: str, key: str, owner: str = "controller/ctrl-a/sub-1", **overrides: object) -> dict:
        request = resource_broker.buildReservationRequest(
            resource=resource,
            key=key,
            controller_id="ctrl-a",
            owner=owner,
            claim_id="claim-1",
            purpose="test",
        )
        request.update(overrides)
        return request

    def test_exclusive_reservations_conflict_across_owners(self) -> None:
        resource_broker.acquireReservations(self.store, [self._request("tcp-port", "8765")], now=self.now)

        with self.assertRaises(resource_broker.ResourceConflict) as caught:
            resource_broker.acquireReservations(
                self.store,
                [self._request("tcp-port", "8765", owner="controller/ctrl-b/sub-2")],
                now=self.now,
            )

        blocked_by = caught.exception.conflicts[0]["blockedBy"][0]
        self.assertEqual("controller/ctrl-a/sub-1", blocked_by["owner"])

    def test_independent_reservations_stay_concurrent(self) -> None:
        resource_broker.acquireReservations(self.store, [self._request("tcp-port", "8765")], now=self.now)

        result = resource_broker.acquireReservations(
            self.store,
            [
                self._request("tcp-port", "8766", owner="controller/ctrl-b/sub-2"),
                self._request("xvfb-display", ":99", owner="controller/ctrl-b/sub-2"),
                self._request("build-dir", "cmake-build-release", owner="controller/ctrl-b/sub-2"),
            ],
            now=self.now,
        )

        self.assertEqual(3, len(result["acquired"]))
        listing = resource_broker.listReservations(self.store, now=self.now)
        self.assertEqual(4, listing["count"])

    def test_shared_memory_reservations_are_advisory_unless_exclusive(self) -> None:
        resource_broker.acquireReservations(self.store, [self._request("memory", "default")], now=self.now)
        resource_broker.acquireReservations(
            self.store,
            [self._request("memory", "default", owner="controller/ctrl-b/sub-2")],
            now=self.now,
        )

        with self.assertRaises(resource_broker.ResourceConflict):
            resource_broker.acquireReservations(
                self.store,
                [self._request("memory", "default", owner="controller/ctrl-c/sub-3", exclusive=True)],
                now=self.now,
            )

    def test_failed_batch_is_atomic_and_leaves_store_unchanged(self) -> None:
        resource_broker.acquireReservations(self.store, [self._request("tcp-port", "8765")], now=self.now)
        before = self.store.read_bytes()

        with self.assertRaises(resource_broker.ResourceConflict):
            resource_broker.acquireReservations(
                self.store,
                [
                    self._request("tcp-port", "9000", owner="controller/ctrl-b/sub-2"),
                    self._request("tcp-port", "8765", owner="controller/ctrl-b/sub-2"),
                ],
                now=self.now,
            )

        self.assertEqual(before, self.store.read_bytes())

    def test_failed_batch_does_not_create_a_missing_store(self) -> None:
        with self.assertRaises(resource_broker.ResourceConflict):
            resource_broker.acquireReservations(
                self.store,
                [
                    self._request("xvfb-display", ":99"),
                    self._request("xvfb-display", ":99", owner="controller/ctrl-b/sub-2"),
                ],
                now=self.now,
            )

        self.assertFalse(self.store.exists())

    def test_within_batch_conflicts_are_rejected(self) -> None:
        with self.assertRaises(resource_broker.ResourceConflict) as caught:
            resource_broker.acquireReservations(
                self.store,
                [self._request("build-dir", "cmake-build-release"), self._request("build-dir", "cmake-build-release")],
                now=self.now,
            )

        blocked_by = caught.exception.conflicts[0]["blockedBy"][0]
        self.assertTrue(blocked_by["withinBatch"])

    def test_expired_reservations_do_not_block_and_are_reported_not_purged(self) -> None:
        resource_broker.acquireReservations(
            self.store,
            [self._request("tcp-port", "8765", durationMinutes=1)],
            now=self.now,
        )
        later = self.now + timedelta(hours=3)

        result = resource_broker.acquireReservations(
            self.store,
            [self._request("tcp-port", "8765", owner="controller/ctrl-b/sub-2")],
            now=later,
        )

        self.assertEqual(1, len(result["acquired"]))
        self.assertEqual(1, len(result["expiredActive"]))
        self.assertTrue(result["expiredActive"][0]["expired"])
        listing = resource_broker.listReservations(self.store, now=later)
        self.assertEqual(2, listing["count"], "expired records must be reported, never deleted")

    def test_recover_marks_only_expired_reservations_and_deletes_nothing(self) -> None:
        acquired = resource_broker.acquireReservations(
            self.store,
            [self._request("build-dir", "cmake-build-release", durationMinutes=1)],
            now=self.now,
        )
        reservation_id = acquired["acquired"][0]["reservationId"]

        with self.assertRaises(resource_broker.ResourceBrokerError):
            resource_broker.recoverReservations(self.store, [reservation_id], reason="stale", now=self.now)

        later = self.now + timedelta(hours=3)
        recovered = resource_broker.recoverReservations(self.store, [reservation_id], reason="stale", now=later)

        self.assertEqual("RECOVERED", recovered["recovered"][0]["state"])
        self.assertEqual("stale", recovered["recovered"][0]["recoveryReason"])
        listing = resource_broker.listReservations(self.store, now=later)
        self.assertEqual(1, listing["count"], "recovery must keep the record")

    def test_renew_extends_expiry_and_checks_identity(self) -> None:
        acquired = resource_broker.acquireReservations(self.store, [self._request("tcp-port", "8765")], now=self.now)
        reservation_id = acquired["acquired"][0]["reservationId"]

        with self.assertRaises(resource_broker.ResourceBrokerError):
            resource_broker.renewReservations(
                self.store, [reservation_id], owner="controller/ctrl-b/sub-2", now=self.now
            )

        renewed = resource_broker.renewReservations(
            self.store,
            [reservation_id],
            owner="controller/ctrl-a/sub-1",
            extend_minutes=240,
            now=self.now,
        )

        expected_expiry = issue_queue.formatUtc(self.now + timedelta(minutes=240))
        self.assertEqual(expected_expiry, renewed["renewed"][0]["expiresAtUtc"])

    def test_release_marks_reservation_released(self) -> None:
        acquired = resource_broker.acquireReservations(
            self.store, [self._request("mcp-server", "default")], now=self.now
        )
        reservation_id = acquired["acquired"][0]["reservationId"]

        released = resource_broker.releaseReservations(
            self.store, [reservation_id], owner="controller/ctrl-a/sub-1", now=self.now
        )

        self.assertEqual("RELEASED", released["released"][0]["state"])
        follow_up = resource_broker.acquireReservations(
            self.store,
            [self._request("mcp-server", "default", owner="controller/ctrl-b/sub-2")],
            now=self.now,
        )
        self.assertEqual(1, len(follow_up["acquired"]))

    def test_reservation_requests_validate_type_key_and_identity(self) -> None:
        with self.assertRaises(resource_broker.ResourceBrokerError):
            resource_broker.acquireReservations(self.store, [self._request("warp-drive", "x")], now=self.now)
        with self.assertRaises(resource_broker.ResourceBrokerError):
            resource_broker.acquireReservations(self.store, [self._request("tcp-port", "not-a-port")], now=self.now)
        with self.assertRaises(resource_broker.ResourceBrokerError):
            resource_broker.acquireReservations(self.store, [self._request("tcp-port", "8765", owner="")], now=self.now)
        self.assertFalse(self.store.exists())


class ControllerResourceAuditBrokerIntegrationTest(unittest.TestCase):
    def _git_report(self) -> controller_resource_audit.GitHealthReport:
        return controller_resource_audit.GitHealthReport(
            statusExitCode=0,
            statusStdout="",
            statusStderr="",
            head="abc123",
            originMain="abc123",
            gitCommonDir="/repo/.git",
            emptyLooseObjects=(),
            emptyRefs=(),
        )

    def test_payload_keeps_existing_fields_and_adds_resources_additively(self) -> None:
        resources = {
            "probes": [{"resource": "memory", "key": None, "status": "available", "detail": "ok"}],
            "reservations": {"store": "/tmp/store.json", "total": 0, "active": 0, "expiredActive": 0},
        }

        with_resources = controller_resource_audit.payload(
            Path("/repo"), self._git_report(), [], [], [], True, None, [], [], resources=resources
        )
        without_resources = controller_resource_audit.payload(
            Path("/repo"), self._git_report(), [], [], [], True, None, [], []
        )

        for existing_key in (
            "repoRoot",
            "git",
            "disk",
            "worktrees",
            "runTrees",
            "branchProtection",
            "mergePolicy",
            "errors",
            "warnings",
        ):
            self.assertIn(existing_key, with_resources)
            self.assertIn(existing_key, without_resources)
        self.assertEqual(resources, with_resources["resources"])
        self.assertIsNone(without_resources["resources"])

    def test_evaluate_resource_observation_warns_about_expired_reservations(self) -> None:
        errors, warnings = controller_resource_audit.evaluateResourceObservation(
            {"probes": [], "reservations": {"total": 3, "active": 1, "expiredActive": 2}}
        )

        self.assertEqual([], errors)
        self.assertTrue(any("2 expired ACTIVE resource reservation(s)" in warning for warning in warnings), warnings)

    def test_evaluate_resource_observation_is_silent_without_findings(self) -> None:
        errors, warnings = controller_resource_audit.evaluateResourceObservation(
            {"probes": [], "reservations": {"total": 1, "active": 1, "expiredActive": 0}}
        )

        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_main_dispatches_broker_subcommands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = str(Path(temp_dir) / "reservations.json")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = controller_resource_audit.main(["list", "--store", store])

        self.assertEqual(0, exit_code)
        listing = json.loads(stdout.getvalue())
        self.assertEqual(0, listing["count"])


if __name__ == "__main__":
    unittest.main()
