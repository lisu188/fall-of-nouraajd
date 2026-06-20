from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
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


if __name__ == "__main__":
    unittest.main()
