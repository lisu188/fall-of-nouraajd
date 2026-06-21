from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from scripts import ci_change_classifier

REPO_ROOT = Path(__file__).resolve().parents[1]


class CiChangeClassifierTest(unittest.TestCase):
    def classify(self, *paths: str) -> ci_change_classifier.ChangeClassification:
        return ci_change_classifier.classifyPaths(paths)

    def test_workflow_python_and_docs_do_not_need_native_validation(self) -> None:
        classification = self.classify(
            ".github/workflows/build.yml",
            "scripts/pr_review_audit.py",
            "tests/test_pr_review_audit.py",
            "docs/testing.md",
            "prompts/codex-workflow-optimizer.md",
        )

        self.assertFalse(classification.nativeNeeded)
        self.assertFalse(classification.coverageNeeded)
        self.assertEqual((), classification.nativeReasons)
        self.assertIn(".github/workflows/build.yml", classification.paths)

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

            self.assertEqual("coverage-needed=true\nnative-needed=true\n", output.read_text(encoding="utf-8"))

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
            self.assertEqual({"coverage-needed": "false", "native-needed": "false"}, values)

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
