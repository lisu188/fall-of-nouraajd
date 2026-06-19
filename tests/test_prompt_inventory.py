from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = REPO_ROOT / "prompts"


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


if __name__ == "__main__":
    unittest.main()
