from __future__ import annotations

import io
import json
import multiprocessing
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import issue_queue, workflow_observations

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "a" * 40


def record_worker(root: str, output: multiprocessing.Queue) -> None:
    stdout = io.StringIO()
    args = [
        "record",
        "--root",
        root,
        "--controller-id",
        "ctrl/concurrent",
        "--role",
        "controller",
        "--source-commit",
        SOURCE_COMMIT,
        "--category",
        "ci",
        "--severity",
        "medium",
        "--phase",
        "validation",
        "--summary",
        "Repeated CI check did not surface actionable failure",
        "--details",
        "The same GitHub Actions job failed without a durable observation.",
        "--impact",
        "Controllers spend time rediscovering the same CI failure.",
        "--evidence-json",
        '{"command": "python3 scripts/poll_pr_checks.py 123 --check linux", "result": "failure"}',
        "--affected-path",
        "scripts/poll_pr_checks.py",
        "--fingerprint",
        "ci linux failure missing durable observation",
    ]
    with redirect_stdout(stdout):
        exitCode = workflow_observations.main(args)
    output.put((exitCode, stdout.getvalue()))


class WorkflowObservationsTest(unittest.TestCase):
    def run_git(self, repo: Path, args: list[str]) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def run_cli(self, args: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exitCode = workflow_observations.main(args)
        return exitCode, stdout.getvalue(), stderr.getvalue()

    def observation_payload(
        self,
        observation_id: str,
        *,
        created_at: str = "2026-06-20T15:00:00Z",
        severity: str = "medium",
        category: str = "ci",
        phase: str = "validation",
        fingerprint: str = "ci linux failure",
        affected_paths: list[str] | None = None,
    ) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "id": observation_id,
            "createdAtUtc": created_at,
            "controllerId": "ctrl-test",
            "role": "controller",
            "sourceCommit": SOURCE_COMMIT,
            "category": category,
            "severity": severity,
            "phase": phase,
            "summary": "Linux CI failed without durable evidence",
            "details": "A controller had to rediscover the same failing GitHub Actions result.",
            "impact": "Repeated manual inspection slowed recovery.",
            "evidence": [{"command": "python3 scripts/poll_pr_checks.py 123 --check linux", "result": "failure"}],
            "affectedPaths": affected_paths or ["scripts/poll_pr_checks.py"],
            "fingerprint": workflow_observations.normalizeFingerprint(fingerprint),
        }

    def write_record(self, root: Path, payload: dict[str, object]) -> None:
        workflow_observations.writeJsonExclusive(
            workflow_observations.recordsDir(root) / f"{payload['id']}.json",
            payload,
        )

    def write_resolution(self, root: Path, payload: dict[str, object]) -> None:
        workflow_observations.writeJsonExclusive(
            workflow_observations.resolutionsDir(root) / f"{payload['observationId']}.json",
            payload,
        )

    def resolution_payload(
        self,
        observation_id: str,
        *,
        status: str = "resolved",
        canonical_id: str | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "schemaVersion": 1,
            "observationId": observation_id,
            "resolvedAtUtc": "2026-06-20T16:00:00Z",
            "status": status,
            "resolver": "optimizer",
            "sourceCommit": SOURCE_COMMIT,
            "resolutionSummary": "Fixed by a workflow PR and verified after merge.",
            "evidence": [{"command": "python3 -m unittest tests.test_workflow_observations", "result": "pass"}],
        }
        if status == "resolved":
            payload["mergedPr"] = 999
            payload["mergeCommit"] = "b" * 40
        if status == "duplicate":
            payload["canonicalObservationId"] = canonical_id
        return payload

    def test_validate_accepts_missing_ledger_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "missing"

            exitCode, stdout, stderr = self.run_cli(["validate", "--root", str(root)])

        self.assertEqual(0, exitCode, stderr)
        payload = json.loads(stdout)
        self.assertEqual(0, payload["records"])
        self.assertEqual(0, payload["resolutions"])
        self.assertEqual([], payload["errors"])

    def test_record_creates_canonical_json_and_missing_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "ledger"
            exitCode, stdout, stderr = self.run_cli(
                [
                    "record",
                    "--root",
                    str(root),
                    "--controller-id",
                    "Ctrl Demo/One",
                    "--role",
                    "optimizer",
                    "--source-commit",
                    SOURCE_COMMIT,
                    "--category",
                    "prompt_drift",
                    "--severity",
                    "high",
                    "--phase",
                    "optimizer",
                    "--summary",
                    "Queue launcher drifted from merged overlap policy",
                    "--details",
                    "The launcher still described source overlap as a hard exclusion.",
                    "--impact",
                    "Controllers may leave their four owned slots underfilled.",
                    "--evidence-json",
                    '{"path": "prompts/codex-queue-goal.txt", "line": 50}',
                    "--affected-path",
                    "prompts/codex-queue-goal.txt",
                ]
            )

            self.assertEqual(0, exitCode, stderr)
            payload = json.loads(stdout)["record"]
            record_path = root / "records" / f"{payload['id']}.json"
            self.assertTrue(record_path.is_file())
            self.assertFalse((root / "resolutions").exists())
            self.assertEqual(record_path.read_bytes(), workflow_observations.canonicalJson(payload))
            self.assertTrue(payload["id"].startswith("20"))
            self.assertIn("-ctrl-demo-one-", payload["id"])

    def test_concurrent_recording_creates_unique_files_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "ledger"
            context = multiprocessing.get_context("spawn")
            output: multiprocessing.Queue = context.Queue()
            processes = [context.Process(target=record_worker, args=(str(root), output)) for _ in range(6)]
            for process in processes:
                process.start()
            results = [output.get(timeout=15) for _ in processes]
            for process in processes:
                process.join(timeout=15)

            self.assertTrue(all(exitCode == 0 for exitCode, _ in results), results)
            ids = [json.loads(stdout)["record"]["id"] for _, stdout in results]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual(len(ids), len(list((root / "records").glob("*.json"))))
            exitCode, stdout, stderr = self.run_cli(["validate", "--root", str(root)])
            self.assertEqual(0, exitCode, stderr)
            self.assertEqual(6, json.loads(stdout)["records"])

    def test_exclusive_writer_refuses_same_id_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "ledger"
            payload = self.observation_payload("20260620T150000Z-ctrl-test-1234abcd")
            self.write_record(root, payload)

            with self.assertRaises(workflow_observations.ObservationError):
                self.write_record(root, payload)

    def test_validate_rejects_malformed_record_schema_paths_id_and_extension(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "ledger"
            payload = self.observation_payload("20260620T150000Z-ctrl-test-1234abcd")
            payload["category"] = "gameplay"
            payload["createdAtUtc"] = "2026-06-20 15:00:00"
            payload["affectedPaths"] = ["/absolute/path.cpp", "../escape.cpp"]
            payload["fingerprint"] = "Not Normalized"
            workflow_observations.writeJsonExclusive(root / "records" / "different-id.json", payload)
            (root / "records" / "junk.txt").write_text("not ledger data\n", encoding="utf-8")
            (root / "records" / "nested").mkdir()

            exitCode, stdout, stderr = self.run_cli(["validate", "--root", str(root)])

        self.assertEqual(1, exitCode)
        errors = "\n".join(json.loads(stdout)["errors"])
        self.assertIn("filename must equal observation id", errors)
        self.assertIn("malformed UTC timestamp", errors)
        self.assertIn("category must be one of", errors)
        self.assertIn("repository-relative", errors)
        self.assertIn("fingerprint must be normalized", errors)
        self.assertIn(".json extension", errors)
        self.assertIn("ledger entries must be files", errors)
        self.assertEqual("", stderr)

    def test_validate_rejects_noncanonical_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "ledger"
            path = root / "records" / "20260620T150000Z-ctrl-test-1234abcd.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(self.observation_payload("20260620T150000Z-ctrl-test-1234abcd")), encoding="utf-8"
            )

            exitCode, stdout, _ = self.run_cli(["validate", "--root", str(root)])

        self.assertEqual(1, exitCode)
        self.assertIn("JSON must end with one newline", "\n".join(json.loads(stdout)["errors"]))

    def test_record_rejects_malformed_evidence_secrets_controls_and_oversized_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "ledger"
            base = [
                "record",
                "--root",
                str(root),
                "--controller-id",
                "ctrl-test",
                "--role",
                "controller",
                "--source-commit",
                SOURCE_COMMIT,
                "--category",
                "resources",
                "--severity",
                "medium",
                "--phase",
                "cleanup",
                "--summary",
                "Resource audit captured unsafe evidence",
                "--details",
                "Controller attempted to persist unsafe diagnostic data.",
                "--impact",
                "The ledger could leak secrets or create unreadable diffs.",
                "--affected-path",
                "scripts/controller_resource_audit.py",
            ]

            exitCode, _, stderr = self.run_cli(base + ["--evidence-json", '{"env": {"TOKEN": "x"}}'])
            self.assertNotEqual(0, exitCode)
            self.assertIn("forbidden", stderr)

            exitCode, _, stderr = self.run_cli(base + ["--evidence-json", "[]"])
            self.assertNotEqual(0, exitCode)
            self.assertIn("at least one entry", stderr)

            exitCode, _, stderr = self.run_cli(
                base
                + [
                    "--evidence-json",
                    '{"path": "scripts/controller_resource_audit.py"}',
                    "--fingerprint",
                    "resource token ghp_abcdefghijklmnopqrstuv",
                ]
            )
            self.assertNotEqual(0, exitCode)
            self.assertIn("fingerprint", stderr)
            self.assertIn("secret", stderr)

            exitCode, _, stderr = self.run_cli(
                base + ["--evidence-json", '{"log": "token=ghp_abcdefghijklmnopqrstuv"}']
            )
            self.assertNotEqual(0, exitCode)
            self.assertIn("secret", stderr)

            exitCode, _, stderr = self.run_cli(base + ["--evidence-json", json.dumps({"log": "bad\u0000text"})])
            self.assertNotEqual(0, exitCode)
            self.assertIn("control", stderr)

            exitCode, _, stderr = self.run_cli(base + ["--evidence-json", json.dumps({"log": "x" * 9000})])
            self.assertNotEqual(0, exitCode)
            self.assertIn("oversized", stderr)

    def test_open_resolved_show_and_resolution_receipt_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "ledger"
            record_exit, record_stdout, record_stderr = self.run_cli(
                [
                    "record",
                    "--root",
                    str(root),
                    "--controller-id",
                    "ctrl-test",
                    "--role",
                    "optimizer",
                    "--source-commit",
                    SOURCE_COMMIT,
                    "--category",
                    "observability",
                    "--severity",
                    "medium",
                    "--phase",
                    "optimizer",
                    "--summary",
                    "Open PR audit missed check rollups",
                    "--details",
                    "The audit did not parse statusCheckRollup entries.",
                    "--impact",
                    "Every open PR looked like generic human-review debt.",
                    "--evidence-json",
                    '{"command": "python3 scripts/pr_review_audit.py --format table", "result": "unknown checks"}',
                    "--affected-path",
                    "scripts/pr_review_audit.py",
                    "--fingerprint",
                    "pr audit status check rollup unknown",
                ]
            )
            self.assertEqual(0, record_exit, record_stderr)
            observation_id = json.loads(record_stdout)["record"]["id"]

            list_exit, list_stdout, _ = self.run_cli(["list", "--root", str(root), "--state", "open"])
            self.assertEqual(0, list_exit)
            self.assertEqual([observation_id], [item["id"] for item in json.loads(list_stdout)["observations"]])

            resolve_exit, resolve_stdout, resolve_stderr = self.run_cli(
                [
                    "resolve",
                    "--root",
                    str(root),
                    "--id",
                    observation_id,
                    "--status",
                    "resolved",
                    "--resolver",
                    "optimizer",
                    "--source-commit",
                    SOURCE_COMMIT,
                    "--summary",
                    "Merged PR fixed statusCheckRollup parsing.",
                    "--evidence-json",
                    '{"pr": 603, "check": "build / linux"}',
                    "--merged-pr",
                    "603",
                    "--merge-commit",
                    "b" * 40,
                ]
            )
            self.assertEqual(0, resolve_exit, resolve_stderr)
            self.assertEqual(observation_id, json.loads(resolve_stdout)["resolution"]["observationId"])

            show_exit, show_stdout, _ = self.run_cli(["show", "--root", str(root), "--id", observation_id])
            self.assertEqual(0, show_exit)
            shown = json.loads(show_stdout)
            self.assertEqual(observation_id, shown["observation"]["id"])
            self.assertEqual("resolved", shown["resolution"]["status"])

            list_exit, list_stdout, _ = self.run_cli(["list", "--root", str(root), "--state", "resolved"])
            self.assertEqual(0, list_exit)
            self.assertEqual([observation_id], [item["id"] for item in json.loads(list_stdout)["observations"]])

    def test_resolve_rejects_orphan_duplicate_receipt_and_self_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "ledger"
            unknown_id = "20260620T150000Z-ctrl-test-1234abcd"

            exitCode, _, stderr = self.run_cli(
                [
                    "resolve",
                    "--root",
                    str(root),
                    "--id",
                    unknown_id,
                    "--status",
                    "resolved",
                    "--resolver",
                    "optimizer",
                    "--source-commit",
                    SOURCE_COMMIT,
                    "--summary",
                    "No observation exists.",
                    "--merged-pr",
                    "1",
                    "--merge-commit",
                    "b" * 40,
                ]
            )
            self.assertNotEqual(0, exitCode)
            self.assertIn("unknown observation", stderr)

            payload = self.observation_payload(unknown_id)
            self.write_record(root, payload)
            exitCode, _, stderr = self.run_cli(
                [
                    "resolve",
                    "--root",
                    str(root),
                    "--id",
                    unknown_id,
                    "--status",
                    "duplicate",
                    "--resolver",
                    "optimizer",
                    "--source-commit",
                    SOURCE_COMMIT,
                    "--summary",
                    "Self duplicate is invalid.",
                    "--canonical-id",
                    unknown_id,
                ]
            )
            self.assertNotEqual(0, exitCode)
            self.assertIn("cannot point to itself", stderr)

    def test_validate_rejects_empty_affected_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "ledger"
            payload = self.observation_payload("20260620T150000Z-ctrl-test-1234abcd")
            payload["affectedPaths"] = []
            self.write_record(root, payload)

            exitCode, stdout, _ = self.run_cli(["validate", "--root", str(root)])

        self.assertEqual(1, exitCode)
        self.assertIn("affectedPaths must contain at least one path", "\n".join(json.loads(stdout)["errors"]))

    def test_resolved_receipt_requires_merged_pr_and_merge_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "ledger"
            observation_id = "20260620T150000Z-ctrl-test-1234abcd"
            self.write_record(root, self.observation_payload(observation_id))

            exitCode, _, stderr = self.run_cli(
                [
                    "resolve",
                    "--root",
                    str(root),
                    "--id",
                    observation_id,
                    "--status",
                    "resolved",
                    "--resolver",
                    "optimizer",
                    "--source-commit",
                    SOURCE_COMMIT,
                    "--summary",
                    "Missing merge evidence must be rejected.",
                    "--evidence-json",
                    '{"check": "post-merge verification pending"}',
                ]
            )

        self.assertNotEqual(0, exitCode)
        self.assertIn("mergedPr", stderr)
        self.assertIn("mergeCommit", stderr)

    def test_validate_reports_malformed_receipt_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "ledger"
            first = self.observation_payload("20260620T150000Z-ctrl-test-11111111")
            second = self.observation_payload("20260620T150100Z-ctrl-test-22222222")
            self.write_record(root, first)
            self.write_record(root, second)
            self.write_resolution(root, self.resolution_payload(first["id"]))
            malformed = self.resolution_payload(second["id"])
            del malformed["status"]
            self.write_resolution(root, malformed)

            exitCode, stdout, stderr = self.run_cli(["validate", "--root", str(root)])

        self.assertEqual(1, exitCode)
        self.assertEqual("", stderr)
        payload = json.loads(stdout)
        self.assertEqual({"resolved": 1}, payload["resolutionStatusCounts"])
        self.assertIn("status must be one of", "\n".join(payload["errors"]))

    def test_validate_rejects_orphan_and_cyclic_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "ledger"
            first = self.observation_payload("20260620T150000Z-ctrl-test-11111111")
            second = self.observation_payload("20260620T150100Z-ctrl-test-22222222")
            self.write_record(root, first)
            self.write_record(root, second)
            self.write_resolution(
                root,
                self.resolution_payload(first["id"], status="duplicate", canonical_id=second["id"]),
            )
            self.write_resolution(
                root,
                self.resolution_payload(second["id"], status="duplicate", canonical_id=first["id"]),
            )
            self.write_resolution(
                root,
                self.resolution_payload("20260620T150200Z-ctrl-test-33333333"),
            )

            exitCode, stdout, _ = self.run_cli(["validate", "--root", str(root)])

        self.assertEqual(1, exitCode)
        errors = "\n".join(json.loads(stdout)["errors"])
        self.assertIn("duplicate cycle", errors)
        self.assertIn("orphan resolution", errors)

    def test_next_ranks_by_severity_recurrence_oldest_and_lexical_tie_break(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "ledger"
            records = [
                self.observation_payload(
                    "20260620T150000Z-ctrl-test-11111111",
                    created_at="2026-06-20T15:00:00Z",
                    severity="high",
                    fingerprint="same ci waste",
                ),
                self.observation_payload(
                    "20260620T150100Z-ctrl-test-22222222",
                    created_at="2026-06-20T15:01:00Z",
                    severity="high",
                    fingerprint="same ci waste",
                ),
                self.observation_payload(
                    "20260620T145900Z-ctrl-test-33333333",
                    created_at="2026-06-20T14:59:00Z",
                    severity="high",
                    fingerprint="single older high",
                ),
                self.observation_payload(
                    "20260620T140000Z-ctrl-test-44444444",
                    created_at="2026-06-20T14:00:00Z",
                    severity="medium",
                    fingerprint="medium repeated",
                ),
            ]
            for payload in records:
                self.write_record(root, payload)
            before = sorted(path.read_bytes() for path in (root / "records").glob("*.json"))

            first_exit, first_stdout, _ = self.run_cli(["next", "--root", str(root)])
            second_exit, second_stdout, _ = self.run_cli(["next", "--root", str(root)])

            self.assertEqual(0, first_exit)
            self.assertEqual(0, second_exit)
            self.assertEqual(json.loads(first_stdout), json.loads(second_stdout))
            payload = json.loads(first_stdout)
            self.assertEqual("same ci waste", payload["next"]["fingerprint"])
            self.assertEqual(2, payload["next"]["recurrenceCount"])
            self.assertIn("severity=high", payload["next"]["ranking"])
            after = sorted(path.read_bytes() for path in (root / "records").glob("*.json"))
            self.assertEqual(before, after)

    def test_cli_errors_are_nonzero_with_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "ledger"

            exitCode, stdout, stderr = self.run_cli(
                ["show", "--root", str(root), "--id", "20260620T150000Z-ctrl-test-1234abcd"]
            )

        self.assertEqual(1, exitCode)
        self.assertEqual("", stdout)
        self.assertIn("unknown observation", stderr)

    def test_validate_base_allows_added_records_and_rejects_mutation_or_non_json_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "repo"
            repo.mkdir()
            self.run_git(repo, ["init"])
            self.run_git(repo, ["config", "user.email", "test@example.invalid"])
            self.run_git(repo, ["config", "user.name", "Workflow Test"])
            root = repo / "planning" / "workflow_observations"
            first = self.observation_payload("20260620T150000Z-ctrl-test-11111111")
            second = self.observation_payload("20260620T150100Z-ctrl-test-22222222")
            self.write_record(root, first)
            self.write_record(root, second)
            self.run_git(repo, ["add", "planning/workflow_observations"])
            self.run_git(repo, ["commit", "-m", "base ledger records"])

            old_cwd = Path.cwd()
            try:
                os.chdir(repo)
                added = self.observation_payload("20260620T150200Z-ctrl-test-33333333")
                self.write_record(Path("planning/workflow_observations"), added)
                self.run_git(repo, ["add", f"planning/workflow_observations/records/{added['id']}.json"])
                exitCode, stdout, stderr = self.run_cli(
                    ["validate", "--root", "planning/workflow_observations", "--base", "HEAD"]
                )
                self.assertEqual(0, exitCode, stderr)
                self.assertEqual([], json.loads(stdout)["errors"])

                mutated = dict(first)
                mutated["summary"] = "Mutated old observation should fail diff validation"
                (Path("planning/workflow_observations/records") / f"{first['id']}.json").write_bytes(
                    workflow_observations.canonicalJson(mutated)
                )
                (Path("planning/workflow_observations/records") / f"{second['id']}.json").unlink()
                Path("planning/workflow_observations/records/not-json.txt").write_text(
                    "not a JSON ledger file\n", encoding="utf-8"
                )
                self.run_git(repo, ["add", "planning/workflow_observations/records/not-json.txt"])

                exitCode, stdout, stderr = self.run_cli(
                    ["validate", "--root", "planning/workflow_observations", "--base", "HEAD"]
                )
            finally:
                os.chdir(old_cwd)

        self.assertEqual(1, exitCode)
        self.assertEqual("", stderr)
        errors = "\n".join(json.loads(stdout)["errors"])
        self.assertIn("may only be added", errors)
        self.assertIn("ledger PR changes must be JSON files", errors)

    def test_validate_base_rejects_mixed_ledger_and_non_ledger_pr_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "repo"
            repo.mkdir()
            self.run_git(repo, ["init"])
            self.run_git(repo, ["config", "user.email", "test@example.invalid"])
            self.run_git(repo, ["config", "user.name", "Workflow Test"])
            (repo / "scripts").mkdir()
            (repo / "scripts" / "placeholder.py").write_text("print('base')\n", encoding="utf-8")
            self.run_git(repo, ["add", "scripts/placeholder.py"])
            self.run_git(repo, ["commit", "-m", "base non-ledger file"])

            old_cwd = Path.cwd()
            try:
                os.chdir(repo)
                added = self.observation_payload("20260620T150200Z-ctrl-test-33333333")
                self.write_record(Path("planning/workflow_observations"), added)
                Path("scripts/placeholder.py").write_text("print('changed')\n", encoding="utf-8")
                self.run_git(
                    repo,
                    [
                        "add",
                        f"planning/workflow_observations/records/{added['id']}.json",
                        "scripts/placeholder.py",
                    ],
                )

                exitCode, stdout, stderr = self.run_cli(
                    ["validate", "--root", "planning/workflow_observations", "--base", "HEAD"]
                )
            finally:
                os.chdir(old_cwd)

        self.assertEqual(1, exitCode)
        self.assertEqual("", stderr)
        self.assertIn(
            "scripts/placeholder.py: ledger PR changes must not be mixed with non-ledger changes",
            "\n".join(json.loads(stdout)["errors"]),
        )

    def test_validate_base_allows_non_ledger_pr_without_ledger_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "repo"
            repo.mkdir()
            self.run_git(repo, ["init"])
            self.run_git(repo, ["config", "user.email", "test@example.invalid"])
            self.run_git(repo, ["config", "user.name", "Workflow Test"])
            (repo / "scripts").mkdir()
            (repo / "scripts" / "placeholder.py").write_text("print('base')\n", encoding="utf-8")
            self.run_git(repo, ["add", "scripts/placeholder.py"])
            self.run_git(repo, ["commit", "-m", "base non-ledger file"])

            old_cwd = Path.cwd()
            try:
                os.chdir(repo)
                Path("scripts/placeholder.py").write_text("print('changed')\n", encoding="utf-8")

                exitCode, stdout, stderr = self.run_cli(
                    ["validate", "--root", "planning/workflow_observations", "--base", "HEAD"]
                )
            finally:
                os.chdir(old_cwd)

        self.assertEqual(0, exitCode, stderr)
        self.assertEqual([], json.loads(stdout)["errors"])

    def test_workflow_ledger_operations_preserve_xlsx_bytes_and_queue_compatibility(self) -> None:
        workbook = REPO_ROOT / issue_queue.DEFAULT_WORKBOOK
        before = workbook.read_bytes()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "ledger"
            exitCode, _, stderr = self.run_cli(
                [
                    "record",
                    "--root",
                    str(root),
                    "--controller-id",
                    "ctrl-test",
                    "--role",
                    "controller",
                    "--source-commit",
                    SOURCE_COMMIT,
                    "--category",
                    "queue_lease",
                    "--severity",
                    "low",
                    "--phase",
                    "dispatch",
                    "--summary",
                    "Queue validation warning required observation",
                    "--details",
                    "The controller recorded a workflow-only queue observation.",
                    "--impact",
                    "The implementation XLSX remains the canonical task queue.",
                    "--evidence-json",
                    '{"command": "python3 scripts/issue_queue.py validate", "result": "warning"}',
                    "--affected-path",
                    "planning/fall_of_nouraajd_issue_proposals.xlsx",
                ]
            )
            self.assertEqual(0, exitCode, stderr)
            self.run_cli(["validate", "--root", str(root)])
            self.run_cli(["list", "--root", str(root), "--state", "all"])
            issue_queue.loadQueue(workbook)

        self.assertEqual(before, workbook.read_bytes())

    def test_current_commit_raises_observation_error_when_git_is_missing(self) -> None:
        def raise_missing_git(*_args: object, **_kwargs: object) -> None:
            raise FileNotFoundError(2, "No such file or directory", "git")

        with patch.object(workflow_observations.subprocess, "run", side_effect=raise_missing_git):
            with self.assertRaises(workflow_observations.ObservationError) as caught:
                workflow_observations.currentCommit()

        self.assertIn("pass --source-commit", str(caught.exception))

    def test_validate_pr_changes_raises_observation_error_when_git_is_missing(self) -> None:
        def raise_missing_git(*_args: object, **_kwargs: object) -> None:
            raise FileNotFoundError(2, "No such file or directory", "git")

        with patch.object(workflow_observations.subprocess, "run", side_effect=raise_missing_git):
            with self.assertRaises(workflow_observations.ObservationError) as caught:
                workflow_observations.validatePrChanges(Path("planning/workflow_observations"), "main")

        self.assertIn("git executable not found on PATH", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
