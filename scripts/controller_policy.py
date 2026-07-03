#!/usr/bin/env python3
"""One canonical, stdlib-only source of the mechanical controller policy.

Mechanical policy values -- controller capacity floors/limits, the global
active-worker floor, heartbeat cadence, lease durations, the target-file overlap
policy, finalized-record retention, and the queue status/priority enums -- used
to be restated across ``scripts/issue_queue.py``, controller prompts, and docs.
Changing one value therefore meant hunting down every duplicate, and stale
restatements silently contradicted the real behavior.

This module is the single authoritative definition. Every field carries a value,
a Python type, inclusive numeric bounds, an optional legal-enum set, and a short
description, and :func:`validate` checks types, bounds, enums, and the cross-field
relationships (for example ``controller_active_issue_limit`` must be at least
``controller_active_issue_floor`` and the derived heartbeat interval must stay
below the reclaim age). ``scripts/issue_queue.py`` and
``scripts/subagent_registry.py`` derive their legacy constants and CLI defaults
from here, so public behavior is unchanged and one edit updates every consumer.

The module deliberately imports nothing from the rest of the repository (only the
standard library), so it loads without the ``_game`` extension, has no import
cycle with the queue scripts that consume it, and can be validated first in fast
CI before the queue/prompt tests run.

Exit codes: 0 the policy schema is valid, 1 the policy schema is invalid.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Sequence

SCHEMA_VERSION = 1


class PolicyError(RuntimeError):
    """Raised for invalid policy access or an invalid policy schema."""


@dataclass(frozen=True)
class PolicyField:
    """One validated mechanical-policy value with its schema metadata."""

    value: Any
    type: type
    description: str
    minimum: float | None = None
    maximum: float | None = None
    enum: tuple[Any, ...] | None = None

    def errors(self, key: str) -> list[str]:
        problems: list[str] = []
        # bool is a subclass of int; keep the two kinds distinct on purpose.
        if isinstance(self.value, bool) != (self.type is bool):
            problems.append(f"{key}: value {self.value!r} is not of type {self.type.__name__}")
            return problems
        if not isinstance(self.value, self.type):
            problems.append(f"{key}: value {self.value!r} is not of type {self.type.__name__}")
            return problems
        if self.enum is not None and self.value not in self.enum:
            problems.append(f"{key}: value {self.value!r} is not one of {list(self.enum)}")
        if isinstance(self.value, (int, float)) and not isinstance(self.value, bool):
            if self.minimum is not None and self.value < self.minimum:
                problems.append(f"{key}: value {self.value!r} is below minimum {self.minimum}")
            if self.maximum is not None and self.value > self.maximum:
                problems.append(f"{key}: value {self.value!r} is above maximum {self.maximum}")
        return problems


# Canonical queue enums. These are the machine-checkable status and priority
# vocabularies; the queue scripts derive their working constants from them.
QUEUE_STATUSES: tuple[str, ...] = (
    "NOT_STARTED",
    "IN_PROGRESS",
    "BLOCKED",
    "DONE",
    "FAILED",
    "CANCELLED",
)
QUEUE_PRIORITIES: tuple[str, ...] = ("P0", "P1", "P2")
TARGET_FILE_OVERLAP_POLICIES: tuple[str, ...] = ("advisory", "blocking")


POLICY: dict[str, PolicyField] = {
    "reclaim_age_minutes": PolicyField(
        value=240,
        type=int,
        minimum=1,
        maximum=100000,
        description=(
            "Minutes a claim's last heartbeat and lease must both be past before a stale IN_PROGRESS row "
            "becomes timing-eligible for reclaim (recovery threshold)."
        ),
    ),
    "heartbeat_interval_divisor": PolicyField(
        value=2,
        type=int,
        minimum=1,
        maximum=240,
        description=(
            "Divisor applied to reclaim_age_minutes to derive the persisted heartbeat interval, so the "
            "heartbeat deadline is always shorter than the reclaim age (default: half the reclaim age)."
        ),
    ),
    "default_lease_minutes": PolicyField(
        value=120,
        type=int,
        minimum=1,
        maximum=100000,
        description="Default lease duration in minutes granted or renewed by claim/heartbeat CLI defaults.",
    ),
    "controller_active_issue_floor": PolicyField(
        value=4,
        type=int,
        minimum=0,
        maximum=1000,
        description=(
            "Minimum healthy implementation claims one controller keeps under its own owner prefix while "
            "status-and-dependency eligible work exists."
        ),
    ),
    "controller_active_issue_limit": PolicyField(
        value=4,
        type=int,
        minimum=0,
        maximum=1000,
        description=(
            "Maximum unresolved implementation claims one controller owns at once; equal to the floor means "
            "'exactly this many' owned slots."
        ),
    ),
    "fleet_active_worker_floor": PolicyField(
        value=8,
        type=int,
        minimum=0,
        maximum=1000,
        description=(
            "Global active-worker floor: live subagents and active implementation issues the controller keeps "
            "whenever that many status-and-dependency eligible issues exist."
        ),
    ),
    "finalized_retention": PolicyField(
        value=50,
        type=int,
        minimum=0,
        maximum=100000,
        description="Newest FINALIZED subagent-registry records retained after finalization pruning.",
    ),
    "target_file_overlap_policy": PolicyField(
        value="advisory",
        type=str,
        enum=TARGET_FILE_OVERLAP_POLICIES,
        description=(
            "How declared target-file overlaps affect claiming: 'advisory' surfaces overlaps as coordination "
            "metadata only and never blocks eligibility."
        ),
    ),
}


def value(key: str) -> Any:
    """Return the canonical value for ``key`` or raise on an unknown key."""

    if key not in POLICY:
        raise PolicyError(f"Unknown policy key: {key!r}")
    return POLICY[key].value


def describe(key: str) -> PolicyField:
    if key not in POLICY:
        raise PolicyError(f"Unknown policy key: {key!r}")
    return POLICY[key]


def heartbeat_interval_minutes() -> int:
    """Derived persisted heartbeat interval: reclaim age divided by the divisor."""

    return int(value("reclaim_age_minutes")) // int(value("heartbeat_interval_divisor"))


def crossFieldErrors() -> list[str]:
    problems: list[str] = []
    floor = value("controller_active_issue_floor")
    limit = value("controller_active_issue_limit")
    if limit < floor:
        problems.append(f"controller_active_issue_limit ({limit}) must be >= controller_active_issue_floor ({floor})")
    fleet = value("fleet_active_worker_floor")
    if fleet < floor:
        problems.append(f"fleet_active_worker_floor ({fleet}) must be >= controller_active_issue_floor ({floor})")
    interval = heartbeat_interval_minutes()
    reclaim = value("reclaim_age_minutes")
    if not 1 <= interval < reclaim:
        problems.append(
            f"derived heartbeat interval ({interval}) must be >= 1 and strictly below reclaim_age_minutes ({reclaim})"
        )
    return problems


def enumErrors() -> list[str]:
    problems: list[str] = []
    for name, members in (
        ("QUEUE_STATUSES", QUEUE_STATUSES),
        ("QUEUE_PRIORITIES", QUEUE_PRIORITIES),
        ("TARGET_FILE_OVERLAP_POLICIES", TARGET_FILE_OVERLAP_POLICIES),
    ):
        if not members:
            problems.append(f"{name}: must declare at least one member")
        if len(set(members)) != len(members):
            problems.append(f"{name}: must not contain duplicate members")
        if any(not isinstance(member, str) or not member for member in members):
            problems.append(f"{name}: members must be non-empty strings")
    if value("target_file_overlap_policy") not in TARGET_FILE_OVERLAP_POLICIES:
        problems.append("target_file_overlap_policy value must be a member of TARGET_FILE_OVERLAP_POLICIES")
    return problems


def validate() -> list[str]:
    """Validate every field's type/bounds/enum plus the cross-field relationships."""

    problems: list[str] = []
    for key, policyField in POLICY.items():
        problems.extend(policyField.errors(key))
    problems.extend(enumErrors())
    problems.extend(crossFieldErrors())
    return problems


def schemaPayload() -> dict[str, Any]:
    """A JSON-serializable snapshot of the whole policy, for inspection or export."""

    return {
        "schemaVersion": SCHEMA_VERSION,
        "fields": {
            key: {
                "value": policyField.value,
                "type": policyField.type.__name__,
                "minimum": policyField.minimum,
                "maximum": policyField.maximum,
                "enum": list(policyField.enum) if policyField.enum is not None else None,
                "description": policyField.description,
            }
            for key, policyField in POLICY.items()
        },
        "derived": {"heartbeat_interval_minutes": heartbeat_interval_minutes()},
        "enums": {
            "queueStatuses": list(QUEUE_STATUSES),
            "queuePriorities": list(QUEUE_PRIORITIES),
            "targetFileOverlapPolicies": list(TARGET_FILE_OVERLAP_POLICIES),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    problems = validate()
    print(json.dumps({"valid": not problems, "errors": problems, "policy": schemaPayload()}, indent=2, sort_keys=True))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
