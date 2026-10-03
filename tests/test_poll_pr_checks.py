from __future__ import annotations

import unittest

from scripts import poll_pr_checks


class PollPrChecksTest(unittest.TestCase):
    def runPayload(self, jobs: list[dict[str, object]]) -> dict[str, object]:
        return {
            "headSha": "abc123",
            "url": "https://github.com/example/repo/actions/runs/1",
            "workflowName": "build",
            "status": "completed",
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

    def test_default_required_steps_include_linux_validation_steps(self) -> None:
        steps = poll_pr_checks.defaultRequiredSteps(["linux"])

        self.assertIn("build test targets", steps)
        self.assertIn("test (c++)", steps)
        self.assertIn("performance guard (native)", steps)
        self.assertIn("test (python gameplay)", steps)
        self.assertIn("test (python ui)", steps)
        self.assertIn("package", steps)

    def test_validation_sensitive_files_include_workflow_and_poller_changes(self) -> None:
        files = poll_pr_checks.validationSensitiveFiles(
            [
                {"path": ".github/workflows/build.yml"},
                {"path": "scripts/poll_pr_checks.py"},
                {"path": "src/core/example.cpp"},
            ]
        )

        self.assertEqual((".github/workflows/build.yml", "scripts/poll_pr_checks.py"), files)

    def test_poll_checks_rejects_ci_polling_when_validation_files_changed(self) -> None:
        original_pr_view = poll_pr_checks.runGhPrView
        original_run_list = poll_pr_checks.runGhRunList
        try:
            poll_pr_checks.runGhPrView = lambda pr, repo: {
                "headRefOid": "abc123",
                "files": [{"path": ".github/workflows/build.yml"}],
            }
            poll_pr_checks.runGhRunList = lambda head_sha, workflow, repo: self.fail("run list should not be called")

            with self.assertRaisesRegex(poll_pr_checks.PollError, "validation-sensitive files"):
                poll_pr_checks.pollChecks("1", None, "build.yml", ["linux"], [], 1, 1)
        finally:
            poll_pr_checks.runGhPrView = original_pr_view
            poll_pr_checks.runGhRunList = original_run_list

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

    def test_evaluate_run_fails_missing_required_step_after_job_success(self) -> None:
        evaluation = poll_pr_checks.evaluateRun(
            self.runPayload([self.jobPayload()]),
            ["linux"],
            ["coverage"],
        )

        self.assertTrue(evaluation.failed)
        self.assertEqual(("linux/coverage",), evaluation.missingSteps)


if __name__ == "__main__":
    unittest.main()
