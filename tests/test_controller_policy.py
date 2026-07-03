from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from scripts import controller_policy, issue_queue, subagent_registry

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = REPO_ROOT / "prompts"

# Designated files whose mechanical numbers restate the canonical policy. Every
# captured restatement must agree with scripts/controller_policy.py.
POLICY_TEXT_PATHS = (
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "docs" / "codex-agent-queue.md",
    PROMPTS_DIR / "codex-queue-controller.md",
    PROMPTS_DIR / "codex-queue-goal.txt",
    PROMPTS_DIR / "codex-workflow-optimizer.md",
)

# Files that must point at the canonical policy source so a value change is a
# one-edit change rather than a doc hunt.
POLICY_REFERENCE_PATHS = (
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "docs" / "codex-agent-queue.md",
    PROMPTS_DIR / "codex-queue-controller.md",
)

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def parseCount(token: str) -> int:
    text = token.strip().lower()
    if text.isdigit():
        return int(text)
    if text not in NUMBER_WORDS:
        raise AssertionError(f"cannot parse a count from {token!r}")
    return NUMBER_WORDS[text]


def normalizedText(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


def driftPatterns() -> list[tuple[re.Pattern[str], int]]:
    floor = controller_policy.value("controller_active_issue_floor")
    limit = controller_policy.value("controller_active_issue_limit")
    fleet = controller_policy.value("fleet_active_worker_floor")
    reclaim = controller_policy.value("reclaim_age_minutes")
    entries = [
        # Reclaim age (minutes).
        (r"reclaim age threshold is (\d+) minutes", reclaim),
        (r"default threshold is (\d+) minutes", reclaim),
        (r"(\d+)-minute (?:default|reclaim age)", reclaim),
        # Per-controller owned-slot floor/limit (equal, so "exactly this many").
        (r"exactly (\w+) (?:owned |of its own )?(?:implementation |workbook )*claim slots", floor),
        (r"more than (\w+) owned", limit),
        (r"below (?:its )?(\w+) owned", floor),
        # Global active-worker floor.
        (r"at least (\w+) live subagents", fleet),
        (r"at least (\w+) (?:active )?implementation issues", fleet),
        (r"floor of (\w+) active", fleet),
        (r"fewer than (\w+) (?:issue workers|implementation (?:issues|workers|slots))", fleet),
    ]
    return [(re.compile(pattern, re.IGNORECASE), expected) for pattern, expected in entries]


class ControllerPolicySchemaTest(unittest.TestCase):
    def test_policy_schema_validates(self) -> None:
        self.assertEqual(controller_policy.validate(), [])

    def test_schema_payload_is_json_serializable_and_complete(self) -> None:
        payload = controller_policy.schemaPayload()
        self.assertEqual(payload["schemaVersion"], controller_policy.SCHEMA_VERSION)
        # Round-trips through JSON (stdlib-only, no _game required).
        self.assertEqual(json.loads(json.dumps(payload)), payload)
        for key, field in controller_policy.POLICY.items():
            entry = payload["fields"][key]
            self.assertEqual(entry["value"], field.value)
            self.assertTrue(entry["description"], f"{key} must document a description")
        self.assertEqual(
            payload["derived"]["heartbeat_interval_minutes"],
            controller_policy.heartbeat_interval_minutes(),
        )

    def test_field_errors_detect_type_bounds_and_enum_violations(self) -> None:
        self.assertTrue(controller_policy.PolicyField(value="x", type=int, description="d").errors("k"))
        self.assertTrue(controller_policy.PolicyField(value=0, type=int, minimum=1, description="d").errors("k"))
        self.assertTrue(controller_policy.PolicyField(value=5, type=int, maximum=4, description="d").errors("k"))
        self.assertTrue(
            controller_policy.PolicyField(value="nope", type=str, enum=("a", "b"), description="d").errors("k")
        )
        # bool must not satisfy an int field even though bool subclasses int.
        self.assertTrue(controller_policy.PolicyField(value=True, type=int, description="d").errors("k"))
        # A well-formed field reports no errors.
        self.assertEqual(
            controller_policy.PolicyField(value=3, type=int, minimum=1, maximum=4, description="d").errors("k"),
            [],
        )

    def test_unknown_policy_key_raises(self) -> None:
        with self.assertRaises(controller_policy.PolicyError):
            controller_policy.value("does_not_exist")

    def test_heartbeat_interval_is_derived_and_below_reclaim_age(self) -> None:
        reclaim = controller_policy.value("reclaim_age_minutes")
        divisor = controller_policy.value("heartbeat_interval_divisor")
        interval = controller_policy.heartbeat_interval_minutes()
        self.assertEqual(interval, reclaim // divisor)
        self.assertTrue(1 <= interval < reclaim)


class DerivedConstantsTest(unittest.TestCase):
    def test_issue_queue_constants_derive_from_policy(self) -> None:
        self.assertEqual(issue_queue.DEFAULT_RECLAIM_AGE_MINUTES, controller_policy.value("reclaim_age_minutes"))
        self.assertEqual(issue_queue.DEFAULT_HEARTBEAT_INTERVAL_MINUTES, controller_policy.heartbeat_interval_minutes())
        self.assertEqual(
            issue_queue.DEFAULT_CONTROLLER_ACTIVE_ISSUE_FLOOR,
            controller_policy.value("controller_active_issue_floor"),
        )
        self.assertEqual(
            issue_queue.DEFAULT_CONTROLLER_ACTIVE_ISSUE_LIMIT,
            controller_policy.value("controller_active_issue_limit"),
        )
        self.assertEqual(issue_queue.DEFAULT_LEASE_MINUTES, controller_policy.value("default_lease_minutes"))
        self.assertEqual(
            issue_queue.DEFAULT_FLEET_ACTIVE_WORKER_FLOOR,
            controller_policy.value("fleet_active_worker_floor"),
        )
        self.assertEqual(issue_queue.TARGET_FILE_OVERLAP_POLICY, controller_policy.value("target_file_overlap_policy"))

    def test_queue_enums_match_policy(self) -> None:
        self.assertEqual(set(issue_queue.ALLOWED_STATUSES), set(controller_policy.QUEUE_STATUSES))
        self.assertEqual(tuple(issue_queue.VALID_PRIORITIES), controller_policy.QUEUE_PRIORITIES)

    def test_subagent_registry_constants_derive_from_policy(self) -> None:
        self.assertEqual(subagent_registry.DEFAULT_RETAIN_FINALIZED, controller_policy.value("finalized_retention"))
        self.assertEqual(subagent_registry.DEFAULT_STALE_AFTER_MINUTES, controller_policy.heartbeat_interval_minutes())


class PolicyDocDriftTest(unittest.TestCase):
    def test_documented_numbers_agree_with_policy(self) -> None:
        patterns = driftPatterns()
        total_matches = 0
        for path in POLICY_TEXT_PATHS:
            text = normalizedText(path)
            for pattern, expected in patterns:
                for match in pattern.finditer(text):
                    total_matches += 1
                    token = match.group(1)
                    with self.subTest(path=path.relative_to(REPO_ROOT), phrase=match.group(0)):
                        self.assertEqual(
                            parseCount(token),
                            expected,
                            f"{path.relative_to(REPO_ROOT)} restates a mechanical value that disagrees with "
                            f"scripts/controller_policy.py: {match.group(0)!r}",
                        )
        # Guard against a vacuous scan: the canonical numbers really are restated.
        self.assertGreaterEqual(total_matches, 8, "expected the designated docs to restate the policy numbers")

    def test_overlap_policy_enum_wording_is_consistent(self) -> None:
        active = controller_policy.value("target_file_overlap_policy")
        self.assertEqual(active, "advisory")
        others = [member for member in controller_policy.TARGET_FILE_OVERLAP_POLICIES if member != active]
        for path in POLICY_REFERENCE_PATHS:
            text = normalizedText(path).lower()
            with self.subTest(path=path.relative_to(REPO_ROOT)):
                self.assertIn(active, text, "the advisory overlap policy must be stated")
                for other in others:
                    for phrase in (f"overlaps are {other}", f"overlap policy is {other}"):
                        self.assertNotIn(
                            phrase,
                            text,
                            f"{path.relative_to(REPO_ROOT)} contradicts the canonical overlap policy",
                        )

    def test_docs_reference_the_canonical_policy_source(self) -> None:
        for path in POLICY_REFERENCE_PATHS:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.relative_to(REPO_ROOT)):
                self.assertIn(
                    "scripts/controller_policy.py",
                    text,
                    "each policy-restating doc must point at the canonical source",
                )


if __name__ == "__main__":
    unittest.main()
