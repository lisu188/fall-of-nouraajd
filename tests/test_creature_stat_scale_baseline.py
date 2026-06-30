# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Characterization baseline for creature stat scaling and levelling.

This test pins, for every concrete creature/player template in
``res/config/monsters.json``, the config-declared per-template balance fields that
are deterministic from configuration alone:

* ``class`` (CCreature / CPlayer),
* ``sw`` (spawn weight, when declared),
* ``baseStats`` (the absolute combat scale a creature spawns with),
* ``levelStats`` (the per-level stat growth increments), and
* ``levelling`` (the level -> skill reference unlock map).

These values drive creature balance and are read straight from the authoritative
JSON config by the object loader; none of them require the native ``_game`` engine.
Anything that can only be produced by a runtime engine pass (e.g. computed effective
stat totals, generated object names, memory addresses, runtime spawn coordinates, or
order-sensitive set iteration) is deliberately excluded so the fixture is stable
across repeated runs. The baseline is a balance-neutral contract: a migration PR that
reshapes how these templates are defined must regenerate it deliberately, and an
accidental balance change fails this test with a useful diff.

The baseline is derived purely from config, so this test runs in the same lightweight
CI step as the other content-config checks; no native ``_game`` module is required.
"""

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MONSTERS_PATH = REPO_ROOT / "res" / "config" / "monsters.json"
BASELINE_PATH = REPO_ROOT / "tests" / "fixtures" / "creature_stat_scale_baseline.json"


def _ref(value):
    """Return the typeId referenced by a ``{"ref": ...}`` config entry."""
    if isinstance(value, dict):
        return value.get("ref")
    return value


def _normalize_stats(block):
    """Return the declared stat map for a ``CStats`` property node, sorted by key.

    Only the declared ``properties`` payload is kept; the ``class`` wrapper is dropped
    because it is a constant loader detail, not a balance value. Values are returned as
    a plain dict; JSON serialization with ``sort_keys=True`` provides the canonical,
    order-insensitive ordering.
    """
    if not isinstance(block, dict):
        return {}
    return dict(block.get("properties", {}) or {})


def _normalize_levelling(levelling):
    """Return the level -> skill-ref unlock map, keyed by string level.

    Levels are JSON object keys (strings); each value is normalized to the referenced
    skill typeId. Iteration order of the source object is irrelevant because the result
    is compared as a dict and serialized with ``sort_keys=True``.
    """
    result = {}
    for level, entry in (levelling or {}).items():
        result[str(level)] = _ref(entry)
    return result


def _derive_template_record(body):
    """Derive the config-declared balance fields for a single creature template."""
    properties = body.get("properties", {}) or {}

    record = {
        "class": body.get("class"),
        "baseStats": _normalize_stats(properties.get("baseStats")),
        "levelStats": _normalize_stats(properties.get("levelStats")),
        "levelling": _normalize_levelling(properties.get("levelling")),
    }
    if "sw" in properties:
        record["sw"] = properties["sw"]
    return record


def derive_baseline_from_config():
    """Build the normalized baseline mapping straight from the monsters config."""
    monsters = json.loads(MONSTERS_PATH.read_text(encoding="utf-8"))
    return {name: _derive_template_record(body) for name, body in monsters.items()}


class CreatureStatScaleBaselineTest(unittest.TestCase):
    def setUp(self):
        self.derived = derive_baseline_from_config()
        fixture = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        self.baseline = fixture["templates"]

    def test_derived_baseline_matches_committed_fixture(self):
        """Every template's stat-scale identities match the committed baseline."""
        self.assertEqual(
            self.baseline,
            self.derived,
            "Creature stat scaling/levelling drifted from the committed baseline. "
            "If this change is intentional and design-approved, regenerate "
            "tests/fixtures/creature_stat_scale_baseline.json to match.",
        )

    def test_baseline_covers_every_template_exactly_once(self):
        """The fixture covers exactly the templates present in monsters.json."""
        self.assertEqual(
            sorted(self.baseline.keys()),
            sorted(self.derived.keys()),
            "Baseline template set differs from monsters.json template set.",
        )

    def test_baseline_is_stable_across_repeated_derivations(self):
        """Re-deriving the baseline yields an identical canonical serialization.

        This guards the normalization: object-key order in the source config must not
        leak into the result, so two independent derivations must serialize byte-for-byte
        identically under ``sort_keys=True``.
        """
        first = json.dumps(derive_baseline_from_config(), sort_keys=True)
        second = json.dumps(derive_baseline_from_config(), sort_keys=True)
        self.assertEqual(first, second)

    def test_intentional_balance_change_is_detected(self):
        """A mutated stat value is detected against the committed baseline.

        This is the drift sanity check: perturbing any baseline number in memory must
        make the fixture comparison fail, proving the contract catches balance changes.
        """
        mutated = json.loads(json.dumps(self.baseline))
        name = sorted(mutated.keys())[0]
        base_stats = mutated[name]["baseStats"]
        if base_stats:
            key = sorted(base_stats.keys())[0]
            value = base_stats[key]
            base_stats[key] = (value + 1) if isinstance(value, (int, float)) else "DRIFTED"
        else:
            mutated[name]["class"] = "DRIFTED"
        self.assertNotEqual(
            mutated,
            self.derived,
            "Mutating a baseline value must be detectable as drift.",
        )


if __name__ == "__main__":
    unittest.main()
