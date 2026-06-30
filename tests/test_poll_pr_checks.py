from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import ci_change_classifier, poll_pr_checks

REPO_ROOT = Path(__file__).resolve().parents[1]


class PollPrChecksTest(unittest.TestCase):
    def runPayload(self, jobs: list[dict[str, object]], *, status: str = "completed") -> dict[str, object]:
        return {
            "headSha": "abc123",
            "url": "https://github.com/example/repo/actions/runs/1",
            "workflowName": "build",
            "status": status,
            "conclusion": "success",
            "jobs": jobs,
        }

    def jobPayload(
        self,
        *,
        name: str = "linux",
        status: str = "completed",
        conclusion: str = "success",
        steps: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        return {
            "name": name,
            "status": status,
            "conclusion": conclusion,
            "url": f"https://github.com/example/repo/actions/jobs/{name}",
            "steps": steps or [],
        }

    def test_select_run_for_head_ignores_stale_runs(self) -> None:
        selected = poll_pr_checks.selectRunForHead(
            [
                {"databaseId": 1, "headSha": "old"},
                {"databaseId": 2, "headSha": "abc123"},
            ],
            "abc123",
        )

        self.assertEqual(2, selected["databaseId"])

    def test_evaluate_run_passes_completed_linux_success(self) -> None:
        evaluation = poll_pr_checks.evaluateRun(
            self.runPayload([self.jobPayload()]),
            ["linux"],
            [],
        )

        self.assertTrue(evaluation.succeeded)
        self.assertEqual("success", evaluation.state)
        self.assertEqual("linux", evaluation.jobs[0].name)

    def test_changed_files_require_coverage_for_workflow_paths(self) -> None:
        self.assertTrue(poll_pr_checks.changedFilesRequireCoverage(["src/core/CGame.cpp"]))
        self.assertTrue(poll_pr_checks.changedFilesRequireCoverage(["src/gui/panel/CListView.cpp"]))
        self.assertTrue(poll_pr_checks.changedFilesRequireCoverage(["src/handler/CFightHandler.cpp"]))
        self.assertTrue(poll_pr_checks.changedFilesRequireCoverage(["tests/unit/test_core.cpp"]))
        self.assertFalse(poll_pr_checks.changedFilesRequireCoverage(["docs/testing.md", "scripts/poll_pr_checks.py"]))

    def test_default_jobs_follow_changed_path_validation_class(self) -> None:
        self.assertEqual(("linux",), poll_pr_checks.defaultJobsForChangedFiles(["docs/testing.md"]))
        self.assertEqual(
            ("linux",),
            poll_pr_checks.defaultJobsForChangedFiles(
                ["planning/workflow_observations/resolutions/example-observation.json"]
            ),
        )
        self.assertEqual(
            ("linux", "windows-deps", "windows"),
            poll_pr_checks.defaultJobsForChangedFiles(["src/handler/CFightHandler.cpp"]),
        )

    def test_coverage_path_patterns_match_workflow_detector(self) -> None:
        workflow = (REPO_ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")

        self.assertEqual(ci_change_classifier.COVERAGE_PATH_PATTERNS, poll_pr_checks.COVERAGE_PATH_PATTERNS)
        self.assertIn("scripts/ci_change_classifier.py", workflow)

    def test_evaluate_run_treats_missing_run_as_pending(self) -> None:
        evaluation = poll_pr_checks.evaluateRun(None, ["linux"], [])

        self.assertEqual("pending", evaluation.state)
        self.assertEqual(("linux",), evaluation.missingJobs)

    def test_evaluate_run_treats_missing_linux_job_as_pending(self) -> None:
        evaluation = poll_pr_checks.evaluateRun(
            self.runPayload([self.jobPayload(name="windows-deps")]),
            ["linux"],
            [],
        )

        self.assertEqual("pending", evaluation.state)
        self.assertEqual(("linux",), evaluation.missingJobs)

    def test_evaluate_run_reports_in_progress_linux(self) -> None:
        evaluation = poll_pr_checks.evaluateRun(
            self.runPayload([self.jobPayload(status="in_progress", conclusion="")]),
            ["linux"],
            [],
        )

        self.assertEqual("pending", evaluation.state)
        self.assertIn("linux=IN_PROGRESS", evaluation.message)

    def test_evaluate_run_fails_completed_non_success(self) -> None:
        evaluation = poll_pr_checks.evaluateRun(
            self.runPayload([self.jobPayload(conclusion="failure")]),
            ["linux"],
            [],
        )

        self.assertTrue(evaluation.failed)
        self.assertIn("linux=FAILURE", evaluation.message)

    def test_evaluate_run_requires_all_requested_jobs(self) -> None:
        evaluation = poll_pr_checks.evaluateRun(
            self.runPayload(
                [
                    self.jobPayload(name="linux"),
                    self.jobPayload(name="windows-deps", status="in_progress", conclusion=""),
                ]
            ),
            ["linux", "windows-deps"],
            [],
        )

        self.assertEqual("pending", evaluation.state)
        self.assertIn("windows-deps=IN_PROGRESS", evaluation.message)

    def test_evaluate_run_requires_named_step_success(self) -> None:
        evaluation = poll_pr_checks.evaluateRun(
            self.runPayload(
                [
                    self.jobPayload(
                        steps=[
                            {
                                "name": "coverage",
                                "status": "completed",
                                "conclusion": "success",
                            }
                        ]
                    )
                ]
            ),
            ["linux"],
            ["coverage"],
        )

        self.assertTrue(evaluation.succeeded)

    def test_evaluate_run_accepts_required_step_from_non_selected_job(self) -> None:
        evaluation = poll_pr_checks.evaluateRun(
            self.runPayload(
                [
                    self.jobPayload(name="linux"),
                    self.jobPayload(
                        name="linux-coverage",
                        steps=[
                            {
                                "name": "coverage",
                                "status": "completed",
                                "conclusion": "success",
                            }
                        ],
                    ),
                ]
            ),
            ["linux"],
            ["coverage"],
        )

        self.assertTrue(evaluation.succeeded)
        self.assertEqual(("linux", "linux-coverage"), tuple(job.name for job in evaluation.jobs))

    def test_evaluate_run_fails_required_step_from_non_selected_job(self) -> None:
        evaluation = poll_pr_checks.evaluateRun(
            self.runPayload(
                [
                    self.jobPayload(name="linux"),
                    self.jobPayload(
                        name="linux-coverage",
                        steps=[
                            {
                                "name": "coverage",
                                "status": "completed",
                                "conclusion": "failure",
                            }
                        ],
                    ),
                ]
            ),
            ["linux"],
            ["coverage"],
        )

        self.assertTrue(evaluation.failed)
        self.assertIn("linux-coverage/coverage=FAILURE", evaluation.message)

    def test_evaluate_run_waits_for_missing_required_step_while_workflow_runs(self) -> None:
        evaluation = poll_pr_checks.evaluateRun(
            self.runPayload([self.jobPayload(name="linux")], status="in_progress"),
            ["linux"],
            ["coverage"],
        )

        self.assertEqual("pending", evaluation.state)
        self.assertEqual(("coverage",), evaluation.missingSteps)
        self.assertIn("missing required step(s) so far", evaluation.message)

    def test_evaluate_run_fails_skipped_required_step(self) -> None:
        evaluation = poll_pr_checks.evaluateRun(
            self.runPayload(
                [
                    self.jobPayload(
                        steps=[
                            {
                                "name": "coverage",
                                "status": "completed",
                                "conclusion": "skipped",
                            }
                        ]
                    )
                ]
            ),
            ["linux"],
            ["coverage"],
        )

        self.assertTrue(evaluation.failed)
        self.assertIn("linux/coverage=SKIPPED", evaluation.message)

    def test_evaluate_run_fails_required_step_job_failure(self) -> None:
        evaluation = poll_pr_checks.evaluateRun(
            self.runPayload(
                [
                    self.jobPayload(name="linux"),
                    self.jobPayload(
                        name="linux-coverage",
                        conclusion="failure",
                        steps=[
                            {
                                "name": "coverage",
                                "status": "completed",
                                "conclusion": "success",
                            }
                        ],
                    ),
                ]
            ),
            ["linux"],
            ["coverage"],
        )

        self.assertTrue(evaluation.failed)
        self.assertIn("linux-coverage=FAILURE", evaluation.message)

    def test_evaluate_run_fails_missing_required_step_after_job_success(self) -> None:
        evaluation = poll_pr_checks.evaluateRun(
            self.runPayload([self.jobPayload()]),
            ["linux"],
            ["coverage"],
        )

        self.assertTrue(evaluation.failed)
        self.assertEqual(("coverage",), evaluation.missingSteps)

    def test_evaluate_pr_state_passes_already_merged_pr(self) -> None:
        evaluation = poll_pr_checks.evaluatePrState(
            {
                "state": "MERGED",
                "mergedAt": "2026-06-19T09:19:25Z",
                "mergeCommit": {"oid": "abc123"},
            }
        )

        self.assertIsNotNone(evaluation)
        self.assertTrue(evaluation.succeeded)
        self.assertIn("already merged", evaluation.message)
        self.assertIn("abc123", evaluation.message)

    def test_evaluate_pr_state_fails_closed_unmerged_pr(self) -> None:
        evaluation = poll_pr_checks.evaluatePrState({"state": "CLOSED"})

        self.assertIsNotNone(evaluation)
        self.assertTrue(evaluation.failed)
        self.assertIn("closed without merge", evaluation.message)

    def test_poll_checks_stops_when_pr_is_already_merged(self) -> None:
        with (
            patch.object(
                poll_pr_checks,
                "runGhPrView",
                return_value={
                    "headRefOid": "abc123",
                    "url": "https://github.com/example/repo/pull/1",
                    "state": "MERGED",
                    "mergedAt": "2026-06-19T09:19:25Z",
                    "mergeCommit": {"oid": "abc123"},
                },
            ),
            patch.object(poll_pr_checks, "runGhRunList") as run_list,
        ):
            with redirect_stdout(io.StringIO()):
                evaluation = poll_pr_checks.pollChecks(
                    pr="1",
                    repo=None,
                    workflow="build.yml",
                    requiredJobs=["linux"],
                    requiredSteps=[],
                    intervalSeconds=1,
                    timeoutSeconds=1,
                )

        self.assertTrue(evaluation.succeeded)
        run_list.assert_not_called()

    def test_poll_checks_auto_requires_coverage_for_coverage_relevant_paths(self) -> None:
        open_pr = {
            "headRefOid": "abc123",
            "url": "https://github.com/example/repo/pull/1",
            "state": "OPEN",
        }
        completed_run = self.runPayload(
            [
                self.jobPayload(name="linux"),
                self.jobPayload(
                    name="linux-coverage",
                    steps=[{"name": "coverage", "status": "completed", "conclusion": "failure"}],
                ),
            ]
        )

        with (
            patch.object(poll_pr_checks, "runGhPrView", return_value=open_pr),
            patch.object(poll_pr_checks, "runGhPrFiles", return_value=("src/gui/panel/CListView.cpp",)),
            patch.object(poll_pr_checks, "runGhRunList", return_value=[{"databaseId": 1, "headSha": "abc123"}]),
            patch.object(poll_pr_checks, "runGhRunView", return_value=completed_run),
        ):
            with redirect_stdout(io.StringIO()):
                evaluation = poll_pr_checks.pollChecks(
                    pr="1",
                    repo=None,
                    workflow="build.yml",
                    requiredJobs=["linux"],
                    requiredSteps=[],
                    intervalSeconds=1,
                    timeoutSeconds=1,
                )

        self.assertTrue(evaluation.failed)
        self.assertIn("linux-coverage/coverage=FAILURE", evaluation.message)

    def test_poll_checks_auto_requires_windows_for_native_paths(self) -> None:
        open_pr = {
            "headRefOid": "abc123",
            "url": "https://github.com/example/repo/pull/1",
            "state": "OPEN",
        }
        completed_run = self.runPayload(
            [
                self.jobPayload(name="linux"),
                self.jobPayload(
                    name="linux-coverage", steps=[{"name": "coverage", "status": "completed", "conclusion": "success"}]
                ),
                self.jobPayload(name="windows-deps"),
                self.jobPayload(name="windows", conclusion="failure"),
            ]
        )

        with (
            patch.object(poll_pr_checks, "runGhPrView", return_value=open_pr),
            patch.object(poll_pr_checks, "runGhPrFiles", return_value=("src/handler/CFightHandler.cpp",)),
            patch.object(poll_pr_checks, "runGhRunList", return_value=[{"databaseId": 1, "headSha": "abc123"}]),
            patch.object(poll_pr_checks, "runGhRunView", return_value=completed_run),
        ):
            with redirect_stdout(io.StringIO()):
                evaluation = poll_pr_checks.pollChecks(
                    pr="1",
                    repo=None,
                    workflow="build.yml",
                    requiredJobs=None,
                    requiredSteps=[],
                    intervalSeconds=1,
                    timeoutSeconds=1,
                )

        self.assertTrue(evaluation.failed)
        self.assertIn("windows=FAILURE", evaluation.message)

    def test_poll_checks_auto_defaults_to_linux_for_lightweight_paths(self) -> None:
        open_pr = {
            "headRefOid": "abc123",
            "url": "https://github.com/example/repo/pull/1",
            "state": "OPEN",
        }
        completed_run = self.runPayload([self.jobPayload(name="linux")])

        with (
            patch.object(poll_pr_checks, "runGhPrView", return_value=open_pr),
            patch.object(poll_pr_checks, "runGhPrFiles", return_value=("scripts/pr_review_audit.py",)),
            patch.object(poll_pr_checks, "runGhRunList", return_value=[{"databaseId": 1, "headSha": "abc123"}]),
            patch.object(poll_pr_checks, "runGhRunView", return_value=completed_run),
        ):
            with redirect_stdout(io.StringIO()):
                evaluation = poll_pr_checks.pollChecks(
                    pr="1",
                    repo=None,
                    workflow="build.yml",
                    requiredJobs=None,
                    requiredSteps=[],
                    intervalSeconds=1,
                    timeoutSeconds=1,
                )

        self.assertTrue(evaluation.succeeded)
        self.assertEqual(("linux",), tuple(job.name for job in evaluation.jobs))

    def test_explicit_linux_check_does_not_require_windows(self) -> None:
        open_pr = {
            "headRefOid": "abc123",
            "url": "https://github.com/example/repo/pull/1",
            "state": "OPEN",
        }
        completed_run = self.runPayload(
            [
                self.jobPayload(name="linux"),
                self.jobPayload(
                    name="linux-coverage",
                    steps=[{"name": "coverage", "status": "completed", "conclusion": "success"}],
                ),
                self.jobPayload(name="windows-deps"),
                self.jobPayload(name="windows", conclusion="failure"),
            ]
        )

        with (
            patch.object(poll_pr_checks, "runGhPrView", return_value=open_pr),
            patch.object(poll_pr_checks, "runGhPrFiles", return_value=("src/handler/CFightHandler.cpp",)),
            patch.object(poll_pr_checks, "runGhRunList", return_value=[{"databaseId": 1, "headSha": "abc123"}]),
            patch.object(poll_pr_checks, "runGhRunView", return_value=completed_run),
        ):
            with redirect_stdout(io.StringIO()):
                evaluation = poll_pr_checks.pollChecks(
                    pr="1",
                    repo=None,
                    workflow="build.yml",
                    requiredJobs=["linux"],
                    requiredSteps=[],
                    intervalSeconds=1,
                    timeoutSeconds=1,
                )

        self.assertTrue(evaluation.succeeded)
        self.assertEqual(("linux", "linux-coverage"), tuple(job.name for job in evaluation.jobs))

    def test_poll_checks_does_not_auto_require_coverage_for_unmatched_paths(self) -> None:
        open_pr = {
            "headRefOid": "abc123",
            "url": "https://github.com/example/repo/pull/1",
            "state": "OPEN",
        }
        completed_run = self.runPayload([self.jobPayload(name="linux")])

        with (
            patch.object(poll_pr_checks, "runGhPrView", return_value=open_pr),
            patch.object(poll_pr_checks, "runGhPrFiles", return_value=("docs/testing.md",)),
            patch.object(poll_pr_checks, "runGhRunList", return_value=[{"databaseId": 1, "headSha": "abc123"}]),
            patch.object(poll_pr_checks, "runGhRunView", return_value=completed_run),
        ):
            with redirect_stdout(io.StringIO()):
                evaluation = poll_pr_checks.pollChecks(
                    pr="1",
                    repo=None,
                    workflow="build.yml",
                    requiredJobs=["linux"],
                    requiredSteps=[],
                    intervalSeconds=1,
                    timeoutSeconds=1,
                )

        self.assertTrue(evaluation.succeeded)

    def test_poll_checks_can_disable_auto_coverage_requirement(self) -> None:
        open_pr = {
            "headRefOid": "abc123",
            "url": "https://github.com/example/repo/pull/1",
            "state": "OPEN",
        }
        completed_run = self.runPayload([self.jobPayload(name="linux")])

        with (
            patch.object(poll_pr_checks, "runGhPrView", return_value=open_pr),
            patch.object(poll_pr_checks, "runGhPrFiles") as files,
            patch.object(poll_pr_checks, "runGhRunList", return_value=[{"databaseId": 1, "headSha": "abc123"}]),
            patch.object(poll_pr_checks, "runGhRunView", return_value=completed_run),
        ):
            with redirect_stdout(io.StringIO()):
                evaluation = poll_pr_checks.pollChecks(
                    pr="1",
                    repo=None,
                    workflow="build.yml",
                    requiredJobs=["linux"],
                    requiredSteps=[],
                    intervalSeconds=1,
                    timeoutSeconds=1,
                    autoRequireCoverage=False,
                )

        self.assertTrue(evaluation.succeeded)
        files.assert_not_called()

    def test_poll_checks_stops_if_pr_merges_while_job_is_pending(self) -> None:
        open_pr = {
            "headRefOid": "abc123",
            "url": "https://github.com/example/repo/pull/1",
            "state": "OPEN",
        }
        merged_pr = {
            "headRefOid": "def456",
            "url": "https://github.com/example/repo/pull/1",
            "state": "MERGED",
            "mergedAt": "2026-06-19T09:19:25Z",
            "mergeCommit": {"oid": "merge123"},
        }
        pending_run = self.runPayload([self.jobPayload(status="in_progress", conclusion="")])

        with (
            patch.object(poll_pr_checks, "runGhPrView", side_effect=[open_pr, merged_pr]),
            patch.object(poll_pr_checks, "runGhPrFiles", return_value=()),
            patch.object(
                poll_pr_checks, "runGhRunList", return_value=[{"databaseId": 1, "headSha": "abc123"}]
            ) as run_list,
            patch.object(poll_pr_checks, "runGhRunView", return_value=pending_run),
            patch.object(poll_pr_checks.time, "sleep") as sleep,
        ):
            with redirect_stdout(io.StringIO()):
                evaluation = poll_pr_checks.pollChecks(
                    pr="1",
                    repo=None,
                    workflow="build.yml",
                    requiredJobs=["linux"],
                    requiredSteps=[],
                    intervalSeconds=30,
                    timeoutSeconds=120,
                )

        self.assertTrue(evaluation.succeeded)
        self.assertIn("already merged", evaluation.message)
        run_list.assert_called_once_with("abc123", "build.yml", None)
        sleep.assert_called_once_with(30)

    def test_verify_run_identity_blocks_head_sha_mismatch(self) -> None:
        run = self.runPayload([self.jobPayload()])
        run["headSha"] = "deadbeef"

        failure = poll_pr_checks.verifyRunIdentity(run, "abc123", "build.yml")

        self.assertIsNotNone(failure)
        self.assertTrue(failure.failed)
        self.assertIn("does not match PR head SHA", failure.message)

    def test_verify_run_identity_blocks_missing_head_sha(self) -> None:
        run = self.runPayload([self.jobPayload()])
        run.pop("headSha")

        failure = poll_pr_checks.verifyRunIdentity(run, "abc123", "build.yml")

        self.assertIsNotNone(failure)
        self.assertTrue(failure.failed)
        self.assertIn("no head SHA", failure.message)

    def test_verify_run_identity_blocks_non_pull_request_event(self) -> None:
        run = self.runPayload([self.jobPayload()])
        run["event"] = "workflow_dispatch"

        failure = poll_pr_checks.verifyRunIdentity(run, "abc123", "build.yml")

        self.assertIsNotNone(failure)
        self.assertTrue(failure.failed)
        self.assertIn("workflow_dispatch", failure.message)

    def test_verify_run_identity_blocks_wrong_workflow_name(self) -> None:
        run = self.runPayload([self.jobPayload()])
        run["workflowName"] = "lint-only"

        failure = poll_pr_checks.verifyRunIdentity(run, "abc123", "build.yml")

        self.assertIsNotNone(failure)
        self.assertTrue(failure.failed)
        self.assertIn("ambiguous check identity", failure.message)

    def test_verify_run_identity_passes_pull_request_run_for_head(self) -> None:
        run = self.runPayload([self.jobPayload()])
        run["event"] = "pull_request"

        self.assertIsNone(poll_pr_checks.verifyRunIdentity(run, "abc123", "build.yml"))

    def test_evaluate_run_blocks_ambiguous_duplicate_job_identity(self) -> None:
        evaluation = poll_pr_checks.evaluateRun(
            self.runPayload(
                [
                    self.jobPayload(name="linux"),
                    self.jobPayload(name="linux", conclusion="failure"),
                ]
            ),
            ["linux"],
            [],
        )

        self.assertTrue(evaluation.failed)
        self.assertIn("ambiguous required job identity: linux", evaluation.message)

    def test_poll_checks_blocks_run_whose_head_does_not_match_pr_head(self) -> None:
        open_pr = {
            "headRefOid": "abc123",
            "url": "https://github.com/example/repo/pull/1",
            "state": "OPEN",
        }
        # The run list returned the head SHA, but the fetched run payload reports a
        # different commit: the poller must refuse to trust it rather than pass.
        spoofed_run = self.runPayload([self.jobPayload(name="linux")])
        spoofed_run["headSha"] = "spoofed0"

        with (
            patch.object(poll_pr_checks, "runGhPrView", return_value=open_pr),
            patch.object(poll_pr_checks, "runGhPrFiles", return_value=("docs/testing.md",)),
            patch.object(poll_pr_checks, "runGhRunList", return_value=[{"databaseId": 1, "headSha": "abc123"}]),
            patch.object(poll_pr_checks, "runGhRunView", return_value=spoofed_run),
        ):
            with redirect_stdout(io.StringIO()):
                evaluation = poll_pr_checks.pollChecks(
                    pr="1",
                    repo=None,
                    workflow="build.yml",
                    requiredJobs=["linux"],
                    requiredSteps=[],
                    intervalSeconds=1,
                    timeoutSeconds=1,
                )

        self.assertTrue(evaluation.failed)
        self.assertIn("does not match PR head SHA", evaluation.message)

    def test_poll_checks_authority_change_cannot_drop_native_or_coverage(self) -> None:
        open_pr = {
            "headRefOid": "abc123",
            "url": "https://github.com/example/repo/pull/1",
            "state": "OPEN",
        }
        # The caller narrowed to --check linux, and the edited classifier would
        # classify the poller change as lightweight, but the windows job failed.
        # Authority enforcement must still require windows and block the merge.
        completed_run = self.runPayload(
            [
                self.jobPayload(name="linux"),
                self.jobPayload(
                    name="linux-coverage",
                    steps=[{"name": "coverage", "status": "completed", "conclusion": "success"}],
                ),
                self.jobPayload(name="windows-deps"),
                self.jobPayload(name="windows", conclusion="failure"),
            ]
        )

        with (
            patch.object(poll_pr_checks, "runGhPrView", return_value=open_pr),
            patch.object(poll_pr_checks, "runGhPrFiles", return_value=("scripts/poll_pr_checks.py",)),
            patch.object(poll_pr_checks, "runGhRunList", return_value=[{"databaseId": 1, "headSha": "abc123"}]),
            patch.object(poll_pr_checks, "runGhRunView", return_value=completed_run),
        ):
            with redirect_stdout(io.StringIO()):
                evaluation = poll_pr_checks.pollChecks(
                    pr="1",
                    repo=None,
                    workflow="build.yml",
                    requiredJobs=["linux"],
                    requiredSteps=[],
                    intervalSeconds=1,
                    timeoutSeconds=1,
                )

        self.assertTrue(evaluation.failed)
        self.assertIn("windows=FAILURE", evaluation.message)

    def test_poll_checks_authority_change_requires_coverage_step(self) -> None:
        open_pr = {
            "headRefOid": "abc123",
            "url": "https://github.com/example/repo/pull/1",
            "state": "OPEN",
        }
        # An authority change whose run skipped coverage must fail closed even
        # though every selected job succeeded.
        completed_run = self.runPayload(
            [
                self.jobPayload(name="linux"),
                self.jobPayload(name="windows-deps"),
                self.jobPayload(name="windows"),
            ]
        )

        with (
            patch.object(poll_pr_checks, "runGhPrView", return_value=open_pr),
            patch.object(poll_pr_checks, "runGhPrFiles", return_value=(".github/workflows/build.yml",)),
            patch.object(poll_pr_checks, "runGhRunList", return_value=[{"databaseId": 1, "headSha": "abc123"}]),
            patch.object(poll_pr_checks, "runGhRunView", return_value=completed_run),
        ):
            with redirect_stdout(io.StringIO()):
                evaluation = poll_pr_checks.pollChecks(
                    pr="1",
                    repo=None,
                    workflow="build.yml",
                    requiredJobs=None,
                    requiredSteps=[],
                    intervalSeconds=1,
                    timeoutSeconds=1,
                )

        self.assertTrue(evaluation.failed)
        self.assertEqual(("coverage",), evaluation.missingSteps)

    def test_run_gh_json_reports_missing_cli_as_poll_error(self) -> None:
        def raise_missing_gh(*_args: object, **_kwargs: object) -> None:
            raise FileNotFoundError(2, "No such file or directory", "gh")

        with patch.object(poll_pr_checks.subprocess, "run", side_effect=raise_missing_gh):
            with self.assertRaises(poll_pr_checks.PollError) as caught:
                poll_pr_checks.runGhJson(["gh", "pr", "view", "1"])

        self.assertIn("gh CLI not found on PATH", str(caught.exception))

    def test_run_gh_pr_files_reports_missing_cli_as_poll_error(self) -> None:
        def raise_missing_gh(*_args: object, **_kwargs: object) -> None:
            raise FileNotFoundError(2, "No such file or directory", "gh")

        with patch.object(poll_pr_checks.subprocess, "run", side_effect=raise_missing_gh):
            with self.assertRaises(poll_pr_checks.PollError) as caught:
                poll_pr_checks.runGhPrFiles("1", None)

        self.assertIn("gh CLI not found on PATH", str(caught.exception))

    def test_main_exits_cleanly_when_gh_cli_is_missing(self) -> None:
        def raise_missing_gh(*_args: object, **_kwargs: object) -> None:
            raise FileNotFoundError(2, "No such file or directory", "gh")

        stderr = io.StringIO()
        with patch.object(poll_pr_checks.subprocess, "run", side_effect=raise_missing_gh):
            with redirect_stderr(stderr):
                exit_code = poll_pr_checks.main(["1"])

        self.assertEqual(3, exit_code)
        self.assertIn("gh CLI not found on PATH", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
