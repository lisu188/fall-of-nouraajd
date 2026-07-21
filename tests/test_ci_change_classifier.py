from __future__ import annotations

import io
import json
import os
import subprocess
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
            "scripts/validate_content.py",
            "tests/test_content_validator.py",
            "docs/testing.md",
            "AGENTS.md",
        )

        self.assertFalse(classification.nativeNeeded)
        self.assertFalse(classification.coverageNeeded)
        self.assertFalse(classification.authorityChange)
        self.assertEqual((), classification.nativeReasons)
        self.assertIn("scripts/validate_content.py", classification.paths)

    def test_coverage_report_unit_test_routes_as_lightweight(self) -> None:
        classification = self.classify("tests/test_coverage_report.py")

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
                "coverage-needed=true\nnative-needed=true\nauthority-change=false\nhuman-review-required=false\n"
                "coverage-relevant=true\nnative-gui=true\nnative-engine=false\ncontent-json-python=false\n"
                "workflow-python=false\nprompts-docs=false\n",
                output.read_text(encoding="utf-8"),
            )

    def test_cli_outputs_json_for_explicit_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "github-output"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exitCode = ci_change_classifier.main(
                    ["--path", "scripts/validate_content.py", "--github-output", str(output)]
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
                    "coverage-relevant": "false",
                    "native-gui": "false",
                    "native-engine": "false",
                    "content-json-python": "false",
                    "workflow-python": "true",
                    "prompts-docs": "false",
                },
                values,
            )

    def test_kind_taxonomy_partitions_representative_paths(self) -> None:
        booleans = (
            "nativeGui",
            "nativeEngine",
            "contentJsonPython",
            "workflowPython",
            "promptsDocs",
            "coverageRelevant",
        )
        matrix = {
            "docs/testing.md": {"promptsDocs"},
            "AGENTS.md": {"promptsDocs"},
            ".github/workflows/other.yml": {"workflowPython"},
            "scripts/validate_content.py": {"workflowPython"},
            "scripts/run_coverage.sh": {"workflowPython", "coverageRelevant"},
            "res/config/monsters.json": {"contentJsonPython"},
            "res/maps/nouraajd/script.py": {"contentJsonPython"},
            "src/gui/panel/CListView.cpp": {"nativeGui", "coverageRelevant"},
            "src/gui/CAnimation.cpp": {"nativeGui", "coverageRelevant"},
            "src/core/CGame.cpp": {"nativeEngine", "coverageRelevant"},
            "native_plugins/foo.cpp": {"nativeEngine", "coverageRelevant"},
            "tests/unit/test_core.cpp": {"nativeEngine", "coverageRelevant"},
        }
        for path, expected in matrix.items():
            with self.subTest(path=path):
                classification = ci_change_classifier.classifyPaths([path])
                actual = {name for name in booleans if getattr(classification, name)}
                self.assertEqual(expected, actual)

    def test_every_gui_descendant_requires_native_and_coverage(self) -> None:
        for path in (
            "src/gui/CAnimation.cpp",
            "src/gui/panel/CListView.cpp",
            "src/gui/widget/deep/nested/Foo.cpp",
        ):
            with self.subTest(path=path):
                classification = ci_change_classifier.classifyPaths([path])
                self.assertTrue(classification.nativeGui)
                self.assertTrue(classification.coverageRelevant)
                self.assertTrue(classification.coverageNeeded)
                self.assertTrue(classification.nativeNeeded)

    def test_mixed_diff_unions_kinds_and_validation_needs(self) -> None:
        classification = ci_change_classifier.classifyPaths(
            ["src/gui/CAnimation.cpp", "docs/x.md", "res/config/monsters.json"]
        )
        self.assertTrue(classification.nativeGui)
        self.assertTrue(classification.promptsDocs)
        self.assertTrue(classification.contentJsonPython)
        self.assertTrue(classification.nativeNeeded)
        self.assertTrue(classification.coverageNeeded)

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

    def test_classifier_changes_are_authority_changes(self) -> None:
        for path in ("scripts/ci_change_classifier.py",):
            with self.subTest(path=path):
                classification = self.classify(path)
                self.assertTrue(classification.authorityChange)
                self.assertTrue(classification.nativeNeeded)
                self.assertTrue(classification.coverageNeeded)
                self.assertTrue(classification.humanReviewRequired)

    def test_auto_merge_workflow_and_policy_are_authority_changes(self) -> None:
        for path in (".github/workflows/auto-merge.yml", "scripts/auto_merge_policy.py"):
            with self.subTest(path=path):
                classification = self.classify(path)
                self.assertTrue(classification.authorityChange)
                self.assertTrue(classification.nativeNeeded)
                self.assertTrue(classification.coverageNeeded)
                self.assertTrue(classification.humanReviewRequired)
                self.assertEqual((path,), classification.authorityPaths)

    def test_authority_change_cannot_self_classify_as_lightweight(self) -> None:
        # A PR that only edits the routing/classifier logic must not be able
        # to claim a lightweight (linux-only, no-coverage) validation class.
        classification = self.classify("scripts/ci_change_classifier.py", "docs/testing.md")

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

    def test_changed_paths_ignores_files_merged_into_base_after_branch_point(self) -> None:
        def run_git(repo: Path, *args: str) -> str:
            return subprocess.run(
                ["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            ).stdout.strip()

        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            run_git(repo, "init", "-b", "main")
            run_git(repo, "config", "user.email", "test@example.invalid")
            run_git(repo, "config", "user.name", "Classifier Test")
            (repo / "docs").mkdir()
            (repo / "docs" / "testing.md").write_text("base\n", encoding="utf-8")
            run_git(repo, "add", "docs/testing.md")
            run_git(repo, "commit", "-m", "base")

            # Lightweight docs-only PR branch.
            run_git(repo, "checkout", "-b", "pr")
            (repo / "docs" / "testing.md").write_text("changed\n", encoding="utf-8")
            run_git(repo, "add", "docs/testing.md")
            run_git(repo, "commit", "-m", "lightweight docs change")
            pr_head = run_git(repo, "rev-parse", "HEAD")

            # The base branch advances with an unrelated native C++ file merged after
            # the branch point.
            run_git(repo, "checkout", "main")
            (repo / "src").mkdir()
            (repo / "src" / "CGame.cpp").write_text("int x;\n", encoding="utf-8")
            run_git(repo, "add", "src/CGame.cpp")
            run_git(repo, "commit", "-m", "concurrent native merge on base")
            advanced_base = run_git(repo, "rev-parse", "HEAD")

            old_cwd = Path.cwd()
            try:
                os.chdir(repo)
                paths = ci_change_classifier.changedPaths(advanced_base, pr_head)
            finally:
                os.chdir(old_cwd)

        # Only the PR's own file is reported; the concurrently merged src/CGame.cpp
        # must not be swept in and force native/coverage classification.
        self.assertEqual(("docs/testing.md",), paths)
        self.assertFalse(ci_change_classifier.classifyPaths(paths).nativeNeeded)

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
