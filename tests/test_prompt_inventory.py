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


if __name__ == "__main__":
    unittest.main()
