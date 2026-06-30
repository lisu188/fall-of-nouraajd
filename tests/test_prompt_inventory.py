from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = REPO_ROOT / "prompts"
WORKFLOW_TEXT_PATHS = (
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "docs" / "codex-agent-queue.md",
    REPO_ROOT / "docs" / "testing.md",
    PROMPTS_DIR / "codex-queue-controller.md",
    PROMPTS_DIR / "codex-queue-goal.txt",
    PROMPTS_DIR / "codex-workflow-optimizer.md",
    PROMPTS_DIR / "codex-workflow-optimizer-goal.txt",
)
OBSERVATION_POLICY_TEXT_PATHS = (
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "docs" / "codex-agent-queue.md",
    REPO_ROOT / "docs" / "codex-workflow-observations.md",
    PROMPTS_DIR / "codex-queue-controller.md",
    PROMPTS_DIR / "codex-queue-goal.txt",
)


class PromptInventoryTest(unittest.TestCase):
    def test_text_prompts_are_goal_launchers_with_existing_prompt_references(self) -> None:
        prompt_paths = sorted(PROMPTS_DIR.glob("*.txt"))

        self.assertTrue(prompt_paths, "expected at least one prompt goal launcher")
        for prompt_path in prompt_paths:
            text = prompt_path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("/goal "), f"{prompt_path} should be a /goal launcher")

            referenced_prompts = re.findall(r"prompts/[A-Za-z0-9_.-]+\.md", text)
            self.assertTrue(referenced_prompts, f"{prompt_path} should reference an authoritative markdown prompt")
            for referenced_prompt in referenced_prompts:
                self.assertTrue((REPO_ROOT / referenced_prompt).exists(), f"{referenced_prompt} should exist")

    def test_bug_finder_prompt_files_bugs_through_the_propose_command(self) -> None:
        prompt_path = PROMPTS_DIR / "codex-bug-finder.md"
        goal_path = PROMPTS_DIR / "codex-bug-finder-goal.txt"
        self.assertTrue(prompt_path.exists(), "bug-finder prompt should exist")
        self.assertTrue(goal_path.exists(), "bug-finder goal launcher should exist")

        prompt = prompt_path.read_text(encoding="utf-8")
        goal = goal_path.read_text(encoding="utf-8")

        self.assertTrue(goal.startswith("/goal "), "goal launcher should be a /goal launcher")
        self.assertIn("prompts/codex-bug-finder.md", goal, "goal should launch the bug-finder prompt")
        self.assertIn(
            "scripts/issue_queue.py propose",
            prompt,
            "the bug-finder must file issues through the propose command",
        )
        for required_flag in ("--issue-name", "--priority", "--component", "--target-file"):
            self.assertIn(
                required_flag,
                prompt,
                f"the bug-finder prompt should document the {required_flag} propose argument",
            )
        # A bug finder must reproduce and deduplicate before filing, not speculate.
        self.assertIn("reproduc", prompt.lower())
        self.assertRegex(prompt.lower(), r"duplicat")

    def test_queue_prompts_do_not_reintroduce_stale_lease_reclaim_drift(self) -> None:
        banned_patterns = {
            r"when\s+the\s+lease\s+is\s+near\s+expiry": "heartbeats must use the derived heartbeat deadline",
            r"even\s+if\s+(?:their|the)\s+lease\s+is\s+still\s+in\s+the\s+future": (
                "future leases must protect ownership from ordinary reclaim"
            ),
        }
        for path in WORKFLOW_TEXT_PATHS:
            text = path.read_text(encoding="utf-8").lower()
            for pattern, reason in banned_patterns.items():
                with self.subTest(path=path.relative_to(REPO_ROOT), pattern=pattern):
                    self.assertIsNone(re.search(pattern, text), reason)

    def test_workflow_prompts_do_not_default_to_linux_only_pr_polling(self) -> None:
        for path in WORKFLOW_TEXT_PATHS:
            lines = path.read_text(encoding="utf-8").splitlines()
            for line_number, line in enumerate(lines, start=1):
                if "poll_pr_checks.py" not in line or "--check linux" not in line:
                    continue
                explicit_all_platforms = "--check windows-deps" in line and "--check windows" in line
                with self.subTest(path=path.relative_to(REPO_ROOT), line=line_number):
                    self.assertTrue(
                        explicit_all_platforms,
                        "ordinary PR polling should use the path-selected default, not a Linux-only command",
                    )

    def test_pr_audit_policy_documents_auto_merge_blockers(self) -> None:
        combined = "\n".join(path.read_text(encoding="utf-8") for path in WORKFLOW_TEXT_PATHS).lower()

        self.assertIn("automergeerror", combined)
        self.assertIn("automergerequest.error", combined)
        self.assertIn("merge_policy_blocked", combined)
        self.assertIn("explicit alternate merge authorization", combined)

    def test_implementation_pr_auto_merge_is_not_an_unconditional_default(self) -> None:
        # Implementation-PR auto-merge must require explicit, repo-verified authorization. Guard against
        # regression to the old opt-out wording that forced auto-merge unless the user opted out, and require
        # the four-state authorization vocabulary to remain documented somewhere in the workflow text.
        banned_patterns = {
            r"--auto\s+--squash`?\s+unless\s+the\s+user\s+explicitly\s+asks\s+not\s+to": (
                "implementation-PR auto-merge must not be framed as an opt-out default"
            ),
            r"run\s+`gh\s+pr\s+merge\s+<pr_number>\s+--auto\s+--squash`\s+unless": (
                "implementation-PR auto-merge must not be framed as an opt-out default"
            ),
        }
        for path in WORKFLOW_TEXT_PATHS:
            text = path.read_text(encoding="utf-8").lower()
            for pattern, reason in banned_patterns.items():
                with self.subTest(path=path.relative_to(REPO_ROOT), pattern=pattern):
                    self.assertIsNone(re.search(pattern, text), reason)

        combined = "\n".join(path.read_text(encoding="utf-8") for path in WORKFLOW_TEXT_PATHS).lower()
        self.assertIn(
            "auto-merge for implementation prs is not an unconditional default",
            combined,
            "implementation-PR auto-merge must be documented as requiring explicit, repo-verified authorization",
        )
        for state in ("allowed", "user-authorized", "disallowed", "unknown"):
            self.assertIn(
                state,
                combined,
                f"the implementation-PR auto-merge authorization state '{state}' must remain documented",
            )

    def test_queue_controller_observation_policy_is_direct_and_append_only(self) -> None:
        combined = "\n".join(path.read_text(encoding="utf-8") for path in OBSERVATION_POLICY_TEXT_PATHS).lower()

        self.assertIn(
            "each queue controller may publish controller-discovered workflow observations directly", combined
        )
        self.assertIn("workers, qa, and project-manager agents report observations to their controller", combined)
        self.assertIn("do not edit or delete existing records or receipts", combined)
        self.assertIn("record-only prs add only files under `planning/workflow_observations/records/`", combined)
        self.assertIn(
            "resolution-only prs add only files under `planning/workflow_observations/resolutions/`",
            combined,
        )
        self.assertIn("never mix ledger files with xlsx", combined)


if __name__ == "__main__":
    unittest.main()
