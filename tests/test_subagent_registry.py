from __future__ import annotations

import contextlib
import io
import json
import os
import shlex
import subprocess
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

from scripts import subagent_registry

OWNER = "controller/ctrl-test-1-abc/subagent-1"
OTHER_OWNER = "controller/ctrl-test-1-abc/subagent-2"
CLAIM_ID = "claim-0001"


class SubagentRegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.registry_path = self.root / "registry" / "subagent_registry.json"
        self.worktree = self.root / "worktrees" / "impl-1"
        self.worktree.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def register_default(self, owner: str = OWNER, claim_id: str = CLAIM_ID, **overrides: object) -> dict:
        arguments = {
            "owner": owner,
            "role": subagent_registry.AgentRole.WORKER.value,
            "issue": "[EPIC_01][STORY_01][SUBSTORY_01]Test issue",
            "claimId": claim_id,
            "worktree": str(self.worktree),
            "branch": "codex/test-branch",
            "validationCommand": "python3 -m unittest tests.test_subagent_registry",
        }
        arguments.update(overrides)
        return subagent_registry.registerAgent(self.registry_path, **arguments)

    def load_records(self) -> list[subagent_registry.AgentRecord]:
        return subagent_registry.loadRegistry(self.registry_path).records

    def init_git_repo(self, branch_names: list[str]) -> Path:
        repo = self.root / "repo"
        repo.mkdir()
        env_config = ["-c", "user.email=test@example.com", "-c", "user.name=Test"]
        subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
        (repo / "file.txt").write_text("content\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "file.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), *env_config, "commit", "--quiet", "-m", "init"], check=True)
        for branch in branch_names:
            subprocess.run(["git", "-C", str(repo), "branch", branch], check=True)
        return repo

    def test_register_creates_record_before_slot_consumption(self) -> None:
        payload = self.register_default()

        self.assertEqual(payload["owner"], OWNER)
        self.assertEqual(payload["status"], subagent_registry.LifecycleStatus.REGISTERED.value)
        self.assertEqual(payload["claimId"], CLAIM_ID)
        self.assertTrue(payload["consumesCapacity"])
        self.assertEqual(payload["spawnedAtUtc"], payload["lastSeenUtc"])

        listing = subagent_registry.listAgents(self.registry_path)
        self.assertEqual(listing["summary"]["activeCount"], 1)
        self.assertEqual(listing["summary"]["byStatus"]["REGISTERED"], 1)

    def test_schema_validation_rejects_invalid_documents(self) -> None:
        self.register_default()
        valid_payload = json.loads(self.registry_path.read_text(encoding="utf-8"))

        wrong_version = dict(valid_payload, schemaVersion=99)
        self.assertTrue(any("schemaVersion" in e for e in subagent_registry.validateRegistryPayload(wrong_version)))

        bad_enum = json.loads(json.dumps(valid_payload))
        bad_enum["records"][0]["status"] = "SLEEPING"
        self.assertTrue(any("status" in e for e in subagent_registry.validateRegistryPayload(bad_enum)))

        bad_timestamp = json.loads(json.dumps(valid_payload))
        bad_timestamp["records"][0]["lastSeenUtc"] = "not-a-time"
        self.assertTrue(any("lastSeenUtc" in e for e in subagent_registry.validateRegistryPayload(bad_timestamp)))

        duplicate_id = json.loads(json.dumps(valid_payload))
        duplicate_id["records"].append(json.loads(json.dumps(duplicate_id["records"][0])))
        errors = subagent_registry.validateRegistryPayload(duplicate_id)
        self.assertTrue(any("duplicate registrationId" in e for e in errors))
        self.assertTrue(any("duplicate active registration for owner" in e for e in errors))

        missing_field = json.loads(json.dumps(valid_payload))
        del missing_field["records"][0]["worktree"]
        missing_errors = subagent_registry.validateRegistryPayload(missing_field)
        self.assertTrue(any("missing field 'worktree'" in e for e in missing_errors))

        self.registry_path.write_text(json.dumps(wrong_version), encoding="utf-8")
        with self.assertRaises(subagent_registry.RegistryError):
            subagent_registry.loadRegistry(self.registry_path)

        self.assertEqual(subagent_registry.validateRegistryPayload(valid_payload), [])

    def test_atomic_persistence_partial_failure_leaves_file_unchanged(self) -> None:
        self.register_default()
        original_bytes = self.registry_path.read_bytes()

        with mock.patch.object(subagent_registry.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.register_default(owner=OTHER_OWNER, claim_id="claim-0002")

        self.assertEqual(self.registry_path.read_bytes(), original_bytes)
        leftovers = [p for p in self.registry_path.parent.iterdir() if p.suffix == ".tmp"]
        self.assertEqual(leftovers, [])
        self.assertEqual(len(self.load_records()), 1)

    def test_lifecycle_transitions(self) -> None:
        registered = self.register_default()
        registration_id = registered["registrationId"]

        live = subagent_registry.reportAgent(
            self.registry_path,
            {"owner": OWNER, "lastSeenUtc": subagent_registry.formatUtc(subagent_registry.utcNow())},
        )
        self.assertEqual(live["status"], "LIVE")

        marked = subagent_registry.markAgent(
            self.registry_path, "UNREACHABLE", registrationId=registration_id, reason="poll timed out"
        )
        self.assertEqual(marked["status"], "UNREACHABLE")
        self.assertEqual(marked["lastNote"], "poll timed out")

        revived = subagent_registry.reportAgent(
            self.registry_path,
            {"owner": OWNER, "lastSeenUtc": subagent_registry.formatUtc(subagent_registry.utcNow())},
        )
        self.assertEqual(revived["status"], "LIVE")

        finalized = subagent_registry.finalizeAgent(
            self.registry_path, registrationId=registration_id, exitResult="COMPLETE"
        )
        self.assertEqual(finalized["status"], "FINALIZED")
        self.assertFalse(finalized["consumesCapacity"])

        with self.assertRaises(subagent_registry.RegistryError):
            subagent_registry.finalizeAgent(self.registry_path, registrationId=registration_id)
        with self.assertRaises(subagent_registry.RegistryError):
            subagent_registry.markAgent(self.registry_path, "ORPHANED", registrationId=registration_id)
        with self.assertRaises(subagent_registry.RegistryError):
            subagent_registry.reportAgent(
                self.registry_path,
                {"owner": OWNER, "lastSeenUtc": subagent_registry.formatUtc(subagent_registry.utcNow())},
                registrationId=registration_id,
            )

    def test_finalized_agents_release_capacity(self) -> None:
        first = self.register_default()
        self.register_default(owner=OTHER_OWNER, claim_id="claim-0002")
        self.assertEqual(subagent_registry.listAgents(self.registry_path)["summary"]["activeCount"], 2)

        subagent_registry.finalizeAgent(self.registry_path, registrationId=first["registrationId"])

        listing = subagent_registry.listAgents(self.registry_path)
        self.assertEqual(listing["summary"]["activeCount"], 1)
        self.assertEqual(listing["summary"]["finalizedCount"], 1)
        active_only = subagent_registry.listAgents(self.registry_path, includeFinalized=False)
        self.assertEqual([record["owner"] for record in active_only["records"]], [OTHER_OWNER])

    def test_duplicate_registration_rejected(self) -> None:
        registered = self.register_default()

        with self.assertRaisesRegex(subagent_registry.RegistryError, "Duplicate registration: owner"):
            self.register_default()
        with self.assertRaisesRegex(subagent_registry.RegistryError, "Duplicate registration: claim"):
            self.register_default(owner=OTHER_OWNER)
        self.assertEqual(len(self.load_records()), 1)

        subagent_registry.finalizeAgent(self.registry_path, registrationId=registered["registrationId"])
        reused = self.register_default()
        self.assertNotEqual(reused["registrationId"], registered["registrationId"])
        self.assertEqual(len(self.load_records()), 2)

    def test_last_seen_only_advances_from_schema_valid_evidence(self) -> None:
        registered = self.register_default()
        base_last_seen = registered["lastSeenUtc"]

        stale_time = subagent_registry.parseUtc(base_last_seen) - timedelta(minutes=30)
        with self.assertRaisesRegex(subagent_registry.RegistryError, "Stale report evidence"):
            subagent_registry.reportAgent(
                self.registry_path, {"owner": OWNER, "lastSeenUtc": subagent_registry.formatUtc(stale_time)}
            )

        fresh = subagent_registry.formatUtc(subagent_registry.utcNow() + timedelta(minutes=1))
        with self.assertRaisesRegex(subagent_registry.RegistryError, "unknown key"):
            subagent_registry.reportAgent(self.registry_path, {"owner": OWNER, "lastSeenUtc": fresh, "surprise": "x"})
        with self.assertRaisesRegex(subagent_registry.RegistryError, "missing required key"):
            subagent_registry.reportAgent(self.registry_path, {"owner": OWNER})
        with self.assertRaisesRegex(subagent_registry.RegistryError, "phase"):
            subagent_registry.reportAgent(
                self.registry_path, {"owner": OWNER, "lastSeenUtc": fresh, "phase": "NAPPING"}
            )
        with self.assertRaisesRegex(subagent_registry.RegistryError, "does not match registered claim"):
            subagent_registry.reportAgent(
                self.registry_path, {"owner": OWNER, "lastSeenUtc": fresh, "claimId": "claim-wrong"}
            )

        record = self.load_records()[0]
        self.assertEqual(record.lastSeenUtc, base_last_seen)
        self.assertEqual(record.status, "REGISTERED")

        marked = subagent_registry.markAgent(self.registry_path, "UNREACHABLE", owner=OWNER, reason="no poll")
        self.assertEqual(marked["lastSeenUtc"], base_last_seen)

        updated = subagent_registry.reportAgent(
            self.registry_path,
            {
                "owner": OWNER,
                "claimId": CLAIM_ID,
                "lastSeenUtc": fresh,
                "phase": "IMPLEMENTATION",
                "validationCommand": "python3 test.py --suite fast",
                "changedFiles": ["scripts/subagent_registry.py"],
                "note": "implementation started",
            },
        )
        self.assertEqual(updated["lastSeenUtc"], fresh)
        self.assertEqual(updated["phase"], "IMPLEMENTATION")
        self.assertEqual(updated["changedFiles"], ["scripts/subagent_registry.py"])
        self.assertEqual(updated["status"], "LIVE")

    def test_restart_reconstructs_live_finalized_and_orphaned_workers(self) -> None:
        live = self.register_default()
        finalized = self.register_default(owner=OTHER_OWNER, claim_id="claim-0002")
        orphan_owner = "controller/ctrl-test-1-abc/subagent-3"
        orphaned = self.register_default(owner=orphan_owner, claim_id="claim-0003")

        subagent_registry.reportAgent(
            self.registry_path,
            {"owner": OWNER, "lastSeenUtc": subagent_registry.formatUtc(subagent_registry.utcNow())},
        )
        subagent_registry.finalizeAgent(self.registry_path, registrationId=finalized["registrationId"])
        subagent_registry.markAgent(self.registry_path, "ORPHANED", registrationId=orphaned["registrationId"])

        # A restarted controller only has the registry file path; reconstruct from disk.
        listing = subagent_registry.listAgents(self.registry_path)
        by_owner = {record["owner"]: record for record in listing["records"]}
        self.assertEqual(by_owner[OWNER]["status"], "LIVE")
        self.assertEqual(by_owner[OTHER_OWNER]["status"], "FINALIZED")
        self.assertEqual(by_owner[orphan_owner]["status"], "ORPHANED")
        self.assertEqual(listing["summary"]["activeCount"], 2)
        self.assertEqual(by_owner[OWNER]["registrationId"], live["registrationId"])

    def test_sweep_recommends_orphaned_for_missing_worktree(self) -> None:
        repo = self.init_git_repo(["codex/test-branch"])
        healthy = self.register_default()
        missing_owner = "controller/ctrl-test-1-abc/subagent-3"
        missing = self.register_default(
            owner=missing_owner, claim_id="claim-0003", worktree=str(self.root / "worktrees" / "gone")
        )

        result = subagent_registry.sweepRegistry(self.registry_path, repoRoot=repo)

        findings = {finding["owner"]: finding for finding in result["findings"]}
        self.assertTrue(result["readOnly"])
        self.assertEqual(findings[OWNER]["recommendedStatus"], "NONE")
        self.assertTrue(findings[OWNER]["checks"]["worktreeExists"])
        self.assertTrue(findings[OWNER]["checks"]["branchExists"])
        self.assertEqual(findings[missing_owner]["recommendedStatus"], "ORPHANED")
        self.assertFalse(findings[missing_owner]["checks"]["worktreeExists"])
        self.assertIn("mark", findings[missing_owner]["recommendedCommand"])
        self.assertIn(missing["registrationId"], findings[missing_owner]["recommendedCommand"])
        self.assertEqual(len(result["recommendations"]), 1)
        del healthy

    def test_sweep_recommended_command_shell_quotes_untrusted_fields(self) -> None:
        # A subagent registers its own branch/worktree, so those strings are
        # untrusted. They flow into the operator-facing recommendedCommand; if it
        # is not shell-quoted, pasting it runs $(...)/`...`/; embedded by an
        # attacker. The command must be a single safely-quoted argv instead.
        repo = self.init_git_repo([])
        malicious_branch = "codex/x$(touch pwned)`id`; rm -rf ."
        record = self.register_default(branch=malicious_branch)

        finding = subagent_registry.sweepRegistry(self.registry_path, repoRoot=repo)["findings"][0]
        command = finding["recommendedCommand"]

        # shlex.split tokenizes exactly as a POSIX shell would: the untrusted
        # branch survives only as one inert --reason argument and never splits
        # into active words like "rm"/"-rf" or a substitution token.
        argv = shlex.split(command)
        self.assertEqual(argv[:3], ["python3", "scripts/subagent_registry.py", "mark"])
        self.assertEqual(argv[argv.index("--registration-id") + 1], record["registrationId"])
        self.assertIn(malicious_branch, argv[argv.index("--reason") + 1])
        self.assertNotIn("rm", argv)
        self.assertNotIn("-rf", argv)
        self.assertNotIn("$(touch", "".join(token for token in argv if token != argv[argv.index("--reason") + 1]))

    def test_sweep_recommends_unreachable_for_missing_branch_or_stale_last_seen(self) -> None:
        repo = self.init_git_repo([])
        self.register_default(branch="codex/branch-that-does-not-exist")

        result = subagent_registry.sweepRegistry(self.registry_path, repoRoot=repo)
        finding = result["findings"][0]
        self.assertEqual(finding["recommendedStatus"], "UNREACHABLE")
        self.assertFalse(finding["checks"]["branchExists"])

        stale_now = subagent_registry.utcNow() + timedelta(minutes=500)
        repo_with_branch = repo
        subprocess.run(["git", "-C", str(repo_with_branch), "branch", "codex/branch-that-does-not-exist"], check=True)
        stale_result = subagent_registry.sweepRegistry(self.registry_path, repoRoot=repo, now=stale_now)
        stale_finding = stale_result["findings"][0]
        self.assertEqual(stale_finding["recommendedStatus"], "UNREACHABLE")
        self.assertTrue(any("minutes old" in reason for reason in stale_finding["reasons"]))

    def test_sweep_uses_workbook_claim_evidence(self) -> None:
        repo = self.init_git_repo(["codex/test-branch"])
        self.register_default()

        matched = subagent_registry.sweepRegistry(
            self.registry_path,
            repoRoot=repo,
            workbookClaims={CLAIM_ID: {"issue": "x", "owner": OWNER, "status": "IN_PROGRESS"}},
        )
        self.assertEqual(matched["findings"][0]["checks"]["claimEvidence"], "MATCH")

        missing = subagent_registry.sweepRegistry(self.registry_path, repoRoot=repo, workbookClaims={})
        self.assertEqual(missing["findings"][0]["checks"]["claimEvidence"], "MISSING")
        self.assertTrue(any("claim evidence is missing" in reason for reason in missing["findings"][0]["reasons"]))

        reclaimed = subagent_registry.sweepRegistry(
            self.registry_path,
            repoRoot=repo,
            workbookClaims={CLAIM_ID: {"issue": "x", "owner": "someone-else", "status": "IN_PROGRESS"}},
        )
        self.assertEqual(reclaimed["findings"][0]["checks"]["claimEvidence"], "OWNER_MISMATCH")

        done = subagent_registry.sweepRegistry(
            self.registry_path,
            repoRoot=repo,
            workbookClaims={CLAIM_ID: {"issue": "x", "owner": OWNER, "status": "DONE"}},
        )
        self.assertEqual(done["findings"][0]["checks"]["claimEvidence"], "NOT_IN_PROGRESS")

    def test_load_workbook_claims_uses_read_only_issue_queue_records(self) -> None:
        from scripts import issue_queue

        task = issue_queue.TaskRecord(
            row=2,
            values={
                "Issue Name": "[EPIC_01][STORY_01][SUBSTORY_01]Test issue",
                "Status": "IN_PROGRESS",
                "Owner": OWNER,
                "Claim ID": CLAIM_ID,
            },
        )
        unclaimed = issue_queue.TaskRecord(row=3, values={"Issue Name": "x", "Status": "NOT_STARTED"})
        fake_state = mock.Mock(tasks=[task, unclaimed])
        with mock.patch.object(subagent_registry.issue_queue, "loadQueue", return_value=fake_state) as load_queue:
            claims = subagent_registry.loadWorkbookClaims(Path("workbook.xlsx"))

        load_queue.assert_called_once_with(Path("workbook.xlsx"), writable=False)
        fake_state.workbook.close.assert_called_once_with()
        expected_claim = {
            "issue": "[EPIC_01][STORY_01][SUBSTORY_01]Test issue",
            "owner": OWNER,
            "status": "IN_PROGRESS",
        }
        self.assertEqual(claims, {CLAIM_ID: expected_claim})

    def test_sweep_is_read_only_and_byte_stable(self) -> None:
        repo = self.init_git_repo([])
        self.register_default(worktree=str(self.root / "worktrees" / "gone"), branch="codex/missing-branch")
        before_bytes = self.registry_path.read_bytes()

        result = subagent_registry.sweepRegistry(self.registry_path, repoRoot=repo)
        self.assertEqual(result["findings"][0]["recommendedStatus"], "ORPHANED")
        self.assertEqual(self.registry_path.read_bytes(), before_bytes)

        # Repeat sweeps stay byte-stable and never create the registry file if it is absent.
        subagent_registry.sweepRegistry(self.registry_path, repoRoot=repo)
        self.assertEqual(self.registry_path.read_bytes(), before_bytes)
        empty_registry = self.root / "never-created" / "registry.json"
        empty_result = subagent_registry.sweepRegistry(empty_registry, repoRoot=repo)
        self.assertEqual(empty_result["findings"], [])
        self.assertFalse(empty_registry.exists())

        record = self.load_records()[0]
        self.assertEqual(record.status, "REGISTERED", "sweep must not apply lifecycle transitions itself")

    def test_finalized_retention_is_deterministic(self) -> None:
        base_now = subagent_registry.utcNow()
        kept_ids: list[str] = []
        for index in range(4):
            owner = f"controller/ctrl-test-1-abc/subagent-{index + 1}"
            registered = subagent_registry.registerAgent(
                self.registry_path, owner=owner, role="WORKER", claimId=f"claim-{index}"
            )
            payload = subagent_registry.finalizeAgent(
                self.registry_path,
                registrationId=registered["registrationId"],
                retainFinalized=2,
                now=base_now + timedelta(minutes=index),
            )
            kept_ids.append(registered["registrationId"])
            del payload

        records = self.load_records()
        self.assertEqual(len(records), 2)
        self.assertEqual(
            sorted(record.registrationId for record in records),
            sorted(kept_ids[-2:]),
            "retention must keep the newest finalized records by finalizedAtUtc",
        )
        with self.assertRaises(subagent_registry.RegistryError):
            subagent_registry.finalizeAgent(self.registry_path, registrationId=kept_ids[-1], retainFinalized=-1)

    def test_cli_round_trip(self) -> None:
        repo = self.init_git_repo(["codex/test-branch"])
        registry_arg = ["--registry", str(self.registry_path)]

        def run_cli(arguments: list[str]) -> tuple[int, str]:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = subagent_registry.main(arguments)
            return code, stdout.getvalue()

        code, output = run_cli(
            [
                "register",
                *registry_arg,
                "--owner",
                OWNER,
                "--role",
                "WORKER",
                "--issue",
                "[EPIC_01][STORY_01][SUBSTORY_01]Test issue",
                "--claim-id",
                CLAIM_ID,
                "--worktree",
                str(self.worktree),
                "--branch",
                "codex/test-branch",
            ]
        )
        self.assertEqual(code, 0)
        registration_id = json.loads(output)["registrationId"]

        report_payload = json.dumps(
            {"owner": OWNER, "lastSeenUtc": subagent_registry.formatUtc(subagent_registry.utcNow())}
        )
        code, output = run_cli(["report", *registry_arg, "--payload", report_payload])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["status"], "LIVE")

        code, output = run_cli(["sweep", *registry_arg, "--repo", str(repo)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["recommendations"], [])

        code, output = run_cli(["validate", *registry_arg])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["errors"], [])

        code, output = run_cli(["finalize", *registry_arg, "--registration-id", registration_id])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["status"], "FINALIZED")

        code, output = run_cli(["list", *registry_arg])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["summary"]["activeCount"], 0)

        # Duplicate-style CLI failures exit with status 2 and leave the registry parseable.
        code, _ = run_cli(["finalize", *registry_arg, "--registration-id", registration_id])
        self.assertEqual(code, 2)
        self.assertEqual(subagent_registry.validateRegistryFile(self.registry_path)["errors"], [])

    def test_registry_path_resolution(self) -> None:
        explicit = subagent_registry.resolveRegistryPath(self.registry_path)
        self.assertEqual(explicit, self.registry_path.resolve())

        env_path = self.root / "env-registry.json"
        with mock.patch.dict(os.environ, {subagent_registry.ENV_REGISTRY_FILE: str(env_path)}):
            self.assertEqual(subagent_registry.resolveRegistryPath(None), env_path.resolve())

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(subagent_registry.ENV_REGISTRY_FILE, None)
            resolved_default = subagent_registry.resolveRegistryPath(None)
        self.assertEqual(resolved_default.name, subagent_registry.DEFAULT_REGISTRY_FILENAME)


if __name__ == "__main__":
    unittest.main()
