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


if __name__ == "__main__":
    unittest.main()
