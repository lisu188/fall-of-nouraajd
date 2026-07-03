from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from scripts import controller_reconciler as reconciler

ISSUE = "[EPIC_01][STORY_01][SUBSTORY_01] #614 Add durable controller transition reconciler"


def rollup(name: str, status: str, conclusion: str | None = None) -> list[dict[str, object]]:
    check: dict[str, object] = {"name": name, "status": status}
    if conclusion is not None:
        check["conclusion"] = conclusion
    return [check]


def evidence(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "issueName": ISSUE,
        "claimId": "claim-1",
        "owner": "controller/ctrl-1/subagent-1",
        "queue": {"status": "IN_PROGRESS", "issueName": ISSUE, "claimId": "claim-1"},
    }
    base.update(overrides)
    return base


class ControllerReconcilerStateMatrixTest(unittest.TestCase):
    def assertState(self, ev: dict[str, object], state: str, action: str) -> reconciler.ControllerSnapshot:
        snapshot = reconciler.reconcile(ev)
        self.assertEqual(state, snapshot.state)
        self.assertEqual(action, snapshot.nextAction)
        return snapshot

    def test_claim_selected_recommends_worktree(self) -> None:
        self.assertState(evidence(), reconciler.STATE_CLAIM_SELECTED, reconciler.ACTION_CREATE_WORKTREE)

    def test_worktree_ready_recommends_worker(self) -> None:
        self.assertState(
            evidence(worktreeReady=True), reconciler.STATE_WORKTREE_READY, reconciler.ACTION_RUN_WORKER
        )

    def test_worker_running_recommends_open_pr(self) -> None:
        self.assertState(
            evidence(workerRunning=True),
            reconciler.STATE_WORKER_RUNNING,
            reconciler.ACTION_OPEN_IMPLEMENTATION_PR,
        )

    def test_ci_pending_waits(self) -> None:
        ev = evidence(
            implementationPr={
                "claimId": "claim-1",
                "issueName": ISSUE,
                "statusCheckRollup": rollup("linux", "IN_PROGRESS"),
            }
        )
        self.assertState(ev, reconciler.STATE_CI_PENDING, reconciler.ACTION_WAIT_FOR_CI)

    def test_ci_failed_fixes(self) -> None:
        ev = evidence(
            implementationPr={
                "claimId": "claim-1",
                "issueName": ISSUE,
                "statusCheckRollup": rollup("linux", "COMPLETED", "FAILURE"),
            }
        )
        self.assertState(ev, reconciler.STATE_CI_FAILED, reconciler.ACTION_FIX_CI)

    def test_ci_passed_clean_merges(self) -> None:
        ev = evidence(
            implementationPr={
                "claimId": "claim-1",
                "issueName": ISSUE,
                "mergeableState": "clean",
                "statusCheckRollup": rollup("linux", "COMPLETED", "SUCCESS"),
            }
        )
        snapshot = self.assertState(ev, reconciler.STATE_CI_PASSED, reconciler.ACTION_MERGE_IMPLEMENTATION)
        self.assertEqual("claim-1:merge_implementation", snapshot.idempotencyKey)

    def test_ci_passed_but_dirty_does_not_merge(self) -> None:
        ev = evidence(
            implementationPr={
                "claimId": "claim-1",
                "issueName": ISSUE,
                "mergeableState": "dirty",
                "statusCheckRollup": rollup("linux", "COMPLETED", "SUCCESS"),
            }
        )
        self.assertState(ev, reconciler.STATE_CI_PASSED, reconciler.ACTION_FIX_CI)

    def test_implementation_merged_marks_done(self) -> None:
        ev = evidence(implementationPr={"claimId": "claim-1", "issueName": ISSUE, "merged": True})
        self.assertState(ev, reconciler.STATE_IMPLEMENTATION_MERGED, reconciler.ACTION_MARK_DONE)

    def test_terminal_pr_open_waits(self) -> None:
        ev = evidence(
            implementationPr={"claimId": "claim-1", "issueName": ISSUE, "merged": True},
            terminalPr={"claimId": "claim-1", "issueName": ISSUE, "merged": False},
        )
        self.assertState(ev, reconciler.STATE_TERMINAL_PR_OPEN, reconciler.ACTION_WAIT_FOR_CI)

    def test_done_is_terminal(self) -> None:
        ev = evidence(queue={"status": "DONE", "issueName": ISSUE})
        self.assertState(ev, reconciler.STATE_DONE, reconciler.ACTION_NONE)

    def test_blocked_is_terminal(self) -> None:
        ev = evidence(queue={"status": "BLOCKED", "issueName": ISSUE})
        self.assertState(ev, reconciler.STATE_BLOCKED, reconciler.ACTION_NONE)

    def test_stale_claim_requires_recovery(self) -> None:
        ev = evidence(queue={"status": "IN_PROGRESS", "issueName": ISSUE, "stale": True})
        self.assertState(ev, reconciler.STATE_RECOVERY_REQUIRED, reconciler.ACTION_RECOVERY_REQUIRED)


class ControllerReconcilerContradictionTest(unittest.TestCase):
    def test_done_row_with_open_implementation_pr_is_recovery(self) -> None:
        ev = evidence(
            queue={"status": "DONE", "issueName": ISSUE},
            implementationPr={"claimId": "claim-1", "issueName": ISSUE, "merged": False},
        )
        snapshot = reconciler.reconcile(ev)
        self.assertEqual(reconciler.STATE_RECOVERY_REQUIRED, snapshot.state)
        self.assertTrue(any("DONE" in c for c in snapshot.contradictions))

    def test_merged_implementation_without_claim_is_recovery(self) -> None:
        ev = evidence(
            queue={"status": "NOT_STARTED", "issueName": ISSUE},
            implementationPr={"claimId": "claim-1", "issueName": ISSUE, "merged": True},
        )
        snapshot = reconciler.reconcile(ev)
        self.assertEqual(reconciler.STATE_RECOVERY_REQUIRED, snapshot.state)

    def test_pr_claim_id_mismatch_is_recovery(self) -> None:
        ev = evidence(implementationPr={"claimId": "other-claim", "issueName": ISSUE})
        snapshot = reconciler.reconcile(ev)
        self.assertEqual(reconciler.STATE_RECOVERY_REQUIRED, snapshot.state)
        self.assertTrue(any("claim id mismatch" in c for c in snapshot.contradictions))

    def test_queue_issue_mismatch_is_recovery(self) -> None:
        ev = evidence(queue={"status": "IN_PROGRESS", "issueName": "[EPIC_09][STORY_09][SUBSTORY_09] other"})
        snapshot = reconciler.reconcile(ev)
        self.assertEqual(reconciler.STATE_RECOVERY_REQUIRED, snapshot.state)

    def test_write_action_without_claim_id_refuses(self) -> None:
        ev = {"issueName": ISSUE, "queue": {"status": "IN_PROGRESS", "issueName": ISSUE}}
        snapshot = reconciler.reconcile(ev)
        # A worktree write with no claim id cannot be made idempotent -> recovery.
        self.assertEqual(reconciler.STATE_RECOVERY_REQUIRED, snapshot.state)
        self.assertIsNone(snapshot.idempotencyKey)


class ControllerReconcilerIdempotencyTest(unittest.TestCase):
    def test_write_actions_carry_a_stable_key_and_reads_do_not(self) -> None:
        write = reconciler.reconcile(evidence(worktreeReady=True))
        self.assertEqual("claim-1:run_worker", write.idempotencyKey)
        wait = reconciler.reconcile(
            evidence(
                implementationPr={
                    "claimId": "claim-1",
                    "issueName": ISSUE,
                    "statusCheckRollup": rollup("linux", "IN_PROGRESS"),
                }
            )
        )
        self.assertIsNone(wait.idempotencyKey)

    def test_duplicate_evidence_yields_identical_snapshot(self) -> None:
        ev = evidence(worktreeReady=True)
        first = reconciler.reconcile(ev)
        second = reconciler.reconcile(json.loads(json.dumps(ev)))
        self.assertEqual(first.toPayload(), second.toPayload())

    def test_idempotency_key_requires_claim(self) -> None:
        self.assertEqual("c9:mark_done", reconciler.idempotencyKey("c9", "mark_done"))
        with self.assertRaises(reconciler.ReconcilerError):
            reconciler.idempotencyKey("", "mark_done")


class ControllerReconcilerCliTest(unittest.TestCase):
    def test_malformed_evidence_raises(self) -> None:
        with self.assertRaises(reconciler.ReconcilerError):
            reconciler.buildFacts([])  # type: ignore[arg-type]
        with self.assertRaises(reconciler.ReconcilerError):
            reconciler.buildFacts({"claimId": "x"})  # missing issueName

    def test_next_action_command_emits_action_and_key(self) -> None:
        stdout = io.StringIO()
        payload = json.dumps(evidence(worktreeReady=True))
        with redirect_stdout(stdout):
            with mock.patch("sys.stdin", io.StringIO(payload)):
                exit_code = reconciler.main(["next-action"])
        self.assertEqual(0, exit_code)
        result = json.loads(stdout.getvalue())
        self.assertEqual(reconciler.ACTION_RUN_WORKER, result["nextAction"])
        self.assertEqual("claim-1:run_worker", result["idempotencyKey"])

    def test_recovery_exit_code_is_one(self) -> None:
        stdout = io.StringIO()
        payload = json.dumps(evidence(queue={"status": "IN_PROGRESS", "issueName": ISSUE, "stale": True}))
        with redirect_stdout(stdout):
            with mock.patch("sys.stdin", io.StringIO(payload)):
                exit_code = reconciler.main(["reconcile"])
        self.assertEqual(1, exit_code)


if __name__ == "__main__":
    unittest.main()
