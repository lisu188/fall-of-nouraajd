from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from scripts import heartbeat_scheduler
from scripts import issue_queue
from tests.test_issue_queue import IssueQueueTest


class HeartbeatSchedulerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = IssueQueueTest("test_claim_treats_target_file_overlap_as_advisory")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.workbook_path = self.fixture.workbook_path
        self.now = datetime(2026, 7, 13, 10, 0, tzinfo=timezone.utc)
        self.owner_prefix = "controller/ctrl-test"
        self.owner_a = f"{self.owner_prefix}/subagent-1"
        self.owner_b = f"{self.owner_prefix}/subagent-2"
        self.claim_a = "11111111-1111-4111-8111-111111111111"
        self.claim_b = "22222222-2222-4222-8222-222222222222"

    def active_row(
        self,
        issue_name: str,
        owner: str,
        claim_id: str,
        *,
        updated_minutes_ago: int,
        lease_minutes_from_now: int,
        progress: int = 10,
    ) -> list[object]:
        row = self.fixture.task_row(issue_name, "P0", None, "scripts/issue_queue.py")
        updated_at = self.now - timedelta(minutes=updated_minutes_ago)
        claimed_at = updated_at - timedelta(minutes=5)
        lease_until = self.now + timedelta(minutes=lease_minutes_from_now)
        return self.fixture.with_values(
            row,
            {
                "Status": issue_queue.STATUS_IN_PROGRESS,
                "Owner": owner,
                "Claim ID": claim_id,
                "Claimed At UTC": issue_queue.formatUtc(claimed_at),
                "Updated At UTC": issue_queue.formatUtc(updated_at),
                "Lease Until UTC": issue_queue.formatUtc(lease_until),
                "Progress %": progress,
                "Last Note": "Working",
                "Attempt": 1,
            },
        )

    def evidence(
        self,
        issue_name: str,
        owner: str,
        claim_id: str,
        *,
        reachable: bool = True,
        live: bool = True,
        observed_minutes_ago: int = 1,
        reference: str = "poll-1",
    ) -> dict[str, object]:
        return {
            "reference": reference,
            "observedAtUtc": issue_queue.formatUtc(self.now - timedelta(minutes=observed_minutes_ago)),
            "reachable": reachable,
            "live": live,
            "issueName": issue_name,
            "owner": owner,
            "claimId": claim_id,
        }

    def request(
        self,
        issue_name: str,
        owner: str,
        claim_id: str,
        *,
        progress: int = 50,
        note: str = "Verified progress",
        lease_minutes: int = 120,
        evidence: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return {
            "issueName": issue_name,
            "owner": owner,
            "claimId": claim_id,
            "progress": progress,
            "note": note,
            "leaseMinutes": lease_minutes,
            "evidence": evidence or self.evidence(issue_name, owner, claim_id),
        }

    def load_task(self, issue_name: str) -> issue_queue.TaskRecord:
        state = issue_queue.loadQueue(self.workbook_path)
        try:
            return issue_queue.taskByName(state, issue_name)
        finally:
            state.workbook.close()

    def test_schedule_states_use_canonical_deadlines(self) -> None:
        issue_due_soon = self.fixture.issue_a
        issue_due = self.fixture.issue_b
        issue_overdue = self.fixture.issue_c
        issue_recovery = self.fixture.issue_d
        self.fixture.create_workbook(
            [
                self.active_row(issue_due_soon, self.owner_a, self.claim_a, updated_minutes_ago=110, lease_minutes_from_now=60),
                self.active_row(issue_due, self.owner_b, self.claim_b, updated_minutes_ago=120, lease_minutes_from_now=60),
                self.active_row(
                    issue_overdue,
                    f"{self.owner_prefix}/subagent-3",
                    "33333333-3333-4333-8333-333333333333",
                    updated_minutes_ago=241,
                    lease_minutes_from_now=60,
                ),
                self.active_row(
                    issue_recovery,
                    f"{self.owner_prefix}/subagent-4",
                    "44444444-4444-4444-8444-444444444444",
                    updated_minutes_ago=241,
                    lease_minutes_from_now=-1,
                ),
            ]
        )
        state = issue_queue.loadQueue(self.workbook_path)
        try:
            schedules = {
                task.issueName: heartbeat_scheduler.heartbeatSchedule(task, self.now, warningMinutes=15)
                for task in state.tasks
            }
        finally:
            state.workbook.close()
        self.assertEqual(heartbeat_scheduler.STATE_DUE_SOON, schedules[issue_due_soon]["state"])
        self.assertEqual(10, schedules[issue_due_soon]["heartbeatDueInMinutes"])
        self.assertEqual(heartbeat_scheduler.STATE_DUE, schedules[issue_due]["state"])
        self.assertEqual(heartbeat_scheduler.STATE_OVERDUE, schedules[issue_overdue]["state"])
        self.assertEqual(heartbeat_scheduler.STATE_RECOVERY_REQUIRED, schedules[issue_recovery]["state"])

    def test_plan_reports_proposals_exclusions_and_recovery(self) -> None:
        issue_due = self.fixture.issue_a
        issue_not_due = self.fixture.issue_b
        issue_unreachable = self.fixture.issue_d
        claim_unreachable = "33333333-3333-4333-8333-333333333333"
        owner_unreachable = f"{self.owner_prefix}/subagent-3"
        self.fixture.create_workbook(
            [
                self.active_row(issue_due, self.owner_a, self.claim_a, updated_minutes_ago=120, lease_minutes_from_now=60),
                self.active_row(issue_not_due, self.owner_b, self.claim_b, updated_minutes_ago=30, lease_minutes_from_now=60),
                self.active_row(
                    issue_unreachable,
                    owner_unreachable,
                    claim_unreachable,
                    updated_minutes_ago=120,
                    lease_minutes_from_now=60,
                ),
            ]
        )
        payload = {
            "entries": [
                self.request(issue_due, self.owner_a, self.claim_a),
                self.request(issue_not_due, self.owner_b, self.claim_b),
                self.request(
                    issue_unreachable,
                    owner_unreachable,
                    claim_unreachable,
                    evidence=self.evidence(
                        issue_unreachable,
                        owner_unreachable,
                        claim_unreachable,
                        reachable=False,
                    ),
                ),
            ]
        }
        before = self.workbook_path.read_bytes()
        result = heartbeat_scheduler.planHeartbeatBatch(
            self.workbook_path,
            payload,
            now=self.now,
            warningMinutes=15,
            ownerPrefix=self.owner_prefix,
        )
        self.assertEqual(before, self.workbook_path.read_bytes())
        self.assertEqual([issue_due], [entry["request"]["issueName"] for entry in result["proposals"]])
        self.assertEqual([issue_not_due], [entry["request"]["issueName"] for entry in result["excluded"]])
        self.assertEqual([issue_unreachable], [entry["request"]["issueName"] for entry in result["recovery"]])
        self.assertFalse(result["applicable"])
        self.assertEqual(sorted([issue_due, issue_not_due, issue_unreachable]), result["publicationGuidance"]["affectedIssues"])

    def test_apply_batch_updates_all_rows_once_and_preserves_later_lease(self) -> None:
        issue_a = self.fixture.issue_a
        issue_b = self.fixture.issue_b
        self.fixture.create_workbook(
            [
                self.active_row(issue_a, self.owner_a, self.claim_a, updated_minutes_ago=120, lease_minutes_from_now=300),
                self.active_row(issue_b, self.owner_b, self.claim_b, updated_minutes_ago=130, lease_minutes_from_now=10),
            ]
        )
        payload = {
            "entries": [
                self.request(issue_a, self.owner_a, self.claim_a, progress=45, note="A", lease_minutes=60),
                self.request(issue_b, self.owner_b, self.claim_b, progress=70, note="B", lease_minutes=90),
            ]
        }
        with mock.patch.object(issue_queue, "atomicSave", wraps=issue_queue.atomicSave) as atomic_save:
            result = heartbeat_scheduler.applyHeartbeatBatch(self.workbook_path, payload, now=self.now)
        self.assertEqual(1, atomic_save.call_count)
        self.assertTrue(result["applied"])
        self.assertEqual(1, result["saveCount"])
        state = issue_queue.loadQueue(self.workbook_path)
        try:
            task_a = issue_queue.taskByName(state, issue_a)
            task_b = issue_queue.taskByName(state, issue_b)
            self.assertEqual(issue_queue.formatUtc(self.now), task_a.values["Updated At UTC"])
            self.assertEqual(issue_queue.formatUtc(self.now), task_b.values["Updated At UTC"])
            self.assertEqual(45, task_a.values["Progress %"])
            self.assertEqual(70, task_b.values["Progress %"])
            self.assertEqual("A", task_a.values["Last Note"])
            self.assertEqual("B", task_b.values["Last Note"])
            self.assertEqual(
                issue_queue.formatUtc(self.now + timedelta(minutes=300)),
                task_a.values["Lease Until UTC"],
            )
            self.assertEqual(
                issue_queue.formatUtc(self.now + timedelta(minutes=90)),
                task_b.values["Lease Until UTC"],
            )
        finally:
            state.workbook.close()

    def test_mixed_validity_batch_is_byte_preserving(self) -> None:
        issue_a = self.fixture.issue_a
        issue_b = self.fixture.issue_b
        self.fixture.create_workbook(
            [
                self.active_row(issue_a, self.owner_a, self.claim_a, updated_minutes_ago=120, lease_minutes_from_now=60),
                self.active_row(issue_b, self.owner_b, self.claim_b, updated_minutes_ago=120, lease_minutes_from_now=60),
            ]
        )
        invalid_evidence = self.evidence(issue_b, self.owner_b, self.claim_b)
        invalid_evidence["claimId"] = "wrong"
        payload = {
            "entries": [
                self.request(issue_a, self.owner_a, self.claim_a),
                self.request(issue_b, self.owner_b, self.claim_b, evidence=invalid_evidence),
            ]
        }
        before = self.workbook_path.read_bytes()
        with self.assertRaisesRegex(issue_queue.QueueError, "evidence claim ID mismatch"):
            heartbeat_scheduler.applyHeartbeatBatch(self.workbook_path, payload, now=self.now)
        self.assertEqual(before, self.workbook_path.read_bytes())

    def test_duplicate_entry_is_rejected_without_mutation(self) -> None:
        issue_a = self.fixture.issue_a
        self.fixture.create_workbook(
            [self.active_row(issue_a, self.owner_a, self.claim_a, updated_minutes_ago=120, lease_minutes_from_now=60)]
        )
        entry = self.request(issue_a, self.owner_a, self.claim_a)
        before = self.workbook_path.read_bytes()
        with self.assertRaisesRegex(issue_queue.QueueError, "duplicate issue"):
            heartbeat_scheduler.applyHeartbeatBatch(
                self.workbook_path,
                {"entries": [entry, dict(entry)]},
                now=self.now,
            )
        self.assertEqual(before, self.workbook_path.read_bytes())

    def test_reclaimable_claim_is_not_renewed(self) -> None:
        issue_a = self.fixture.issue_a
        self.fixture.create_workbook(
            [self.active_row(issue_a, self.owner_a, self.claim_a, updated_minutes_ago=241, lease_minutes_from_now=-1)]
        )
        before = self.workbook_path.read_bytes()
        with self.assertRaisesRegex(issue_queue.QueueError, "lease expired and heartbeat overdue"):
            heartbeat_scheduler.applyHeartbeatBatch(
                self.workbook_path,
                {"entries": [self.request(issue_a, self.owner_a, self.claim_a)]},
                now=self.now,
            )
        self.assertEqual(before, self.workbook_path.read_bytes())

    def test_expired_but_unreclaimed_claim_can_be_renewed_with_live_evidence(self) -> None:
        issue_a = self.fixture.issue_a
        self.fixture.create_workbook(
            [self.active_row(issue_a, self.owner_a, self.claim_a, updated_minutes_ago=30, lease_minutes_from_now=-1)]
        )
        result = heartbeat_scheduler.applyHeartbeatBatch(
            self.workbook_path,
            {"entries": [self.request(issue_a, self.owner_a, self.claim_a, lease_minutes=75)]},
            now=self.now,
        )
        self.assertTrue(result["applied"])
        task = self.load_task(issue_a)
        self.assertEqual(
            issue_queue.formatUtc(self.now + timedelta(minutes=75)),
            task.values["Lease Until UTC"],
        )

    def test_stale_worker_evidence_is_rejected(self) -> None:
        issue_a = self.fixture.issue_a
        self.fixture.create_workbook(
            [self.active_row(issue_a, self.owner_a, self.claim_a, updated_minutes_ago=120, lease_minutes_from_now=60)]
        )
        evidence = self.evidence(
            issue_a,
            self.owner_a,
            self.claim_a,
            observed_minutes_ago=issue_queue.DEFAULT_HEARTBEAT_INTERVAL_MINUTES + 1,
        )
        before = self.workbook_path.read_bytes()
        with self.assertRaisesRegex(issue_queue.QueueError, "evidence is stale"):
            heartbeat_scheduler.applyHeartbeatBatch(
                self.workbook_path,
                {"entries": [self.request(issue_a, self.owner_a, self.claim_a, evidence=evidence)]},
                now=self.now,
            )
        self.assertEqual(before, self.workbook_path.read_bytes())

    def test_save_failure_restores_original_bytes(self) -> None:
        issue_a = self.fixture.issue_a
        self.fixture.create_workbook(
            [self.active_row(issue_a, self.owner_a, self.claim_a, updated_minutes_ago=120, lease_minutes_from_now=60)]
        )
        before = self.workbook_path.read_bytes()

        def failing_save(_state: issue_queue.QueueState, workbook_path: Path) -> None:
            workbook_path.write_bytes(b"partial replacement")
            raise OSError("simulated save failure")

        with mock.patch.object(issue_queue, "atomicSave", side_effect=failing_save):
            with self.assertRaisesRegex(OSError, "simulated save failure"):
                heartbeat_scheduler.applyHeartbeatBatch(
                    self.workbook_path,
                    {"entries": [self.request(issue_a, self.owner_a, self.claim_a)]},
                    now=self.now,
                )
        self.assertEqual(before, self.workbook_path.read_bytes())

    def test_existing_single_heartbeat_api_remains_compatible(self) -> None:
        issue_a = self.fixture.issue_a
        current_now = issue_queue.utcNow()
        row = self.fixture.task_row(issue_a, "P0", None, "scripts/issue_queue.py")
        row = self.fixture.with_values(
            row,
            {
                "Status": issue_queue.STATUS_IN_PROGRESS,
                "Owner": self.owner_a,
                "Claim ID": self.claim_a,
                "Claimed At UTC": issue_queue.formatUtc(current_now - timedelta(minutes=10)),
                "Updated At UTC": issue_queue.formatUtc(current_now - timedelta(minutes=5)),
                "Lease Until UTC": issue_queue.formatUtc(current_now + timedelta(minutes=10)),
                "Progress %": 5,
                "Last Note": "Working",
                "Attempt": 1,
            },
        )
        self.fixture.create_workbook([row])
        result = issue_queue.heartbeatTask(
            self.workbook_path,
            issueName=issue_a,
            claimId=self.claim_a,
            owner=self.owner_a,
            progress=25,
            note="Still working",
            leaseMinutes=30,
        )
        self.assertEqual(25, result["Progress %"])
        self.assertEqual("Still working", result["Last Note"])
        self.assertIn("previousTiming", result)
        self.assertIn("resultingTiming", result)

    def test_apply_dry_run_cli_is_read_only(self) -> None:
        issue_a = self.fixture.issue_a
        self.fixture.create_workbook(
            [self.active_row(issue_a, self.owner_a, self.claim_a, updated_minutes_ago=120, lease_minutes_from_now=60)]
        )
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as stream:
            json.dump({"entries": [self.request(issue_a, self.owner_a, self.claim_a)]}, stream)
            request_path = Path(stream.name)
        self.addCleanup(lambda: request_path.unlink(missing_ok=True))
        before = self.workbook_path.read_bytes()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = heartbeat_scheduler.main(
                [
                    "apply",
                    "--dry-run",
                    "--workbook",
                    str(self.workbook_path),
                    "--request-file",
                    str(request_path),
                    "--now",
                    issue_queue.formatUtc(self.now),
                ]
            )
        self.assertEqual(0, exit_code)
        self.assertTrue(json.loads(stdout.getvalue())["applicable"])
        self.assertEqual(before, self.workbook_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
