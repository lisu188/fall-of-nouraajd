from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import subagent_registry, worker_report

OWNER = "controller/ctrl-test-1-abc/subagent-1"
CONTROLLER_ID = "ctrl-test-1-abc"
CLAIM_ID = "7920ae34-aaca-4808-a308-adfcd6e0f3e3"
ISSUE = "[EPIC_01][STORY_03][SUBSTORY_02]Standardize structured worker reports"
BRANCH = "codex/epic-01-story-03-substory-02-structured-reports"
CI_SHA = "0123456789abcdef0123456789abcdef01234567"
OBSERVATION_REF = "20260101T000000Z-ctrl-test-1-abc-0a1b2c3d"


def validReport(**overrides: object) -> dict:
    payload: dict = {
        "schemaVersion": worker_report.SCHEMA_VERSION,
        "owner": OWNER,
        "claimId": CLAIM_ID,
        "issue": ISSUE,
        "branch": BRANCH,
        "outcome": "COMPLETE",
        "ciHeadSha": CI_SHA,
        "filesChanged": ["scripts/worker_report.py", "tests/test_worker_report.py"],
        "commands": [
            {
                "command": "python3 -m unittest tests.test_worker_report",
                "status": "passed",
                "exitCode": 0,
                "outputSummary": "OK",
            },
            {"command": "python3 test.py", "status": "skipped", "outputSummary": "outsourced to CI"},
        ],
    }
    payload.update(overrides)
    return payload


class WorkerReportSchemaTest(unittest.TestCase):
    def test_valid_report_passes_schema_validation(self) -> None:
        self.assertEqual(worker_report.validateReportPayload(validReport()), [])
        optional = validReport(
            controllerId=CONTROLLER_ID,
            registrationId="reg-1234",
            role="WORKER",
            phase="FULL_VALIDATION",
            createdAtUtc="2026-07-02T10:00:00Z",
            blockers=["waiting for CI"],
            risks=["doc drift"],
            nextAction="open the implementation PR",
            observationRefs=[OBSERVATION_REF],
        )
        self.assertEqual(worker_report.validateReportPayload(optional), [])

    def test_malformed_reports_are_rejected(self) -> None:
        self.assertTrue(worker_report.validateReportPayload("not-a-dict"))

        missing = validReport()
        del missing["claimId"]
        self.assertTrue(
            any("missing required key 'claimId'" in e for e in worker_report.validateReportPayload(missing))
        )

        unknown = validReport(surprise="x")
        self.assertTrue(any("unknown key 'surprise'" in e for e in worker_report.validateReportPayload(unknown)))

        wrong_version = validReport(schemaVersion=99)
        self.assertTrue(any("schemaVersion" in e for e in worker_report.validateReportPayload(wrong_version)))

        bad_owner = validReport(owner="subagent-1")
        self.assertTrue(any("owner" in e for e in worker_report.validateReportPayload(bad_owner)))

        empty_claim = validReport(claimId="   ")
        self.assertTrue(any("claimId" in e for e in worker_report.validateReportPayload(empty_claim)))

        spaced_branch = validReport(branch="codex/bad branch")
        self.assertTrue(any("branch" in e for e in worker_report.validateReportPayload(spaced_branch)))

        for bad_path in ("/abs/path.py", "..\\evil.py", "../escape.py", "a//b.py", ""):
            errors = worker_report.validateReportPayload(validReport(filesChanged=[bad_path]))
            self.assertTrue(any("filesChanged[0]" in e for e in errors), bad_path)

        duplicates = validReport(filesChanged=["scripts/worker_report.py", "scripts/worker_report.py"])
        self.assertTrue(any("duplicates" in e for e in worker_report.validateReportPayload(duplicates)))

        oversized = validReport(filesChanged=[f"src/file{i}.py" for i in range(worker_report.MAX_LIST_ENTRIES + 1)])
        self.assertTrue(any("must not exceed" in e for e in worker_report.validateReportPayload(oversized)))

    def test_command_enum_and_exit_code_precision(self) -> None:
        def command_errors(entry: dict, outcome: str = "IN_PROGRESS") -> list[str]:
            return worker_report.validateReportPayload(validReport(outcome=outcome, commands=[entry]))

        base = {"command": "python3 test.py", "status": "passed", "exitCode": 0}
        self.assertEqual(command_errors(base), [])

        self.assertTrue(any("status" in e for e in command_errors(dict(base, status="mostly_passed"))))
        self.assertTrue(
            any("requires an integer exitCode" in e for e in command_errors({"command": "x", "status": "passed"}))
        )
        self.assertTrue(
            any("requires an integer exitCode" in e for e in command_errors({"command": "x", "status": "failed"}))
        )
        self.assertTrue(any("exitCode 0" in e for e in command_errors(dict(base, exitCode=1))))
        self.assertTrue(any("integer exitCode" in e for e in command_errors(dict(base, exitCode=True))))
        self.assertTrue(
            any(
                "must not carry an exitCode" in e
                for e in command_errors({"command": "x", "status": "skipped", "exitCode": 0})
            )
        )
        self.assertTrue(any("unknown key" in e for e in command_errors(dict(base, stdout="x"))))
        self.assertEqual(command_errors({"command": "x", "status": "failed", "exitCode": 2}), [])
        for status in ("skipped", "blocked", "not_run"):
            self.assertEqual(command_errors({"command": "x", "status": status}), [])

        bad_outcome = validReport(outcome="DONE_ISH")
        self.assertTrue(any("outcome" in e for e in worker_report.validateReportPayload(bad_outcome)))

        no_passed = validReport(commands=[{"command": "x", "status": "not_run"}])
        self.assertTrue(
            any("COMPLETE requires at least one" in e for e in worker_report.validateReportPayload(no_passed))
        )
        with_failed = validReport(
            commands=[
                {"command": "a", "status": "passed", "exitCode": 0},
                {"command": "b", "status": "failed", "exitCode": 1},
            ]
        )
        self.assertTrue(any("COMPLETE must not carry" in e for e in worker_report.validateReportPayload(with_failed)))

    def test_output_summary_and_text_bounds(self) -> None:
        at_bound = validReport()
        at_bound["commands"][0]["outputSummary"] = "x" * worker_report.MAX_OUTPUT_SUMMARY_CHARS
        self.assertEqual(worker_report.validateReportPayload(at_bound), [])

        over_bound = validReport()
        over_bound["commands"][0]["outputSummary"] = "x" * (worker_report.MAX_OUTPUT_SUMMARY_CHARS + 1)
        self.assertTrue(any("outputSummary exceeds" in e for e in worker_report.validateReportPayload(over_bound)))

        long_blocker = validReport(blockers=["x" * (worker_report.MAX_TEXT_CHARS + 1)])
        self.assertTrue(any("blockers[0]" in e for e in worker_report.validateReportPayload(long_blocker)))

    def test_observation_refs_are_validated(self) -> None:
        self.assertEqual(worker_report.validateReportPayload(validReport(observationRefs=[OBSERVATION_REF])), [])
        bad_ref = validReport(observationRefs=["not-an-observation-id"])
        self.assertTrue(any("observationRefs[0]" in e for e in worker_report.validateReportPayload(bad_ref)))
        duplicate_refs = validReport(observationRefs=[OBSERVATION_REF, OBSERVATION_REF])
        self.assertTrue(any("duplicates" in e for e in worker_report.validateReportPayload(duplicate_refs)))


class WorkerReportIdentityAndCiShaTest(unittest.TestCase):
    def test_controller_id_must_match_owner_segment(self) -> None:
        self.assertEqual(worker_report.validateReportPayload(validReport(controllerId=CONTROLLER_ID)), [])
        errors = worker_report.validateReportPayload(validReport(controllerId="ctrl-other"))
        self.assertTrue(any("does not match the owner controller segment" in e for e in errors))

    def test_identity_cross_checks_reject_mismatches(self) -> None:
        report = validReport()
        matching = worker_report.identityErrors(
            report, expectedOwner=OWNER, expectedClaimId=CLAIM_ID, expectedIssue=ISSUE, expectedBranch=BRANCH
        )
        self.assertEqual(matching, [])

        self.assertTrue(worker_report.identityErrors(report, expectedOwner="controller/ctrl-x/subagent-9"))
        self.assertTrue(worker_report.identityErrors(report, expectedClaimId="other-claim"))
        self.assertTrue(worker_report.identityErrors(report, expectedIssue="[EPIC_99][STORY_01][SUBSTORY_01]Other"))
        mismatch = worker_report.identityErrors(report, expectedBranch="codex/other-branch")
        self.assertTrue(any("identity mismatch" in e and "branch" in e for e in mismatch))

    def test_ci_sha_plausibility_and_staleness(self) -> None:
        for bad_sha in ("xyz", "12345", "ABCDEF0123456", ""):
            errors = worker_report.validateReportPayload(validReport(ciHeadSha=bad_sha))
            self.assertTrue(any("ciHeadSha" in e for e in errors), bad_sha)
        abbreviated = validReport(ciHeadSha=CI_SHA[:9])
        self.assertEqual(worker_report.validateReportPayload(abbreviated), [])

        self.assertEqual(worker_report.ciShaErrors(validReport(), CI_SHA, "evidence"), [])
        self.assertEqual(worker_report.ciShaErrors(abbreviated, CI_SHA, "evidence"), [])
        self.assertEqual(worker_report.ciShaErrors(validReport(), CI_SHA[:12], "evidence"), [])

        stale = worker_report.ciShaErrors(validReport(), "f" * 40, "current head")
        self.assertTrue(any("stale ciHeadSha" in e for e in stale))
        bad_evidence = worker_report.ciShaErrors(validReport(), "not-a-sha", "current head")
        self.assertTrue(any("not a plausible git SHA" in e for e in bad_evidence))

    def test_validate_cli_rejects_stale_ci_sha_against_real_branch_head(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "repo"
            repo.mkdir()
            env_config = ["-c", "user.email=test@example.com", "-c", "user.name=Test"]
            subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
            (repo / "file.txt").write_text("content\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "file.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), *env_config, "commit", "--quiet", "-m", "init"], check=True)
            subprocess.run(["git", "-C", str(repo), "branch", BRANCH], check=True)
            head = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", BRANCH], check=True, capture_output=True, text=True
            ).stdout.strip()

            fresh_file = Path(temp_dir) / "fresh.json"
            fresh_file.write_text(json.dumps(validReport(ciHeadSha=head)), encoding="utf-8")
            stale_file = Path(temp_dir) / "stale.json"
            stale_file.write_text(json.dumps(validReport()), encoding="utf-8")

            code, payload = runCli(["validate", "--report-file", str(fresh_file), "--repo", str(repo)])
            self.assertEqual(code, 0)
            self.assertEqual(payload["errors"], [])

            code, payload = runCli(["validate", "--report-file", str(stale_file), "--repo", str(repo)])
            self.assertEqual(code, 1)
            self.assertTrue(any("stale ciHeadSha" in e for e in payload["errors"]))

            missing_branch = validReport(ciHeadSha=head, branch="codex/branch-that-does-not-exist")
            missing_file = Path(temp_dir) / "missing.json"
            missing_file.write_text(json.dumps(missing_branch), encoding="utf-8")
            code, payload = runCli(["validate", "--report-file", str(missing_file), "--repo", str(repo)])
            self.assertEqual(code, 1)
            self.assertTrue(any("cannot be resolved" in e for e in payload["errors"]))


class WorkerReportHandoffTest(unittest.TestCase):
    def overflowingReport(self) -> dict:
        commands = [{"command": f"python3 check_{i}.py", "status": "not_run"} for i in range(15)]
        commands.append({"command": "python3 -m unittest tests.test_worker_report", "status": "passed", "exitCode": 0})
        return validReport(
            outcome="IN_PROGRESS",
            commands=commands,
            filesChanged=[f"src/core/file{i:02d}.cpp" for i in range(25)],
            blockers=[f"blocker {i}" for i in range(12)],
            risks=[f"risk {i}" for i in range(12)],
        )

    def test_handoff_is_deterministic_and_ignores_wall_clock(self) -> None:
        first = worker_report.buildHandoff(validReport(createdAtUtc="2026-07-01T08:00:00Z"))
        second = worker_report.buildHandoff(validReport(createdAtUtc="2026-07-02T23:59:59Z"))
        self.assertEqual(first, second)
        self.assertEqual(first, worker_report.buildHandoff(validReport()))
        self.assertEqual(worker_report.canonicalJson(first), worker_report.canonicalJson(second))
        self.assertEqual(
            worker_report.reportFingerprint(validReport(createdAtUtc="2026-07-01T08:00:00Z")),
            worker_report.reportFingerprint(validReport()),
        )

    def test_handoff_is_bounded_with_documented_cap(self) -> None:
        report = self.overflowingReport()
        handoff = worker_report.buildHandoff(report)

        cap = worker_report.HANDOFF_MAX_ITEMS_PER_SECTION
        self.assertEqual(handoff["maxItemsPerSection"], cap)
        self.assertEqual(len(handoff["filesChanged"]), cap)
        self.assertEqual(handoff["filesChangedOmitted"], 25 - cap)
        self.assertEqual(len(handoff["pendingValidation"]), cap)
        self.assertEqual(handoff["pendingValidationOmitted"], 15 - cap)
        self.assertEqual(len(handoff["blockers"]), cap)
        self.assertEqual(handoff["blockersOmitted"], 12 - cap)
        self.assertEqual(handoff["risksOmitted"], 12 - cap)
        self.assertEqual(
            handoff["acceptedEvidence"], [{"command": "python3 -m unittest tests.test_worker_report", "exitCode": 0}]
        )
        self.assertEqual(handoff["commandStatusCounts"]["not_run"], 15)
        self.assertEqual(handoff["commandStatusCounts"]["passed"], 1)
        # Pending validation preserves the authored execution order.
        self.assertEqual(handoff["pendingValidation"][0]["command"], "python3 check_0.py")

        widened = worker_report.buildHandoff(report, maxItems=30)
        self.assertEqual(len(widened["filesChanged"]), 25)
        self.assertEqual(widened["filesChangedOmitted"], 0)

        for bad_cap in (0, -1, worker_report.HANDOFF_MAX_ITEMS_LIMIT + 1, True):
            with self.assertRaises(worker_report.WorkerReportError):
                worker_report.buildHandoff(report, maxItems=bad_cap)

    def test_restart_handoff_supports_resume_after_interruption(self) -> None:
        # The worker was interrupted mid-task; the controller restarts with only
        # the last accepted report and must rebuild a safe resume context.
        interrupted = validReport(
            outcome="IN_PROGRESS",
            phase="FOCUSED_VALIDATION",
            commands=[
                {"command": "python3 scripts/validate_content.py --repo-root .", "status": "passed", "exitCode": 0},
                {"command": "python3 -m unittest tests.test_worker_report", "status": "failed", "exitCode": 1},
                {"command": "python3 test.py", "status": "not_run"},
            ],
            blockers=["focused regression still failing"],
        )
        handoff = worker_report.buildHandoff(interrupted)

        self.assertEqual(handoff["kind"], "restart-handoff")
        self.assertEqual(handoff["source"]["owner"], OWNER)
        self.assertEqual(handoff["source"]["claimId"], CLAIM_ID)
        self.assertEqual(handoff["source"]["issue"], ISSUE)
        self.assertEqual(handoff["source"]["branch"], BRANCH)
        self.assertEqual(handoff["source"]["phase"], "FOCUSED_VALIDATION")
        self.assertEqual(
            [entry["command"] for entry in handoff["pendingValidation"]],
            ["python3 -m unittest tests.test_worker_report", "python3 test.py"],
        )
        self.assertEqual(
            handoff["acceptedEvidence"],
            [{"command": "python3 scripts/validate_content.py --repo-root .", "exitCode": 0}],
        )
        self.assertEqual(handoff["blockers"], ["focused regression still failing"])
        self.assertEqual(handoff["safeNextAction"], worker_report.SAFE_NEXT_ACTION_BY_OUTCOME["IN_PROGRESS"])
        self.assertEqual(handoff, worker_report.buildHandoff(interrupted))

        with self.assertRaisesRegex(worker_report.WorkerReportError, "invalid report"):
            worker_report.buildHandoff(validReport(outcome="DONE_ISH"))

    def test_json_and_markdown_render_from_one_normalized_model(self) -> None:
        report = validReport(
            controllerId=CONTROLLER_ID,
            phase="FULL_VALIDATION",
            blockers=["waiting for CI"],
            nextAction="enable auto-merge after CI",
            observationRefs=[OBSERVATION_REF],
        )
        normalized = worker_report.normalizeReport(report)
        markdown = worker_report.renderReportMarkdown(report)

        for value in (OWNER, CLAIM_ID, ISSUE, BRANCH, CI_SHA, "waiting for CI", "enable auto-merge after CI"):
            self.assertIn(value, markdown)
        for entry in normalized["commands"]:
            self.assertIn(entry["command"], markdown)
            self.assertIn(f"[{entry['status']}]", markdown)
        for path in normalized["filesChanged"]:
            self.assertIn(path, markdown)

        handoff = worker_report.buildHandoff(report)
        handoff_markdown = worker_report.renderHandoffMarkdown(handoff)
        for value in (OWNER, CLAIM_ID, ISSUE, handoff["reportFingerprint"], handoff["safeNextAction"]):
            self.assertIn(value, handoff_markdown)

        with self.assertRaisesRegex(worker_report.WorkerReportError, "invalid report"):
            worker_report.renderReportMarkdown(validReport(claimId=""))


class WorkerReportRegistryIntegrationTest(unittest.TestCase):
    def test_registry_payload_round_trip_advances_last_seen(self) -> None:
        report = validReport(phase="FULL_VALIDATION", createdAtUtc="2026-07-02T10:00:00Z")
        payload = worker_report.registryReportPayload(report)
        self.assertEqual(subagent_registry.validateReportPayload(payload), [])
        self.assertEqual(payload["owner"], OWNER)
        self.assertEqual(payload["claimId"], CLAIM_ID)
        self.assertEqual(payload["lastSeenUtc"], "2026-07-02T10:00:00Z")
        self.assertEqual(payload["changedFiles"], sorted(report["filesChanged"]))

        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "registry.json"
            subagent_registry.registerAgent(
                registry_path,
                owner=OWNER,
                role="WORKER",
                issue=ISSUE,
                claimId=CLAIM_ID,
                now=subagent_registry.parseUtc("2026-07-02T09:00:00Z"),
            )
            updated = subagent_registry.reportAgent(registry_path, payload)
            self.assertEqual(updated["status"], "LIVE")
            self.assertEqual(updated["phase"], "FULL_VALIDATION")

        with self.assertRaisesRegex(worker_report.WorkerReportError, "last-seen-utc"):
            worker_report.registryReportPayload(validReport())
        explicit = worker_report.registryReportPayload(validReport(), lastSeenUtc="2026-07-02T11:00:00Z")
        self.assertEqual(explicit["lastSeenUtc"], "2026-07-02T11:00:00Z")


def runCli(arguments: list[str]) -> tuple[int, dict]:
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
        code = worker_report.main(arguments)
    text = stdout.getvalue()
    return code, json.loads(text) if text.lstrip().startswith("{") else {"text": text}


class WorkerReportCliTest(unittest.TestCase):
    def test_cli_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "report.json"
            code, created = runCli(
                [
                    "create",
                    "--owner",
                    OWNER,
                    "--claim-id",
                    CLAIM_ID,
                    "--issue",
                    ISSUE,
                    "--branch",
                    BRANCH,
                    "--outcome",
                    "COMPLETE",
                    "--ci-head-sha",
                    CI_SHA.upper(),
                    "--file-changed",
                    "scripts/worker_report.py",
                    "--command-json",
                    json.dumps(
                        {"command": "python3 -m unittest tests.test_worker_report", "status": "passed", "exitCode": 0}
                    ),
                    "--created-at-utc",
                    "2026-07-02T10:00:00Z",
                    "--output",
                    str(report_path),
                ]
            )
            self.assertEqual(code, 0)
            del created
            stored = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(stored["ciHeadSha"], CI_SHA)
            self.assertEqual(worker_report.validateReportPayload(stored), [])

            code, payload = runCli(
                [
                    "validate",
                    "--report-file",
                    str(report_path),
                    "--expect-owner",
                    OWNER,
                    "--expect-claim-id",
                    CLAIM_ID,
                    "--expect-issue",
                    ISSUE,
                    "--expect-branch",
                    BRANCH,
                    "--expect-ci-sha",
                    CI_SHA,
                ]
            )
            self.assertEqual(code, 0)
            self.assertTrue(payload["valid"])

            code, payload = runCli(
                ["validate", "--report-file", str(report_path), "--expect-claim-id", "another-claim"]
            )
            self.assertEqual(code, 1)
            self.assertTrue(any("identity mismatch" in e for e in payload["errors"]))

            code, payload = runCli(["validate", "--report-file", str(report_path), "--expect-ci-sha", "f" * 40])
            self.assertEqual(code, 1)
            self.assertTrue(any("stale ciHeadSha" in e for e in payload["errors"]))

            code, payload = runCli(["render", "--report-file", str(report_path), "--format", "json"])
            self.assertEqual(code, 0)
            self.assertEqual(payload["owner"], OWNER)

            code, payload = runCli(["render", "--report-file", str(report_path), "--format", "markdown"])
            self.assertEqual(code, 0)
            self.assertIn("# Worker report:", payload["text"])

            code, handoff = runCli(["handoff", "--report-file", str(report_path)])
            self.assertEqual(code, 0)
            self.assertEqual(handoff["kind"], "restart-handoff")
            self.assertEqual(handoff["source"]["claimId"], CLAIM_ID)

            code, registry_payload = runCli(["registry-payload", "--report-file", str(report_path)])
            self.assertEqual(code, 0)
            self.assertEqual(subagent_registry.validateReportPayload(registry_payload), [])

    def test_cli_error_paths(self) -> None:
        code, _ = runCli(["validate"])
        self.assertEqual(code, 2)

        with tempfile.TemporaryDirectory() as temp_dir:
            broken = Path(temp_dir) / "broken.json"
            broken.write_text("{not json", encoding="utf-8")
            code, _ = runCli(["validate", "--report-file", str(broken)])
            self.assertEqual(code, 2)

            invalid = Path(temp_dir) / "invalid.json"
            invalid.write_text(json.dumps(validReport(outcome="DONE_ISH")), encoding="utf-8")
            code, payload = runCli(["validate", "--report-file", str(invalid)])
            self.assertEqual(code, 1)
            self.assertTrue(payload["errors"])
            code, _ = runCli(["handoff", "--report-file", str(invalid)])
            self.assertEqual(code, 2)

        code, created = runCli(
            [
                "create",
                "--owner",
                "not-an-owner",
                "--claim-id",
                CLAIM_ID,
                "--issue",
                ISSUE,
                "--branch",
                BRANCH,
                "--outcome",
                "IN_PROGRESS",
                "--ci-head-sha",
                CI_SHA,
            ]
        )
        self.assertEqual(code, 1)
        self.assertFalse(created["valid"])


if __name__ == "__main__":
    unittest.main()
