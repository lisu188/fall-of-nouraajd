from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import ci_change_classifier

REPO_ROOT = Path(__file__).resolve().parents[1]


class CiChangeClassifierTest(unittest.TestCase):
    def classify(self, *paths: str) -> ci_change_classifier.ChangeClassification:
        return ci_change_classifier.classifyPaths(paths)

    def test_non_authority_python_and_docs_do_not_need_native_validation(self) -> None:
        classification = self.classify(
            ".github/workflows/release.yml",
            "scripts/pr_review_audit.py",
            "tests/test_pr_review_audit.py",
            "docs/testing.md",
            "prompts/codex-workflow-optimizer.md",
        )

        self.assertFalse(classification.nativeNeeded)
        self.assertFalse(classification.coverageNeeded)
        self.assertFalse(classification.authorityChange)
        self.assertEqual((), classification.nativeReasons)
        self.assertIn("scripts/pr_review_audit.py", classification.paths)

    def test_workflow_observation_ledger_json_does_not_need_native_validation(self) -> None:
        classification = self.classify(
            "planning/workflow_observations/records/20260621T120000Z-controller-example-1234abcd.json",
            "planning/workflow_observations/resolutions/20260621T120000Z-controller-example-1234abcd.json",
        )

        self.assertFalse(classification.nativeNeeded)
        self.assertFalse(classification.coverageNeeded)
        self.assertEqual((), classification.nativeReasons)

    def test_temporary_multi_workbook_transport_paths_do_not_need_native_validation(self) -> None:
        classification = self.classify(
            ".github/multi-workbook-inspection.txt",
            ".github/multi-workbook-payload/patch.xz.b64",
            ".github/workflows/apply-multi-workbook-workflow.yml",
        )

        self.assertFalse(classification.nativeNeeded)
        self.assertFalse(classification.coverageNeeded)
        self.assertEqual((), classification.nativeReasons)

    def test_gui_cpp_requires_native_and_coverage_validation(self) -> None:
        classification = self.classify("src/gui/panel/CListView.cpp")

        self.assertTrue(classification.nativeNeeded)
        self.assertTrue(classification.coverageNeeded)
        self.assertIn("coverage-relevant paths", classification.nativeReasons)
        self.assertIn("src/gui/panel/CListView.cpp", classification.nativeReasons)

    def test_native_core_and_unit_test_paths_require_coverage(self) -> None:
        for path in ("src/core/CGame.cpp", "src/handler/CFightHandler.cpp", "tests/unit/test_gui.cpp"):
            with self.subTest(path=path):
                classification = self.classify(path)
                self.assertTrue(classification.nativeNeeded)
                self.assertTrue(classification.coverageNeeded)

    def test_content_and_unknown_paths_fail_closed_to_native_validation(self) -> None:
        for path in ("res/maps/nouraajd/script.py", "requirements-dev.txt"):
            with self.subTest(path=path):
                classification = self.classify(path)
                self.assertTrue(classification.nativeNeeded)
                self.assertFalse(classification.coverageNeeded)

        self.assertIn("unclassified:requirements-dev.txt", self.classify("requirements-dev.txt").nativeReasons)

    def test_force_native_preserves_push_validation_policy(self) -> None:
        classification = ci_change_classifier.classifyPaths(["docs/testing.md"], forceNative=True)

        self.assertTrue(classification.nativeNeeded)
        self.assertFalse(classification.coverageNeeded)
        self.assertIn("forced", classification.nativeReasons)

    def test_github_output_writes_booleans(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "github-output"
            classification = self.classify("src/gui/CListView.cpp")

            ci_change_classifier.writeGithubOutput(output, classification)

            self.assertEqual(
                "coverage-needed=true\nnative-needed=true\nauthority-change=false\nhuman-review-required=false\n",
                output.read_text(encoding="utf-8"),
            )

    def test_cli_outputs_json_for_explicit_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "github-output"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exitCode = ci_change_classifier.main(
                    ["--path", "scripts/pr_review_audit.py", "--github-output", str(output)]
                )

            self.assertEqual(0, exitCode)
            payload = json.loads(stdout.getvalue())
            self.assertFalse(payload["coverageNeeded"])
            self.assertFalse(payload["nativeNeeded"])
            values = dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines())
            self.assertEqual(
                {
                    "coverage-needed": "false",
                    "native-needed": "false",
                    "authority-change": "false",
                    "human-review-required": "false",
                },
                values,
            )

    def test_main_returns_clean_error_when_git_executable_is_missing(self) -> None:
        def raise_missing_git(*_args: object, **_kwargs: object) -> None:
            raise FileNotFoundError(2, "No such file or directory", "git")

        stderr = io.StringIO()
        with patch.object(ci_change_classifier.subprocess, "run", side_effect=raise_missing_git):
            with redirect_stderr(stderr):
                exitCode = ci_change_classifier.main(["--base", "a", "--head", "b"])

        self.assertEqual(2, exitCode)
        self.assertIn("git executable not found on PATH", stderr.getvalue())

    def test_build_workflow_change_forces_native_coverage_and_human_review(self) -> None:
        classification = self.classify(".github/workflows/build.yml")

        self.assertTrue(classification.authorityChange)
        self.assertTrue(classification.nativeNeeded)
        self.assertTrue(classification.coverageNeeded)
        self.assertTrue(classification.humanReviewRequired)
        self.assertIn("ci-authority change", classification.nativeReasons)
        self.assertEqual((".github/workflows/build.yml",), classification.authorityPaths)

    def test_poller_and_classifier_changes_are_authority_changes(self) -> None:
        for path in ("scripts/poll_pr_checks.py", "scripts/ci_change_classifier.py"):
            with self.subTest(path=path):
                classification = self.classify(path)
                self.assertTrue(classification.authorityChange)
                self.assertTrue(classification.nativeNeeded)
                self.assertTrue(classification.coverageNeeded)
                self.assertTrue(classification.humanReviewRequired)

    def test_authority_change_cannot_self_classify_as_lightweight(self) -> None:
        # A PR that only edits the routing/poller/classifier logic must not be able
        # to claim a lightweight (linux-only, no-coverage) validation class.
        classification = self.classify("scripts/poll_pr_checks.py", "docs/testing.md")

        self.assertTrue(classification.nativeNeeded)
        self.assertTrue(classification.coverageNeeded)
        self.assertTrue(classification.humanReviewRequired)

    def test_authority_change_reported_in_github_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "github-output"
            classification = self.classify("scripts/ci_change_classifier.py")

            ci_change_classifier.writeGithubOutput(output, classification)

            values = dict(
                line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines()
            )
            self.assertEqual("true", values["authority-change"])
            self.assertEqual("true", values["human-review-required"])
            self.assertEqual("true", values["native-needed"])
            self.assertEqual("true", values["coverage-needed"])

    def test_build_workflow_uses_classifier_outputs_for_native_routing(self) -> None:
        workflow = (REPO_ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")

        self.assertIn("coverage-needed: ${{ steps.change-classification.outputs.coverage-needed }}", workflow)
        self.assertIn("native-needed: ${{ steps.change-classification.outputs.native-needed }}", workflow)
        self.assertIn("python3 scripts/ci_change_classifier.py", workflow)
        self.assertIn("force_native=(--force-native)", workflow)
        self.assertIn("if: needs.linux-fast.outputs.native-needed != 'true'", workflow)
        self.assertIn("if: needs.linux-fast.outputs.native-needed == 'true'", workflow)


if __name__ == "__main__":
    unittest.main()
