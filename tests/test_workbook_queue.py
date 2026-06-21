from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scripts import issue_queue, workbook_queue
from tests.test_issue_queue import IssueQueueTest


class WorkbookQueueTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.planning = self.root / "planning"
        self.planning.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def row(
        self,
        issue_name: str,
        *,
        priority: str = "P1",
        dependencies: str | None = None,
        status: str = issue_queue.STATUS_NOT_STARTED,
        target: str = "src/test.cpp",
    ) -> list[object]:
        helper = IssueQueueTest(methodName="runTest")
        row = helper.task_row(issue_name, priority, dependencies, target)
        if status == issue_queue.STATUS_DONE:
            row = helper.with_values(
                row,
                {
                    "Status": issue_queue.STATUS_DONE,
                    "Completed At UTC": "2026-01-01T00:00:00Z",
                    "Progress %": 100,
                    "Result Summary": "Completed fixture",
                    "Validation Results": "Fixture validation passed",
                    "Attempt": 1,
                },
            )
        return row

    def create_queue(self, name: str, rows: list[list[object]]) -> Path:
        path = self.planning / name
        helper = IssueQueueTest(methodName="runTest")
        helper.workbook_path = path
        helper.create_workbook(rows)
        return path

    def discover(self, paths: list[Path]) -> workbook_queue.Discovery:
        return workbook_queue.discoverQueues([str(path) for path in paths])

    def test_discovers_multiple_queue_workbooks_and_reports_incompatible_files(self) -> None:
        issue_a = "[EPIC_01][STORY_01][SUBSTORY_01] First queue issue"
        issue_b = "[EPIC_02][STORY_01][SUBSTORY_01] Second queue issue"
        first = self.create_queue("first.xlsx", [self.row(issue_a)])
        second = self.create_queue("second.xlsx", [self.row(issue_b)])
        reference = self.planning / "reference.xlsx"
        reference.write_text("not an XLSX queue", encoding="utf-8")

        discovery = self.discover([first, second, reference])
        try:
            summary = workbook_queue.workbookSummary(discovery)
            self.assertEqual(summary["compatibleCount"], 2)
            self.assertEqual(summary["skippedCount"], 1)
            self.assertEqual({item["issues"] for item in summary["compatible"]}, {1})
            self.assertIn("reference.xlsx", summary["skipped"][0]["workbook"])
        finally:
            discovery.close()

    def test_cross_workbook_dependency_is_valid_and_eligible(self) -> None:
        prerequisite = "[EPIC_01][STORY_01][SUBSTORY_01] Shared prerequisite"
        dependent = "[EPIC_01][STORY_02][SUBSTORY_01] Cross workbook dependent"
        first = self.create_queue(
            "first.xlsx",
            [self.row(dependent, priority="P0", dependencies=prerequisite)],
        )
        second = self.create_queue(
            "second.xlsx",
            [self.row(prerequisite, priority="P0", status=issue_queue.STATUS_DONE)],
        )

        discovery = self.discover([first, second])
        try:
            errors, warnings = workbook_queue.validateDiscovery(discovery)
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])
            payload = issue_queue.shortlistTasks(
                workbook_queue.aggregateState(discovery),
                seed="cross-workbook-test",
                includeRejected=True,
            )
            payload = workbook_queue.annotateShortlist(payload, discovery)
            self.assertTrue(payload["eligible"])
            self.assertEqual(payload["selected"]["issue"]["issueName"], dependent)
            self.assertEqual(payload["selected"]["issue"]["workbook"], workbook_queue.displayPath(first))
        finally:
            discovery.close()

    def test_duplicate_issue_names_across_workbooks_block_validation(self) -> None:
        issue = "[EPIC_01][STORY_01][SUBSTORY_01] Duplicate issue"
        first = self.create_queue("first.xlsx", [self.row(issue)])
        second = self.create_queue("second.xlsx", [self.row(issue)])

        discovery = self.discover([first, second])
        try:
            errors, _ = workbook_queue.validateDiscovery(discovery)
            self.assertTrue(any("Duplicate Issue Name across workbooks" in error for error in errors))
            with self.assertRaises(workbook_queue.AggregateQueueError):
                workbook_queue.requireUniqueIssue(discovery, issue)
        finally:
            discovery.close()

    def test_claim_updates_only_the_selected_source_workbook(self) -> None:
        issue_a = "[EPIC_01][STORY_01][SUBSTORY_01] First issue"
        issue_b = "[EPIC_02][STORY_01][SUBSTORY_01] Second issue"
        first = self.create_queue("first.xlsx", [self.row(issue_a)])
        second = self.create_queue("second.xlsx", [self.row(issue_b, priority="P0")])

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = workbook_queue.main(
                [
                    "claim",
                    "--workbook",
                    str(first),
                    "--workbook",
                    str(second),
                    "--owner",
                    "controller/test/subagent-1",
                    "--issue",
                    issue_b,
                    "--lease-minutes",
                    "30",
                ]
            )
        self.assertEqual(result, 0, output.getvalue())
        self.assertIn(str(second.resolve()), output.getvalue())

        first_state = issue_queue.loadQueue(first)
        second_state = issue_queue.loadQueue(second)
        try:
            self.assertEqual(issue_queue.taskByName(first_state, issue_a).status, issue_queue.STATUS_NOT_STARTED)
            claimed = issue_queue.taskByName(second_state, issue_b)
            self.assertEqual(claimed.status, issue_queue.STATUS_IN_PROGRESS)
            self.assertEqual(claimed.values["Owner"], "controller/test/subagent-1")
        finally:
            first_state.workbook.close()
            second_state.workbook.close()

    def test_repository_planning_workbooks_are_queue_compatible(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        expected = {
            "fall_of_nouraajd_issue_proposals.xlsx",
            "fall_of_nouraajd_creature_archetype_jira_plan.xlsx",
            "fall_of_nouraajd_github_issues_implementation_workbook.xlsx",
        }
        paths = [repository_root / "planning" / name for name in sorted(expected)]
        missing = [path.name for path in paths if not path.is_file()]
        self.assertEqual(missing, [], f"Missing planning workbooks: {missing}")

        discovery = workbook_queue.discoverQueues([str(path) for path in paths])
        try:
            self.assertEqual(
                {queue.path.name for queue in discovery.queues},
                expected,
                f"Skipped workbook details: {discovery.skipped}",
            )
            self.assertEqual(discovery.skipped, [])
            errors, _ = workbook_queue.validateDiscovery(discovery)
            self.assertEqual(errors, [])
        finally:
            discovery.close()


if __name__ == "__main__":
    unittest.main()
