from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import auto_merge_policy

REPO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "owner/repository"
RUN_ID = 9876
PR_NUMBER = 321
HEAD_SHA = "a" * 40


def evidence() -> tuple[dict[str, object], dict[str, object]]:
    association = {
        "url": f"https://api.github.invalid/repos/{REPOSITORY}/pulls/{PR_NUMBER}",
        "id": 123456,
        "number": PR_NUMBER,
        "head": {"ref": "feature", "sha": HEAD_SHA, "repo": {"id": 1001, "url": "https://api.github.invalid"}},
        "base": {"ref": "main", "sha": "b" * 40, "repo": {"id": 1001, "url": "https://api.github.invalid"}},
    }
    event = {
        "action": "completed",
        "repository": {"full_name": REPOSITORY, "default_branch": "main"},
        "workflow_run": {
            "id": RUN_ID,
            "head_sha": HEAD_SHA,
            "repository": {"full_name": REPOSITORY},
            # The real workflow_run association supplies a number and API URL,
            # not an html_url.  The policy must never depend on html_url.
            "pull_requests": [copy.deepcopy(association)],
        },
    }
    run = {
        "id": RUN_ID,
        "name": "build",
        "path": ".github/workflows/build.yml",
        "status": "completed",
        "conclusion": "success",
        "event": "pull_request",
        "head_sha": HEAD_SHA,
        "repository": {"full_name": REPOSITORY},
        "pull_requests": [copy.deepcopy(association)],
    }
    return event, run


def pullRequest(*, changedFiles: int = 1) -> dict[str, object]:
    return {
        "number": PR_NUMBER,
        "state": "open",
        "draft": False,
        "changed_files": changedFiles,
        "base": {"ref": "main", "repo": {"full_name": REPOSITORY}},
        "head": {"sha": HEAD_SHA, "repo": {"full_name": REPOSITORY}},
    }


class FakeApi:
    def __init__(
        self,
        run: dict[str, object],
        *,
        pr: dict[str, object] | None = None,
        files: list[dict[str, object]] | None = None,
        settings: dict[str, object] | None = None,
        branch: dict[str, object] | None = None,
        protection: dict[str, object] | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.responses: dict[str, object] = {
            f"repos/{REPOSITORY}/actions/runs/{RUN_ID}": run,
            f"repos/{REPOSITORY}/pulls/{PR_NUMBER}": pr or pullRequest(),
            f"repos/{REPOSITORY}/pulls/{PR_NUMBER}/files?per_page=100&page=1": (
                files if files is not None else [{"filename": "docs/readme.md", "status": "modified"}]
            ),
            f"repos/{REPOSITORY}": (
                settings
                if settings is not None
                else {"full_name": REPOSITORY, "default_branch": "main", "allow_auto_merge": True}
            ),
            f"repos/{REPOSITORY}/branches/main": branch if branch is not None else {"name": "main", "protected": True},
            f"repos/{REPOSITORY}/branches/main/protection": (
                protection
                if protection is not None
                else {
                    "required_status_checks": {
                        "strict": True,
                        "contexts": ["linux", "windows-deps", "windows"],
                        "checks": [],
                    }
                }
            ),
        }

    def __call__(self, path: str) -> object:
        self.calls.append(path)
        if path not in self.responses:
            raise auto_merge_policy.ApiError(path, "fixture has no response")
        return copy.deepcopy(self.responses[path])


class AutoMergePolicyTest(unittest.TestCase):
    def evaluate(
        self,
        *,
        event: dict[str, object] | None = None,
        run: dict[str, object] | None = None,
        api: FakeApi | None = None,
    ) -> auto_merge_policy.PolicyResult:
        defaultEvent, defaultRun = evidence()
        return auto_merge_policy.evaluatePolicy(
            event or defaultEvent,
            REPOSITORY,
            api or FakeApi(run or defaultRun),
        )

    def test_real_association_without_html_url_is_allowed(self) -> None:
        result = self.evaluate()

        self.assertTrue(result.allow)
        self.assertEqual(PR_NUMBER, result.prNumber)
        self.assertEqual("allowed", result.reason)

    def test_absent_or_multiple_pr_associations_are_unverifiable(self) -> None:
        for associations in ([], [{"number": PR_NUMBER}, {"number": PR_NUMBER + 1}]):
            with self.subTest(count=len(associations)):
                event, _run = evidence()
                event["workflow_run"]["pull_requests"] = associations  # type: ignore[index]
                with self.assertRaisesRegex(auto_merge_policy.EvidenceError, "associations") as caught:
                    self.evaluate(event=event)
                self.assertEqual("pr_association_count_not_one", caught.exception.reason)

    def test_refetched_association_must_match_event(self) -> None:
        event, run = evidence()
        run["pull_requests"] = [{"number": PR_NUMBER + 1}]

        with self.assertRaises(auto_merge_policy.EvidenceError) as caught:
            self.evaluate(event=event, run=run)

        self.assertEqual("workflow_identity_unverifiable", caught.exception.reason)

    def test_wrong_action_event_repository_or_workflow_identity_is_denied(self) -> None:
        event, run = evidence()
        cases = []
        wrongAction = copy.deepcopy(event)
        wrongAction["action"] = "requested"
        cases.append((wrongAction, run, "workflow_not_completed"))
        wrongRepo = copy.deepcopy(event)
        wrongRepo["repository"]["full_name"] = "other/repository"  # type: ignore[index]
        cases.append((wrongRepo, run, "event_repository_mismatch"))
        wrongWorkflowEvent = copy.deepcopy(run)
        wrongWorkflowEvent["event"] = "push"
        cases.append((event, wrongWorkflowEvent, "workflow_event_not_pull_request"))
        wrongWorkflow = copy.deepcopy(run)
        wrongWorkflow["name"] = "release"
        cases.append((event, wrongWorkflow, "workflow_identity_mismatch"))
        for eventPayload, runPayload, reason in cases:
            with self.subTest(reason=reason):
                result = self.evaluate(event=eventPayload, run=runPayload)
                self.assertFalse(result.allow)
                self.assertEqual(reason, result.reason)

    def test_wrong_refetched_run_path_or_repository_is_denied(self) -> None:
        event, run = evidence()
        wrongPath = copy.deepcopy(run)
        wrongPath["path"] = ".github/workflows/release.yml"
        wrongRepository = copy.deepcopy(run)
        wrongRepository["repository"]["full_name"] = "other/repository"  # type: ignore[index]
        for payload, reason in (
            (wrongPath, "workflow_identity_mismatch"),
            (wrongRepository, "workflow_repository_mismatch"),
        ):
            with self.subTest(reason=reason):
                result = self.evaluate(event=event, run=payload)
                self.assertFalse(result.allow)
                self.assertEqual(reason, result.reason)

    def test_incomplete_or_unsuccessful_refetched_run_is_denied(self) -> None:
        event, run = evidence()
        for field, value, reason in (
            ("status", "in_progress", "workflow_not_completed"),
            ("conclusion", "failure", "workflow_not_successful"),
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(run)
                changed[field] = value
                result = self.evaluate(event=event, run=changed)
                self.assertEqual(reason, result.reason)

    def test_event_and_refetched_head_sha_must_match(self) -> None:
        event, run = evidence()
        run["head_sha"] = "b" * 40

        with self.assertRaises(auto_merge_policy.EvidenceError) as caught:
            self.evaluate(event=event, run=run)

        self.assertEqual("workflow_identity_unverifiable", caught.exception.reason)

    def test_closed_and_draft_prs_are_denied(self) -> None:
        event, run = evidence()
        for field, value, reason in (
            ("state", "closed", "pr_not_open"),
            ("draft", True, "pr_is_draft"),
        ):
            with self.subTest(field=field):
                pr = pullRequest()
                pr[field] = value
                result = self.evaluate(event=event, api=FakeApi(run, pr=pr))
                self.assertEqual(reason, result.reason)

    def test_wrong_base_or_fork_is_denied(self) -> None:
        event, run = evidence()
        cases: list[tuple[dict[str, object], str]] = []
        wrongBase = pullRequest()
        wrongBase["base"]["ref"] = "release"  # type: ignore[index]
        cases.append((wrongBase, "pr_base_not_main"))
        baseFork = pullRequest()
        baseFork["base"]["repo"]["full_name"] = "fork/repository"  # type: ignore[index]
        cases.append((baseFork, "pr_base_repository_mismatch"))
        headFork = pullRequest()
        headFork["head"]["repo"]["full_name"] = "fork/repository"  # type: ignore[index]
        cases.append((headFork, "pr_head_repository_mismatch"))
        for pr, reason in cases:
            with self.subTest(reason=reason):
                result = self.evaluate(event=event, api=FakeApi(run, pr=pr))
                self.assertEqual(reason, result.reason)

    def test_stale_pr_head_sha_is_denied(self) -> None:
        event, run = evidence()
        pr = pullRequest()
        pr["head"]["sha"] = "b" * 40  # type: ignore[index]

        result = self.evaluate(event=event, api=FakeApi(run, pr=pr))

        self.assertEqual("pr_head_sha_mismatch", result.reason)

    def test_disabled_auto_merge_is_denied(self) -> None:
        event, run = evidence()
        api = FakeApi(
            run,
            settings={"full_name": REPOSITORY, "default_branch": "main", "allow_auto_merge": False},
        )

        result = self.evaluate(event=event, api=api)

        self.assertEqual("auto_merge_disabled", result.reason)

    def test_default_branch_must_be_main(self) -> None:
        event, run = evidence()
        api = FakeApi(
            run,
            settings={"full_name": REPOSITORY, "default_branch": "develop", "allow_auto_merge": True},
        )

        result = self.evaluate(event=event, api=api)

        self.assertEqual("default_branch_not_main", result.reason)

    def test_unprotected_or_non_strict_main_is_denied(self) -> None:
        event, run = evidence()
        unprotected = FakeApi(run, branch={"name": "main", "protected": False})
        result = self.evaluate(event=event, api=unprotected)
        self.assertEqual("main_not_protected", result.reason)

        nonStrict = FakeApi(
            run,
            protection={
                "required_status_checks": {"strict": False, "contexts": list(auto_merge_policy.REQUIRED_CONTEXTS)}
            },
        )
        result = self.evaluate(event=event, api=nonStrict)
        self.assertEqual("required_checks_not_strict", result.reason)

        noStatusChecks = FakeApi(run, protection={"required_status_checks": None})
        result = self.evaluate(event=event, api=noStatusChecks)
        self.assertEqual("required_checks_not_strict", result.reason)

    def test_required_contexts_can_come_from_contexts_and_checks(self) -> None:
        event, run = evidence()
        protection = {
            "required_status_checks": {
                "strict": True,
                "contexts": ["linux"],
                "checks": [{"context": "windows-deps", "app_id": 1}, {"context": "windows", "app_id": 1}],
            }
        }

        result = self.evaluate(event=event, api=FakeApi(run, protection=protection))

        self.assertTrue(result.allow)

    def test_missing_required_context_is_denied(self) -> None:
        event, run = evidence()
        protection = {"required_status_checks": {"strict": True, "contexts": ["linux", "windows"], "checks": []}}

        result = self.evaluate(event=event, api=FakeApi(run, protection=protection))

        self.assertEqual("required_contexts_missing", result.reason)

    def test_malformed_contexts_or_checks_are_unverifiable(self) -> None:
        event, run = evidence()
        for statusChecks in (
            {"strict": True, "contexts": "linux", "checks": []},
            {"strict": True, "contexts": [], "checks": [{"context": None}]},
            {"strict": True, "contexts": []},
        ):
            with self.subTest(statusChecks=statusChecks):
                protection = {"required_status_checks": statusChecks}
                with self.assertRaises(auto_merge_policy.EvidenceError) as caught:
                    self.evaluate(event=event, api=FakeApi(run, protection=protection))
                self.assertEqual("malformed_evidence", caught.exception.reason)

    def test_authority_file_on_second_page_is_denied(self) -> None:
        event, run = evidence()
        firstPage = [{"filename": f"docs/file-{index}.md"} for index in range(100)]
        api = FakeApi(run, pr=pullRequest(changedFiles=101), files=firstPage)
        api.responses[f"repos/{REPOSITORY}/pulls/{PR_NUMBER}/files?per_page=100&page=2"] = [
            {"filename": "scripts/auto_merge_policy.py"}
        ]

        result = self.evaluate(event=event, api=api)

        self.assertEqual("authority_change", result.reason)

    def test_rename_from_authority_file_is_denied(self) -> None:
        event, run = evidence()
        files = [{"filename": "scripts/renamed_policy.py", "previous_filename": ".github/workflows/auto-merge.yml"}]

        result = self.evaluate(event=event, api=FakeApi(run, files=files))

        self.assertEqual("authority_change", result.reason)

    def test_changed_file_count_mismatch_is_unverifiable(self) -> None:
        event, run = evidence()
        api = FakeApi(run, pr=pullRequest(changedFiles=2))

        with self.assertRaises(auto_merge_policy.EvidenceError) as caught:
            self.evaluate(event=event, api=api)

        self.assertEqual("changed_files_count_mismatch", caught.exception.reason)

    def test_malformed_api_response_is_unverifiable(self) -> None:
        event, run = evidence()
        api = FakeApi(run)
        api.responses[f"repos/{REPOSITORY}/pulls/{PR_NUMBER}"] = []

        with self.assertRaises(auto_merge_policy.EvidenceError) as caught:
            self.evaluate(event=event, api=api)

        self.assertEqual("malformed_evidence", caught.exception.reason)

    def runCli(
        self,
        event: object,
        api: FakeApi,
    ) -> tuple[int, dict[str, str], str]:
        with tempfile.TemporaryDirectory() as tempDir:
            eventPath = Path(tempDir) / "event.json"
            outputPath = Path(tempDir) / "output"
            eventPath.write_text(json.dumps(event), encoding="utf-8")
            stderr = io.StringIO()
            with patch.object(auto_merge_policy.GhApi, "get", side_effect=api):
                with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
                    exitCode = auto_merge_policy.main(
                        [
                            "--event",
                            str(eventPath),
                            "--repository",
                            REPOSITORY,
                            "--github-output",
                            str(outputPath),
                        ]
                    )
            outputs = dict(line.split("=", 1) for line in outputPath.read_text(encoding="utf-8").splitlines())
            return exitCode, outputs, stderr.getvalue()

    def test_cli_writes_allowed_outputs_and_exits_zero(self) -> None:
        event, run = evidence()

        exitCode, outputs, stderr = self.runCli(event, FakeApi(run))

        self.assertEqual(0, exitCode)
        self.assertEqual({"allow": "true", "pr_number": str(PR_NUMBER), "reason": "allowed"}, outputs)
        self.assertEqual("", stderr)

    def test_cli_policy_denial_writes_outputs_and_exits_zero(self) -> None:
        event, run = evidence()
        pr = pullRequest()
        pr["draft"] = True

        exitCode, outputs, stderr = self.runCli(event, FakeApi(run, pr=pr))

        self.assertEqual(0, exitCode)
        self.assertEqual("false", outputs["allow"])
        self.assertEqual(str(PR_NUMBER), outputs["pr_number"])
        self.assertEqual("pr_is_draft", outputs["reason"])
        self.assertEqual("", stderr)

    def test_cli_malformed_event_writes_outputs_and_exits_nonzero(self) -> None:
        _event, run = evidence()

        exitCode, outputs, stderr = self.runCli([], FakeApi(run))

        self.assertEqual(2, exitCode)
        self.assertEqual({"allow": "false", "pr_number": "", "reason": "malformed_event"}, outputs)
        self.assertIn("event must be an object", stderr)

    def test_cli_api_failure_writes_outputs_and_exits_nonzero(self) -> None:
        event, run = evidence()
        api = FakeApi(run)
        del api.responses[f"repos/{REPOSITORY}/actions/runs/{RUN_ID}"]

        exitCode, outputs, stderr = self.runCli(event, api)

        self.assertEqual(2, exitCode)
        self.assertEqual("false", outputs["allow"])
        self.assertEqual("api_error", outputs["reason"])
        self.assertIn("fixture has no response", stderr)

    def test_cli_malformed_decision_fields_exit_nonzero(self) -> None:
        event, baselineRun = evidence()
        cases: list[tuple[str, FakeApi]] = []
        for field, value in (
            ("name", None),
            ("path", []),
            ("status", None),
            ("conclusion", None),
            ("event", 7),
        ):
            run = copy.deepcopy(baselineRun)
            run[field] = value
            cases.append((f"run-{field}", FakeApi(run)))

        for field, value in (("state", None), ("draft", "false")):
            pr = pullRequest()
            pr[field] = value
            cases.append((f"pr-{field}", FakeApi(baselineRun, pr=pr)))
        pr = pullRequest()
        pr["base"]["ref"] = None  # type: ignore[index]
        cases.append(("pr-base-ref", FakeApi(baselineRun, pr=pr)))
        cases.append(
            (
                "protection-strict",
                FakeApi(
                    baselineRun,
                    protection={"required_status_checks": {"contexts": [], "checks": []}},
                ),
            )
        )

        for name, api in cases:
            with self.subTest(name=name):
                exitCode, outputs, stderr = self.runCli(event, api)
                self.assertEqual(2, exitCode)
                self.assertEqual("false", outputs["allow"])
                self.assertIn(outputs["reason"], ("malformed_evidence", "branch_protection_unverifiable"))
                self.assertTrue(stderr)

    def test_cli_missing_action_or_draft_exits_nonzero(self) -> None:
        event, run = evidence()
        missingAction = copy.deepcopy(event)
        del missingAction["action"]
        missingDraft = pullRequest()
        del missingDraft["draft"]

        for name, eventPayload, api in (
            ("action", missingAction, FakeApi(run)),
            ("draft", event, FakeApi(run, pr=missingDraft)),
        ):
            with self.subTest(name=name):
                exitCode, outputs, stderr = self.runCli(eventPayload, api)
                self.assertEqual(2, exitCode)
                self.assertEqual("false", outputs["allow"])
                self.assertEqual("malformed_evidence", outputs["reason"])
                self.assertTrue(stderr)

    def test_gh_api_timeout_is_unverifiable(self) -> None:
        with patch.object(
            auto_merge_policy.subprocess,
            "run",
            side_effect=auto_merge_policy.subprocess.TimeoutExpired(["gh", "api"], 30),
        ):
            with self.assertRaises(auto_merge_policy.ApiError) as caught:
                auto_merge_policy.GhApi().get("repos/owner/repository")

        self.assertEqual("api_error", caught.exception.reason)
        self.assertIn("timed out after 30 seconds", str(caught.exception))

    def test_cli_timeout_writes_api_error_and_exits_nonzero(self) -> None:
        event, _run = evidence()
        with tempfile.TemporaryDirectory() as tempDir:
            eventPath = Path(tempDir) / "event.json"
            outputPath = Path(tempDir) / "output"
            eventPath.write_text(json.dumps(event), encoding="utf-8")
            with patch.object(
                auto_merge_policy.subprocess,
                "run",
                side_effect=auto_merge_policy.subprocess.TimeoutExpired(["gh", "api"], 30),
            ):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    exitCode = auto_merge_policy.main(
                        [
                            "--event",
                            str(eventPath),
                            "--repository",
                            REPOSITORY,
                            "--github-output",
                            str(outputPath),
                        ]
                    )

            outputs = dict(line.split("=", 1) for line in outputPath.read_text(encoding="utf-8").splitlines())
            self.assertEqual(2, exitCode)
            self.assertEqual("false", outputs["allow"])
            self.assertEqual("api_error", outputs["reason"])

    def test_workflow_uses_trusted_policy_and_explicit_merge_identity(self) -> None:
        workflow = (REPO_ROOT / ".github/workflows/auto-merge.yml").read_text(encoding="utf-8")

        self.assertIn("actions: read", workflow)
        self.assertIn("actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0", workflow)
        self.assertIn("ref: ${{ github.event.repository.default_branch }}", workflow)
        self.assertIn("python3 scripts/auto_merge_policy.py", workflow)
        self.assertIn("if: steps.policy.outputs.allow == 'true'", workflow)
        self.assertIn('gh pr merge --auto --squash "$PR_NUMBER"', workflow)
        self.assertIn('--repo "$REPOSITORY"', workflow)
        self.assertIn('--match-head-commit "$HEAD_SHA"', workflow)
        self.assertNotIn("html_url", workflow)
        self.assertNotIn("git ", workflow)


if __name__ == "__main__":
    unittest.main()
