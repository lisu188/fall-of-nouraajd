from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from scripts import pr_review_audit


def successCheck() -> dict[str, str]:
    return {"name": "build / linux", "status": "completed", "conclusion": "success"}


class PrReviewAuditTest(unittest.TestCase):
    def classify(self, payload: dict[str, object]) -> dict[str, object]:
        return pr_review_audit.classifyPr(payload)

    def test_ready_implementation_pr_keeps_active_claim_type(self) -> None:
        review = self.classify(
            {
                "number": 101,
                "title": "Fix combat flow",
                "files": ["src/handler/CFightHandler.cpp"],
                "mergeStateStatus": "CLEAN",
                "checks": [successCheck()],
                "queue": {
                    "status": "IN_PROGRESS",
                    "owner": "controller/ctrl-a/subagent-1",
                    "claimId": "abc123",
                },
            }
        )

        self.assertEqual("ready_to_merge", review["actionCategory"])
        self.assertEqual("implementation_pr_with_active_workbook_claim", review["prType"])
        self.assertTrue(review["mergeAllowed"])
        self.assertFalse(review["controllerDispatchAttention"])

    def test_auto_merge_disabled_blocks_ready_controller_pr(self) -> None:
        review = self.classify(
            {
                "number": 134,
                "title": "Fix validated implementation",
                "files": ["src/core/CGameContext.cpp"],
                "mergeStateStatus": "CLEAN",
                "checks": [successCheck()],
                "autoMergeError": "GraphQL: Auto merge is not allowed for this repository (enablePullRequestAutoMerge)",
                "queue": {
                    "status": "IN_PROGRESS",
                    "owner": "controller/ctrl-a/subagent-9",
                    "claimId": "validated-claim",
                },
            }
        )

        self.assertEqual("merge_policy_blocked", review["actionCategory"])
        self.assertEqual("implementation_pr_with_active_workbook_claim", review["prType"])
        self.assertIn("merge_policy_blocked", review["buckets"])
        self.assertIn("repository auto-merge is disabled or unavailable", review["blockers"])
        self.assertFalse(review["mergeAllowed"])
        self.assertTrue(review["controllerDispatchAttention"])
        self.assertTrue(review["humanApprovalRequired"])
        self.assertIn("explicit alternate merge authorization", review["recommendedActions"][0])

    def test_nested_auto_merge_error_blocks_ready_workflow_pr(self) -> None:
        review = self.classify(
            {
                "number": 135,
                "files": ["scripts/pr_review_audit.py"],
                "mergeStateStatus": "CLEAN",
                "checks": [successCheck()],
                "autoMergeRequest": {"error": "GraphQL: Auto merge is not allowed for this repository"},
            }
        )

        self.assertEqual("merge_policy_blocked", review["actionCategory"])
        self.assertEqual("workflow_pr", review["prType"])
        self.assertFalse(review["mergeAllowed"])
        self.assertTrue(review["humanApprovalRequired"])

    def test_workbook_only_queue_pr_is_ready_only_after_successful_signals(self) -> None:
        review = self.classify(
            {
                "number": 102,
                "title": "Claim queue row",
                "files": ["planning/fall_of_nouraajd_issue_proposals.xlsx"],
                "mergeable_state": "clean",
                "checkRollup": "success",
            }
        )

        self.assertEqual("ready_to_merge", review["actionCategory"])
        self.assertEqual("workbook_only_queue_pr", review["prType"])
        self.assertIn("workbook_only_queue_pr", review["buckets"])
        self.assertIn("confirm XLSX-only diff", review["recommendedActions"][0])

    def test_workbook_only_queue_pr_does_not_poll_pending_ci(self) -> None:
        review = self.classify(
            {
                "number": 121,
                "title": "Claim queue row",
                "files": ["planning/fall_of_nouraajd_issue_proposals.xlsx"],
                "mergeStateStatus": "CLEAN",
                "checks": [{"name": "build / linux", "status": "in_progress"}],
            }
        )

        self.assertEqual("ready_to_merge", review["actionCategory"])
        self.assertEqual("workbook_only_queue_pr", review["prType"])
        self.assertEqual("pending", review["checkState"])
        self.assertEqual(["build / linux"], review["pendingChecks"])
        self.assertIn("ci_exempt_pending", review["buckets"])
        self.assertNotIn("poll", review["buckets"])
        self.assertTrue(review["mergeAllowed"])
        self.assertIn("confirm XLSX-only diff", review["recommendedActions"][0])

    def test_workbook_only_queue_pr_still_blocks_failed_ci(self) -> None:
        review = self.classify(
            {
                "number": 122,
                "title": "Claim queue row",
                "files": ["planning/fall_of_nouraajd_issue_proposals.xlsx"],
                "mergeStateStatus": "CLEAN",
                "checks": [{"name": "build / linux", "status": "completed", "conclusion": "failure"}],
            }
        )

        self.assertEqual("failing_ci", review["actionCategory"])
        self.assertEqual("workbook_only_queue_pr", review["prType"])
        self.assertFalse(review["mergeAllowed"])
        self.assertIn("required check failure: build / linux", review["blockers"])

    def test_dirty_and_failing_pr_requires_update_before_ci_fix(self) -> None:
        review = self.classify(
            {
                "number": 103,
                "files": ["src/gui/CListView.cpp"],
                "mergeable_state": "dirty",
                "checks": [{"name": "coverage", "state": "FAILURE"}],
                "queue": {"status": "IN_PROGRESS", "owner": "controller/ctrl-a/subagent-2"},
            }
        )

        self.assertEqual("needs_update_rebase", review["actionCategory"])
        self.assertIn("failing_ci", review["buckets"])
        self.assertTrue(review["controllerDispatchAttention"])
        self.assertTrue(any("merge state DIRTY" in blocker for blocker in review["blockers"]))
        self.assertTrue(any("required check failure" in blocker for blocker in review["blockers"]))

    def test_pending_checks_are_pollable(self) -> None:
        review = self.classify(
            {
                "number": 104,
                "files": ["scripts/issue_queue.py"],
                "mergeStateStatus": "CLEAN",
                "checks": [{"name": "build / linux", "status": "in_progress"}],
            }
        )

        self.assertEqual("poll", review["actionCategory"])
        self.assertEqual("workflow_pr", review["prType"])
        self.assertEqual(["build / linux"], review["pendingChecks"])

    def test_status_check_rollup_list_reports_pending_checks(self) -> None:
        review = self.classify(
            {
                "number": 118,
                "files": ["scripts/pr_review_audit.py"],
                "mergeStateStatus": "CLEAN",
                "statusCheckRollup": [
                    {
                        "__typename": "CheckRun",
                        "name": "linux-fast",
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                    },
                    {
                        "__typename": "CheckRun",
                        "name": "linux",
                        "status": "IN_PROGRESS",
                        "conclusion": "",
                    },
                ],
            }
        )

        self.assertEqual("poll", review["actionCategory"])
        self.assertEqual("pending", review["checkState"])
        self.assertEqual(["linux"], review["pendingChecks"])

    def test_status_check_rollup_list_reports_failures(self) -> None:
        review = self.classify(
            {
                "number": 119,
                "files": ["scripts/pr_review_audit.py"],
                "mergeStateStatus": "UNKNOWN",
                "statusCheckRollup": [
                    {
                        "__typename": "CheckRun",
                        "name": "linux-fast",
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                    },
                    {
                        "__typename": "CheckRun",
                        "name": "linux",
                        "status": "COMPLETED",
                        "conclusion": "FAILURE",
                    },
                ],
            }
        )

        self.assertEqual("failing_ci", review["actionCategory"])
        self.assertEqual("failure", review["checkState"])
        self.assertEqual(["linux"], review["failedChecks"])

    def test_skipped_status_check_rollup_entry_is_non_blocking(self) -> None:
        review = self.classify(
            {
                "number": 120,
                "files": ["scripts/pr_review_audit.py"],
                "mergeStateStatus": "CLEAN",
                "statusCheckRollup": [
                    {
                        "__typename": "CheckRun",
                        "name": "linux",
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                    },
                    {
                        "__typename": "CheckRun",
                        "name": "linux-coverage",
                        "status": "COMPLETED",
                        "conclusion": "SKIPPED",
                    },
                ],
            }
        )

        self.assertEqual("ready_to_merge", review["actionCategory"])
        self.assertEqual("success", review["checkState"])
        self.assertEqual([], review["failedChecks"])

    def test_object_shaped_status_check_rollup_resolves_aggregate_state(self) -> None:
        review = self.classify(
            {
                "number": 121,
                "files": ["scripts/pr_review_audit.py"],
                "mergeStateStatus": "CLEAN",
                "statusCheckRollup": {"state": "SUCCESS"},
            }
        )

        self.assertEqual("success", review["checkState"])
        self.assertEqual([], review["failedChecks"])
        self.assertNotIn("check rollup is missing or unrecognized", review.get("blockers", []))

    def test_object_shaped_status_check_rollup_reports_failure(self) -> None:
        review = self.classify(
            {
                "number": 122,
                "files": ["scripts/pr_review_audit.py"],
                "mergeStateStatus": "UNKNOWN",
                "statusCheckRollup": {"state": "FAILURE"},
            }
        )

        self.assertEqual("failure", review["checkState"])
        self.assertEqual("failing_ci", review["actionCategory"])

    def test_newer_duplicate_check_success_replaces_older_cancelled_attempt(self) -> None:
        review = self.classify(
            {
                "number": 123,
                "files": ["scripts/pr_review_audit.py"],
                "mergeStateStatus": "CLEAN",
                "statusCheckRollup": [
                    {
                        "__typename": "CheckRun",
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "CANCELLED",
                        "completedAt": "2026-06-20T10:00:00Z",
                    },
                    {
                        "__typename": "CheckRun",
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                        "completedAt": "2026-06-20T10:10:00Z",
                    },
                ],
            }
        )

        self.assertEqual("ready_to_merge", review["actionCategory"])
        self.assertEqual("success", review["checkState"])
        self.assertEqual([], review["failedChecks"])

    def test_newer_duplicate_check_pending_replaces_older_failure(self) -> None:
        review = self.classify(
            {
                "number": 124,
                "files": ["scripts/pr_review_audit.py"],
                "mergeStateStatus": "CLEAN",
                "statusCheckRollup": [
                    {
                        "__typename": "CheckRun",
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "FAILURE",
                        "completedAt": "2026-06-20T10:00:00Z",
                    },
                    {
                        "__typename": "CheckRun",
                        "name": "linux",
                        "workflowName": "build",
                        "status": "IN_PROGRESS",
                        "startedAt": "2026-06-20T10:15:00Z",
                    },
                ],
            }
        )

        self.assertEqual("poll", review["actionCategory"])
        self.assertEqual("pending", review["checkState"])
        self.assertEqual([], review["failedChecks"])
        self.assertEqual(["linux"], review["pendingChecks"])

    def test_newer_duplicate_check_failure_replaces_older_success(self) -> None:
        review = self.classify(
            {
                "number": 125,
                "files": ["scripts/pr_review_audit.py"],
                "mergeStateStatus": "CLEAN",
                "statusCheckRollup": [
                    {
                        "__typename": "CheckRun",
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                        "completedAt": "2026-06-20T10:00:00Z",
                    },
                    {
                        "__typename": "CheckRun",
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "FAILURE",
                        "completedAt": "2026-06-20T10:15:00Z",
                    },
                ],
            }
        )

        self.assertEqual("failing_ci", review["actionCategory"])
        self.assertEqual("failure", review["checkState"])
        self.assertEqual(["linux"], review["failedChecks"])

    def test_same_label_checks_from_different_workflows_remain_independent(self) -> None:
        review = self.classify(
            {
                "number": 126,
                "files": ["scripts/pr_review_audit.py"],
                "mergeStateStatus": "CLEAN",
                "statusCheckRollup": [
                    {
                        "__typename": "CheckRun",
                        "name": "lint",
                        "workflowName": "fast",
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                        "completedAt": "2026-06-20T10:00:00Z",
                    },
                    {
                        "__typename": "CheckRun",
                        "name": "lint",
                        "workflowName": "full",
                        "status": "COMPLETED",
                        "conclusion": "FAILURE",
                        "completedAt": "2026-06-20T10:05:00Z",
                    },
                ],
            }
        )

        self.assertEqual("failing_ci", review["actionCategory"])
        self.assertEqual(["lint"], review["failedChecks"])

    def test_missing_duplicate_ordering_uses_conservative_state(self) -> None:
        review = self.classify(
            {
                "number": 127,
                "files": ["scripts/pr_review_audit.py"],
                "mergeStateStatus": "CLEAN",
                "statusCheckRollup": [
                    {
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                    },
                    {
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "FAILURE",
                    },
                ],
            }
        )

        self.assertEqual("failing_ci", review["actionCategory"])
        self.assertEqual("failure", review["checkState"])
        self.assertEqual(["linux"], review["failedChecks"])

    def test_attempt_number_orders_duplicate_checks_without_timestamps(self) -> None:
        review = self.classify(
            {
                "number": 128,
                "files": ["scripts/pr_review_audit.py"],
                "mergeStateStatus": "CLEAN",
                "statusCheckRollup": [
                    {
                        "__typename": "CheckRun",
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "FAILURE",
                        "checkSuite": {"workflowRun": {"runAttempt": 1}},
                    },
                    {
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                        "run_attempt": 2,
                    },
                ],
            }
        )

        self.assertEqual("ready_to_merge", review["actionCategory"])
        self.assertEqual("success", review["checkState"])
        self.assertEqual([], review["failedChecks"])

    def test_check_attempt_dedupe_table(self) -> None:
        cases = [
            {
                "name": "cancelled_then_success_reports_success",
                "checks": [
                    {
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "CANCELLED",
                        "completedAt": "2026-06-20T10:00:00Z",
                    },
                    {
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                        "completedAt": "2026-06-20T10:10:00Z",
                    },
                ],
                "state": "success",
                "failed": [],
                "pending": [],
                "staleStates": ["failure"],
                "ambiguous": [],
            },
            {
                "name": "failure_then_pending_reports_pending",
                "checks": [
                    {
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "FAILURE",
                        "completedAt": "2026-06-20T10:00:00Z",
                    },
                    {
                        "name": "linux",
                        "workflowName": "build",
                        "status": "IN_PROGRESS",
                        "startedAt": "2026-06-20T10:20:00Z",
                    },
                ],
                "state": "pending",
                "failed": [],
                "pending": ["linux"],
                "staleStates": ["failure"],
                "ambiguous": [],
            },
            {
                "name": "success_then_failure_reports_failure",
                "checks": [
                    {
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                        "completedAt": "2026-06-20T10:00:00Z",
                    },
                    {
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "FAILURE",
                        "completedAt": "2026-06-20T10:20:00Z",
                    },
                ],
                "state": "failure",
                "failed": ["linux"],
                "pending": [],
                "staleStates": ["success"],
                "ambiguous": [],
            },
            {
                "name": "mixed_graphql_and_rest_shapes_group_by_identity",
                "checks": [
                    {
                        "__typename": "CheckRun",
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "CANCELLED",
                        "checkSuite": {"workflowRun": {"runAttempt": 1, "databaseId": 900}},
                        "detailsUrl": "https://example.test/run/900",
                    },
                    {
                        "name": "linux",
                        "workflow_name": "build",
                        "status": "completed",
                        "conclusion": "success",
                        "run_attempt": 2,
                        "check_suite": {"workflow_run": {"run_attempt": 2, "id": 901}},
                        "details_url": "https://example.test/run/901",
                    },
                ],
                "state": "success",
                "failed": [],
                "pending": [],
                "staleStates": ["failure"],
                "ambiguous": [],
            },
            {
                "name": "missing_timestamps_use_run_ids",
                "checks": [
                    {
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "FAILURE",
                        "checkSuite": {"workflowRun": {"databaseId": 11}},
                    },
                    {
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                        "check_suite": {"workflow_run": {"id": 12}},
                    },
                ],
                "state": "success",
                "failed": [],
                "pending": [],
                "staleStates": ["failure"],
                "ambiguous": [],
            },
            {
                "name": "missing_ordering_with_conflicting_states_is_conservative_and_ambiguous",
                "checks": [
                    {"name": "linux", "workflowName": "build", "status": "COMPLETED", "conclusion": "SUCCESS"},
                    {"name": "linux", "workflowName": "build", "status": "COMPLETED", "conclusion": "FAILURE"},
                ],
                "state": "failure",
                "failed": ["linux"],
                "pending": [],
                "staleStates": ["success"],
                "ambiguous": ["linux"],
            },
            {
                "name": "duplicate_identical_nodes_collapse_without_ambiguity",
                "checks": [
                    {"name": "linux", "workflowName": "build", "status": "COMPLETED", "conclusion": "SUCCESS"},
                    {"name": "linux", "workflowName": "build", "status": "COMPLETED", "conclusion": "SUCCESS"},
                ],
                "state": "success",
                "failed": [],
                "pending": [],
                "staleStates": ["success"],
                "ambiguous": [],
            },
            {
                "name": "same_label_status_context_and_check_run_stay_independent",
                "checks": [
                    {
                        "__typename": "CheckRun",
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                        "completedAt": "2026-06-20T10:10:00Z",
                    },
                    {
                        "__typename": "StatusContext",
                        "context": "linux",
                        "state": "FAILURE",
                        "createdAt": "2026-06-20T10:00:00Z",
                    },
                ],
                "state": "failure",
                "failed": ["linux"],
                "pending": [],
                "staleStates": [],
                "ambiguous": [],
            },
            {
                "name": "same_label_checks_from_different_apps_stay_independent",
                "checks": [
                    {
                        "name": "lint",
                        "app": {"slug": "ci-alpha"},
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                        "completedAt": "2026-06-20T10:10:00Z",
                    },
                    {
                        "name": "lint",
                        "app": {"slug": "ci-beta"},
                        "status": "COMPLETED",
                        "conclusion": "FAILURE",
                        "completedAt": "2026-06-20T10:00:00Z",
                    },
                ],
                "state": "failure",
                "failed": ["lint"],
                "pending": [],
                "staleStates": [],
                "ambiguous": [],
            },
            {
                "name": "stale_rerun_does_not_suppress_independent_current_failure",
                "checks": [
                    {
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "CANCELLED",
                        "completedAt": "2026-06-20T10:00:00Z",
                    },
                    {
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                        "completedAt": "2026-06-20T10:10:00Z",
                    },
                    {
                        "name": "coverage",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "FAILURE",
                        "completedAt": "2026-06-20T10:05:00Z",
                    },
                ],
                "state": "failure",
                "failed": ["coverage"],
                "pending": [],
                "staleStates": ["failure"],
                "ambiguous": [],
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                summary = pr_review_audit.checkSummary({"checks": case["checks"]})
                self.assertEqual(case["state"], summary.state)
                self.assertEqual(tuple(case["failed"]), summary.failed)
                self.assertEqual(tuple(case["pending"]), summary.pending)
                self.assertEqual(case["staleStates"], [record["state"] for record in summary.ignoredStale])
                self.assertEqual(tuple(case["ambiguous"]), summary.ambiguous)

    def test_ignored_stale_attempts_are_exposed_additively_in_json(self) -> None:
        review = self.classify(
            {
                "number": 136,
                "files": ["scripts/pr_review_audit.py"],
                "mergeStateStatus": "CLEAN",
                "statusCheckRollup": [
                    {
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "CANCELLED",
                        "completedAt": "2026-06-20T10:00:00Z",
                        "detailsUrl": "https://example.test/run/1",
                    },
                    {
                        "name": "linux",
                        "workflowName": "build",
                        "status": "COMPLETED",
                        "conclusion": "SUCCESS",
                        "completedAt": "2026-06-20T10:10:00Z",
                        "detailsUrl": "https://example.test/run/2",
                    },
                ],
            }
        )

        self.assertEqual("ready_to_merge", review["actionCategory"])
        self.assertEqual("success", review["checkState"])
        self.assertEqual([], review["failedChecks"])
        self.assertEqual([], review["ambiguousChecks"])
        self.assertEqual(1, len(review["ignoredStaleChecks"]))
        stale = review["ignoredStaleChecks"][0]
        self.assertEqual("linux", stale["name"])
        self.assertEqual("failure", stale["state"])
        self.assertEqual("success", stale["effectiveState"])
        self.assertEqual("https://example.test/run/1", stale["url"])
        self.assertEqual(1, stale["position"])
        # Backward-compatible schema: previously existing keys are still present.
        for key in ("checkState", "failedChecks", "pendingChecks", "blockers", "mergeAllowed", "buckets"):
            self.assertIn(key, review)

    def test_ambiguous_duplicate_ordering_reports_blocker_and_marker(self) -> None:
        review = self.classify(
            {
                "number": 137,
                "files": ["scripts/pr_review_audit.py"],
                "mergeStateStatus": "CLEAN",
                "statusCheckRollup": [
                    {"name": "linux", "workflowName": "build", "status": "COMPLETED", "conclusion": "SUCCESS"},
                    {"name": "linux", "workflowName": "build", "status": "COMPLETED", "conclusion": "FAILURE"},
                ],
            }
        )

        self.assertEqual("failing_ci", review["actionCategory"])
        self.assertEqual(["linux"], review["ambiguousChecks"])
        self.assertIn("ambiguous duplicate check attempt ordering: linux", review["blockers"])

    def test_duplicate_resolution_is_stable_under_input_reordering(self) -> None:
        checks = [
            {
                "name": "linux",
                "workflowName": "build",
                "status": "COMPLETED",
                "conclusion": "FAILURE",
                "completedAt": "2026-06-20T10:00:00Z",
            },
            {
                "name": "linux",
                "workflowName": "build",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
                "completedAt": "2026-06-20T10:10:00Z",
            },
        ]

        forward = pr_review_audit.checkSummary({"checks": checks})
        backward = pr_review_audit.checkSummary({"checks": list(reversed(checks))})

        self.assertEqual("success", forward.state)
        self.assertEqual(forward.state, backward.state)
        self.assertEqual(forward.failed, backward.failed)
        self.assertEqual(forward.pending, backward.pending)
        self.assertEqual(
            [record["state"] for record in forward.ignoredStale],
            [record["state"] for record in backward.ignoredStale],
        )

    def test_table_output_explains_ignored_stale_attempts(self) -> None:
        payload = pr_review_audit.auditPayload(
            [
                {
                    "number": 138,
                    "files": ["scripts/pr_review_audit.py"],
                    "mergeStateStatus": "CLEAN",
                    "statusCheckRollup": [
                        {
                            "name": "linux",
                            "workflowName": "build",
                            "status": "COMPLETED",
                            "conclusion": "CANCELLED",
                            "completedAt": "2026-06-20T10:00:00Z",
                        },
                        {
                            "name": "linux",
                            "workflowName": "build",
                            "status": "COMPLETED",
                            "conclusion": "SUCCESS",
                            "completedAt": "2026-06-20T10:10:00Z",
                        },
                    ],
                }
            ]
        )

        table = pr_review_audit.renderTable(payload)
        self.assertIn("PR\tACTION\tTYPE\tCHECKS\tMERGE\tATTENTION\tBLOCKERS\tSTALE", table)
        self.assertIn("ignored stale failure attempt of linux (current: success)", table)
        self.assertEqual(1, payload["summary"]["ignoredStaleChecks"])
        self.assertEqual(0, payload["summary"]["ambiguousChecks"])

    def test_stale_linked_claim_requires_human_review(self) -> None:
        review = self.classify(
            {
                "number": 105,
                "files": ["res/maps/siege/script.py"],
                "mergeStateStatus": "CLEAN",
                "checks": [successCheck()],
                "queue": {
                    "status": "IN_PROGRESS",
                    "owner": "controller/ctrl-a/subagent-3",
                    "claimId": "stale-claim",
                    "leaseExpired": True,
                },
            }
        )

        self.assertEqual("human_review_required", review["actionCategory"])
        self.assertEqual("implementation_pr_with_stale_workbook_claim", review["prType"])
        self.assertTrue(review["controllerDispatchAttention"])
        self.assertIn("linked workbook claim requires recovery before merge or cleanup", review["blockers"])

    def test_heartbeat_overdue_linked_claim_requires_human_review(self) -> None:
        review = self.classify(
            {
                "number": 130,
                "files": ["src/gui/CMap.cpp"],
                "mergeStateStatus": "CLEAN",
                "checks": [successCheck()],
                "queue": {
                    "status": "IN_PROGRESS",
                    "owner": "controller/ctrl-a/subagent-5",
                    "claimId": "heartbeat-overdue-claim",
                    "heartbeatOverdue": True,
                    "leaseExpired": False,
                },
            }
        )

        self.assertEqual("human_review_required", review["actionCategory"])
        self.assertEqual("implementation_pr_with_stale_workbook_claim", review["prType"])
        self.assertTrue(review["controllerDispatchAttention"])

    def test_reclaimable_linked_claim_requires_human_review(self) -> None:
        review = self.classify(
            {
                "number": 131,
                "files": ["src/core/CGameContext.cpp"],
                "mergeStateStatus": "CLEAN",
                "checks": [successCheck()],
                "queue": {
                    "status": "IN_PROGRESS",
                    "owner": "controller/ctrl-a/subagent-6",
                    "claimId": "reclaimable-claim",
                    "reclaimable": True,
                },
            }
        )

        self.assertEqual("human_review_required", review["actionCategory"])
        self.assertEqual("implementation_pr_with_stale_workbook_claim", review["prType"])
        self.assertTrue(review["controllerDispatchAttention"])

    def test_unhealthy_claim_health_requires_human_review(self) -> None:
        review = self.classify(
            {
                "number": 132,
                "files": ["src/handler/CFightHandler.cpp"],
                "mergeStateStatus": "CLEAN",
                "checks": [successCheck()],
                "queue": {
                    "status": "IN_PROGRESS",
                    "owner": "controller/ctrl-a/subagent-7",
                    "claimId": "lease-expired-recent-heartbeat",
                    "claimHealth": "lease_expired_heartbeat_recent",
                },
            }
        )

        self.assertEqual("human_review_required", review["actionCategory"])
        self.assertEqual("implementation_pr_with_stale_workbook_claim", review["prType"])
        self.assertTrue(review["controllerDispatchAttention"])

    def test_healthy_claim_health_keeps_active_claim_type(self) -> None:
        review = self.classify(
            {
                "number": 133,
                "files": ["src/handler/CFightHandler.cpp"],
                "mergeStateStatus": "CLEAN",
                "checks": [successCheck()],
                "queue": {
                    "status": "IN_PROGRESS",
                    "owner": "controller/ctrl-a/subagent-8",
                    "claimId": "healthy-claim",
                    "claimHealth": "healthy",
                    "heartbeatOverdue": False,
                    "leaseExpired": False,
                    "reclaimable": False,
                },
            }
        )

        self.assertEqual("ready_to_merge", review["actionCategory"])
        self.assertEqual("implementation_pr_with_active_workbook_claim", review["prType"])
        self.assertFalse(review["controllerDispatchAttention"])

    def test_unknown_unlinked_pr_is_not_merge_ready(self) -> None:
        review = self.classify(
            {
                "number": 106,
                "title": "Mystery branch",
                "mergeStateStatus": "CLEAN",
                "checks": [successCheck()],
            }
        )

        self.assertEqual("human_review_required", review["actionCategory"])
        self.assertEqual("unknown_pr", review["prType"])
        self.assertFalse(review["controllerDispatchAttention"])
        self.assertFalse(review["mergeAllowed"])

    def test_controller_owned_unknown_pr_counts_as_attention_debt(self) -> None:
        review = self.classify(
            {
                "number": 115,
                "title": "Controller branch with missing queue signals",
                "mergeStateStatus": "CLEAN",
                "checks": [successCheck()],
                "queue": {"controllerOwned": True},
            }
        )

        self.assertEqual("human_review_required", review["actionCategory"])
        self.assertEqual("unknown_pr", review["prType"])
        self.assertTrue(review["controllerDispatchAttention"])

    def test_github_changed_file_count_is_missing_signal_not_crash(self) -> None:
        review = self.classify(
            {
                "number": 113,
                "title": "Raw GitHub PR list item",
                "changed_files": 3,
                "mergeable_state": "clean",
                "checkRollup": "success",
            }
        )

        self.assertEqual("human_review_required", review["actionCategory"])
        self.assertEqual("unknown_pr", review["prType"])
        self.assertIn("missing queue link", review["blockers"][0])

    def test_non_controller_owned_failing_pr_does_not_count_as_controller_attention(self) -> None:
        review = self.classify(
            {
                "number": 116,
                "files": ["src/gui/CListView.cpp"],
                "mergeable_state": "dirty",
                "checks": [{"name": "coverage", "state": "FAILURE"}],
                "queue": {"status": "IN_PROGRESS", "owner": "external-worker"},
            }
        )

        self.assertEqual("needs_update_rebase", review["actionCategory"])
        self.assertFalse(review["controllerOwned"])
        self.assertFalse(review["controllerDispatchAttention"])

    def test_unstable_merge_state_requires_human_review(self) -> None:
        review = self.classify(
            {
                "number": 117,
                "files": ["scripts/pr_review_audit.py"],
                "mergeStateStatus": "UNSTABLE",
                "checks": [successCheck()],
            }
        )

        self.assertEqual("human_review_required", review["actionCategory"])
        self.assertEqual("workflow_pr", review["prType"])
        self.assertFalse(review["mergeAllowed"])
        self.assertIn("merge state UNSTABLE requires human review", review["blockers"])

    def test_graphql_nodes_payloads_are_supported(self) -> None:
        review = self.classify(
            {
                "number": 114,
                "files": {"nodes": [{"path": "scripts/pr_review_audit.py"}]},
                "labels": {"nodes": [{"name": "workflow"}]},
                "checks": {"nodes": [{"name": "build / linux", "state": "SUCCESS"}]},
                "mergeStateStatus": "CLEAN",
            }
        )

        self.assertEqual("ready_to_merge", review["actionCategory"])
        self.assertEqual("workflow_pr", review["prType"])

    def test_obsolete_duplicate_close_requires_human_approval(self) -> None:
        review = self.classify(
            {
                "number": 107,
                "files": ["docs/old-flow.md"],
                "mergeStateStatus": "CLEAN",
                "checks": [successCheck()],
                "labels": [{"name": "duplicate"}],
            }
        )

        self.assertEqual("obsolete_duplicate_close", review["actionCategory"])
        self.assertTrue(review["humanApprovalRequired"])
        self.assertFalse(review["cleanupAllowed"])

    def test_closed_merged_branch_is_cleanup_candidate_only(self) -> None:
        review = self.classify(
            {
                "number": 108,
                "state": "closed",
                "merged": True,
                "files": ["scripts/poll_pr_checks.py"],
                "mergeStateStatus": "CLEAN",
                "checks": [successCheck()],
            }
        )

        self.assertEqual("branch_cleanup_candidate", review["actionCategory"])
        self.assertTrue(review["humanApprovalRequired"])
        self.assertFalse(review["cleanupAllowed"])

    def test_github_merged_state_is_cleanup_candidate_only(self) -> None:
        review = self.classify(
            {
                "number": 129,
                "state": "MERGED",
                "mergedAt": "2026-06-20T18:59:01Z",
                "mergeCommit": {"oid": "25a5a983d2085cd92564fa56a1349648416e8a2b"},
                "files": ["planning/fall_of_nouraajd_issue_proposals.xlsx"],
                "mergeStateStatus": "UNKNOWN",
                "statusCheckRollup": [{"name": "linux", "status": "IN_PROGRESS"}],
            }
        )

        self.assertEqual("branch_cleanup_candidate", review["actionCategory"])
        self.assertEqual("workbook_only_queue_pr", review["prType"])
        self.assertEqual("pending", review["checkState"])
        self.assertTrue(review["humanApprovalRequired"])
        self.assertFalse(review["mergeAllowed"])
        self.assertNotIn("PR state is merged", review["blockers"])

    def test_dirty_local_recovery_state_is_never_touch(self) -> None:
        review = self.classify(
            {
                "number": 109,
                "files": ["src/core/CGameContext.cpp"],
                "mergeStateStatus": "CLEAN",
                "checks": [successCheck()],
                "queue": {"status": "IN_PROGRESS", "owner": "controller/ctrl-a/subagent-4"},
                "local": {"dirtyWorktree": True},
            }
        )

        self.assertEqual("never_touch", review["actionCategory"])
        self.assertIn("local worktree is dirty", review["blockers"])
        self.assertFalse(review["cleanupAllowed"])

    def test_audit_payload_summarizes_actions_and_attention(self) -> None:
        payload = pr_review_audit.auditPayload(
            [
                {
                    "number": 110,
                    "files": ["scripts/issue_queue.py"],
                    "mergeStateStatus": "CLEAN",
                    "checks": [successCheck()],
                },
                {
                    "number": 111,
                    "files": ["src/core/CGameContext.cpp"],
                    "mergeStateStatus": "DIRTY",
                    "checks": [successCheck()],
                    "queue": {"status": "IN_PROGRESS", "owner": "controller/ctrl-a/subagent-4"},
                },
            ]
        )

        self.assertTrue(payload["readOnly"])
        self.assertEqual(2, payload["summary"]["total"])
        self.assertEqual(1, payload["summary"]["actions"]["ready_to_merge"])
        self.assertEqual(1, payload["summary"]["controllerDispatchAttention"])

    def test_cli_outputs_json_and_table_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "prs.json"
            path.write_text(
                json.dumps(
                    {
                        "pullRequests": [
                            {
                                "number": 112,
                                "files": ["scripts/pr_review_audit.py"],
                                "mergeStateStatus": "CLEAN",
                                "checks": [successCheck()],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exitCode = pr_review_audit.main(["--input", str(path)])
            self.assertEqual(0, exitCode)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(1, payload["summary"]["total"])

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exitCode = pr_review_audit.main(["--input", str(path), "--format", "table"])
            self.assertEqual(0, exitCode)
            self.assertIn("PR\tACTION\tTYPE", stdout.getvalue())
            self.assertIn("#112", stdout.getvalue())


class PrPreflightTest(unittest.TestCase):
    ISSUE = "[EPIC_01][STORY_04][SUBSTORY_01] Add pull-request preflight duplicate and scope guard"
    CLAIM_ID = "claim-623-abc"
    OWNER = "controller/ctrl-a/subagent-1"
    HEAD = "codex/e01-s04-ss01-preflight"

    def claim(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "issueName": self.ISSUE,
            "claimId": self.CLAIM_ID,
            "owner": self.OWNER,
            "headBranch": self.HEAD,
        }
        payload.update(overrides)
        return payload

    def preflight(self, **request: object) -> dict[str, object]:
        request.setdefault("claim", self.claim())
        return pr_review_audit.preflightVerdict(request)

    def test_no_snapshot_conflicts_allows_pr(self) -> None:
        verdict = self.preflight(pullRequests=[])

        self.assertEqual("allow", verdict["verdict"])
        self.assertTrue(verdict["allowed"])
        self.assertTrue(verdict["readOnly"])
        self.assertEqual([], verdict["openDuplicates"])
        self.assertEqual([], verdict["mergedDuplicates"])
        self.assertEqual([], verdict["reasons"])

    def test_second_open_pr_for_same_live_claim_is_rejected(self) -> None:
        verdict = self.preflight(
            pullRequests=[{"number": 1490, "state": "open", "claimId": self.CLAIM_ID, "headBranch": "codex/other-head"}]
        )

        self.assertEqual("reject_duplicate_open", verdict["verdict"])
        self.assertFalse(verdict["allowed"])
        self.assertEqual([1490], [dup["number"] for dup in verdict["openDuplicates"]])
        self.assertIn("open PR #1490 duplicates this live claim: open PR carries the same claim id", verdict["reasons"])

    def test_open_pr_with_same_issue_name_and_different_claim_is_rejected(self) -> None:
        verdict = self.preflight(
            pullRequests=[
                {
                    "number": 1491,
                    "state": "open",
                    "claimId": "stale-claim",
                    "issueName": self.ISSUE,
                    "headBranch": "codex/old",
                }
            ]
        )

        self.assertEqual("reject_duplicate_open", verdict["verdict"])
        self.assertEqual("open PR references the same issue name", verdict["openDuplicates"][0]["reason"])

    def test_open_pr_on_same_head_branch_is_rejected(self) -> None:
        verdict = self.preflight(pullRequests=[{"number": 1492, "state": "open", "headRefName": self.HEAD}])

        self.assertEqual("reject_duplicate_open", verdict["verdict"])
        self.assertEqual("open PR uses the same head branch", verdict["openDuplicates"][0]["reason"])

    def test_merged_pr_for_same_claim_short_circuits_as_already_delivered(self) -> None:
        verdict = self.preflight(
            pullRequests=[{"number": 1480, "state": "merged", "claimId": self.CLAIM_ID, "headBranch": self.HEAD}]
        )

        self.assertEqual("already_delivered", verdict["verdict"])
        self.assertFalse(verdict["allowed"])
        self.assertEqual([1480], [dup["number"] for dup in verdict["mergedDuplicates"]])
        self.assertIn("terminal queue publication", verdict["recommendedActions"][0])

    def test_merged_pr_on_same_head_without_claim_id_short_circuits(self) -> None:
        verdict = self.preflight(
            pullRequests=[{"number": 1481, "state": "closed", "merged": True, "branch": self.HEAD}]
        )

        self.assertEqual("already_delivered", verdict["verdict"])
        self.assertEqual("merged PR matches the same head branch", verdict["mergedDuplicates"][0]["reason"])

    def test_open_and_merged_prs_with_different_heads_and_claims_do_not_match(self) -> None:
        verdict = self.preflight(
            pullRequests=[
                {
                    "number": 1470,
                    "state": "open",
                    "claimId": "other-claim",
                    "issueName": "[EPIC_02][STORY_01][SUBSTORY_01] Other",
                    "headBranch": "codex/other",
                },
                {
                    "number": 1471,
                    "state": "merged",
                    "claimId": "third-claim",
                    "issueName": "[EPIC_03][STORY_01][SUBSTORY_01] Third",
                    "headBranch": "codex/third",
                },
            ]
        )

        self.assertEqual("allow", verdict["verdict"])
        self.assertEqual([], verdict["openDuplicates"])
        self.assertEqual([], verdict["mergedDuplicates"])

    def test_merged_same_head_under_different_claim_warns_but_allows(self) -> None:
        verdict = self.preflight(
            pullRequests=[{"number": 1482, "state": "merged", "claimId": "other-claim", "headBranch": self.HEAD}]
        )

        self.assertEqual("allow", verdict["verdict"])
        self.assertTrue(any("under a different claim id" in warning for warning in verdict["warnings"]))

    def test_explicit_replacement_of_open_duplicate_is_allowed(self) -> None:
        verdict = self.preflight(
            replaces=1490,
            pullRequests=[{"number": 1490, "state": "open", "claimId": self.CLAIM_ID, "headBranch": "codex/old-head"}],
        )

        self.assertEqual("allow_replacement", verdict["verdict"])
        self.assertTrue(verdict["allowed"])
        self.assertEqual(1490, verdict["replaces"])
        self.assertIn(
            "request explicit human approval before closing the superseded PR", verdict["recommendedActions"][0]
        )

    def test_replacement_covers_only_declared_pr_and_other_open_duplicate_still_rejects(self) -> None:
        verdict = self.preflight(
            replaces=1490,
            pullRequests=[
                {"number": 1490, "state": "open", "claimId": self.CLAIM_ID},
                {"number": 1493, "state": "open", "issueName": self.ISSUE},
            ],
        )

        self.assertEqual("reject_duplicate_open", verdict["verdict"])
        self.assertTrue(any("not covered by the declared replacement" in reason for reason in verdict["reasons"]))

    def test_replacement_target_missing_from_snapshot_cannot_verify(self) -> None:
        verdict = self.preflight(replaces=999, pullRequests=[])

        self.assertEqual("cannot_verify", verdict["verdict"])
        self.assertFalse(verdict["allowed"])
        self.assertIn("declared replacement PR #999 is not present in the snapshot; cannot verify", verdict["reasons"])

    def test_replacement_target_unrelated_to_claim_cannot_verify(self) -> None:
        verdict = self.preflight(
            replaces=1470,
            pullRequests=[
                {
                    "number": 1470,
                    "state": "open",
                    "claimId": "other",
                    "issueName": "[EPIC_02][STORY_01][SUBSTORY_01] Other",
                    "headBranch": "codex/other",
                }
            ],
        )

        self.assertEqual("cannot_verify", verdict["verdict"])
        self.assertIn(
            "declared replacement PR #1470 does not match this claim identity; cannot verify", verdict["reasons"]
        )

    def test_replacement_of_merged_duplicate_allows_re_delivery_with_warning(self) -> None:
        verdict = self.preflight(
            replaces=1480,
            pullRequests=[{"number": 1480, "state": "merged", "claimId": self.CLAIM_ID, "headBranch": self.HEAD}],
        )

        self.assertEqual("allow_replacement", verdict["verdict"])
        self.assertIn("explicit replacement of merged PR #1480 re-delivers already-merged work", verdict["warnings"])

    def test_title_collision_alone_is_advisory_not_rejecting(self) -> None:
        verdict = self.preflight(
            claim=self.claim(title="[EPIC_01][STORY_04][SUBSTORY_01] #623 Add preflight guard"),
            pullRequests=[
                {
                    "number": 1494,
                    "state": "open",
                    "title": "[EPIC_01][STORY_04][SUBSTORY_01]  #623 add Preflight guard",
                    "headBranch": "codex/unrelated",
                }
            ],
        )

        self.assertEqual("allow", verdict["verdict"])
        self.assertEqual([], verdict["openDuplicates"])
        self.assertIn("title collision with open PR #1494; titles are not authoritative identity", verdict["warnings"])

    def test_missing_claim_identity_fails_closed_to_cannot_verify(self) -> None:
        verdict = pr_review_audit.preflightVerdict(
            {"claim": {"owner": self.OWNER, "headBranch": self.HEAD}, "pullRequests": []}
        )

        self.assertEqual("cannot_verify", verdict["verdict"])
        self.assertFalse(verdict["allowed"])
        self.assertIn("claim identity is missing: issueName, claimId; cannot verify duplicates", verdict["reasons"])

    def test_missing_head_branch_is_warned_but_claim_matching_still_works(self) -> None:
        verdict = self.preflight(
            claim=self.claim(headBranch=""),
            pullRequests=[{"number": 1490, "state": "open", "claimId": self.CLAIM_ID}],
        )

        self.assertEqual("reject_duplicate_open", verdict["verdict"])
        self.assertTrue(any("head branch is missing" in warning for warning in verdict["warnings"]))

    def test_out_of_scope_files_produce_advisory_scope_warning(self) -> None:
        verdict = self.preflight(
            claim=self.claim(targetFiles=["scripts/pr_review_audit.py", "tests/test_pr_review_audit.py"]),
            candidate={"files": ["scripts/pr_review_audit.py", "src/core/CGameContext.cpp"]},
            pullRequests=[],
        )

        self.assertEqual("allow", verdict["verdict"])
        self.assertTrue(verdict["allowed"])
        self.assertTrue(
            any(
                "outside the claimed target files: src/core/CGameContext.cpp" in warning
                for warning in verdict["warnings"]
            )
        )

    def test_broad_diff_file_count_warns_without_rejecting(self) -> None:
        files = [f"src/generated/file_{index}.cpp" for index in range(pr_review_audit.BROAD_DIFF_FILE_LIMIT + 1)]
        verdict = self.preflight(candidate={"files": files}, pullRequests=[])

        self.assertEqual("allow", verdict["verdict"])
        self.assertTrue(any("broad diff with" in warning for warning in verdict["warnings"]))

    def test_workbook_in_candidate_diff_warns(self) -> None:
        verdict = self.preflight(candidate={"files": [pr_review_audit.WORKBOOK_PATH]}, pullRequests=[])

        self.assertEqual("allow", verdict["verdict"])
        self.assertTrue(any("touches the queue workbook" in warning for warning in verdict["warnings"]))

    def test_closed_unmerged_matching_pr_warns_but_allows(self) -> None:
        verdict = self.preflight(pullRequests=[{"number": 1483, "state": "closed", "claimId": self.CLAIM_ID}])

        self.assertEqual("allow", verdict["verdict"])
        self.assertIn(
            "closed unmerged PR #1483 previously matched this claim; verify it was superseded", verdict["warnings"]
        )

    def test_verdict_is_deterministic_and_side_effect_free(self) -> None:
        request = {
            "claim": self.claim(targetFiles=["scripts/pr_review_audit.py"]),
            "candidate": {"files": ["scripts/pr_review_audit.py", "docs/extra.md"]},
            "pullRequests": [
                {"number": 1490, "state": "open", "claimId": self.CLAIM_ID},
                {"number": 1480, "state": "merged", "claimId": self.CLAIM_ID, "headBranch": self.HEAD},
            ],
        }
        snapshotBefore = json.dumps(request, sort_keys=True)

        first = pr_review_audit.preflightVerdict(json.loads(snapshotBefore))
        second = pr_review_audit.preflightVerdict(json.loads(snapshotBefore))

        self.assertEqual(first, second)
        self.assertEqual(snapshotBefore, json.dumps(request, sort_keys=True))
        self.assertTrue(first["readOnly"])

    def test_cli_preflight_subcommand_reports_verdict_and_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            allowPath = Path(temp_dir) / "allow.json"
            allowPath.write_text(
                json.dumps({"claim": self.claim(), "pullRequests": []}),
                encoding="utf-8",
            )
            rejectPath = Path(temp_dir) / "reject.json"
            rejectPath.write_text(
                json.dumps(
                    {
                        "claim": self.claim(),
                        "pullRequests": [{"number": 1490, "state": "open", "claimId": self.CLAIM_ID}],
                    }
                ),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exitCode = pr_review_audit.main(["preflight", "--input", str(allowPath)])
            self.assertEqual(0, exitCode)
            self.assertEqual("allow", json.loads(stdout.getvalue())["verdict"])

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exitCode = pr_review_audit.main(["preflight", "--input", str(rejectPath)])
            self.assertEqual(1, exitCode)
            self.assertEqual("reject_duplicate_open", json.loads(stdout.getvalue())["verdict"])


if __name__ == "__main__":
    unittest.main()
