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
"""Characterization baseline for creature starter equipment and inventory.

This test pins, for every concrete creature template in ``res/config/monsters.json``,
the equipped ``slot -> item typeId`` mapping and the inventory ``item typeId -> count``
multiplicities, and compares them against a committed fixture. It protects the rule that
starter gear stays attached to the concrete creature/player-class templates (rather than
being moved into shared class definitions) and that each starter item is attached exactly
once.

The baseline is derived purely from the authoritative JSON configuration, which is the
only source of starter equipment/inventory: ``equipped`` and ``items`` are declared as
template properties in ``monsters.json`` and mapped onto ``CCreature::setEquipped`` /
``CCreature::setItems`` by the object loader. No native ``_game`` module is required, so
this test runs in the same lightweight CI step as the other content-config checks.
"""
import collections
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MONSTERS_PATH = REPO_ROOT / "res" / "config" / "monsters.json"
BASELINE_PATH = REPO_ROOT / "tests" / "fixtures" / "creature_equipment_inventory_baseline.json"
ITEM_CONFIG_PATHS = (
    REPO_ROOT / "res" / "config" / "weapons.json",
    REPO_ROOT / "res" / "config" / "armors.json",
    REPO_ROOT / "res" / "config" / "items.json",
    REPO_ROOT / "res" / "config" / "potions.json",
    REPO_ROOT / "res" / "config" / "misc.json",
)


def _ref(value):
    """Return the item typeId referenced by an equipped/inventory config entry."""
    if isinstance(value, dict):
        return value.get("ref")
    return value


def _derive_template_record(body):
    """Derive the equipped/inventory identities for a single creature template."""
    properties = body.get("properties", {}) or {}

    equipped = {}
    for slot, entry in (properties.get("equipped", {}) or {}).items():
        equipped[slot] = _ref(entry)

    inventory = collections.Counter()
    for entry in properties.get("items", []) or []:
        inventory[_ref(entry)] += 1

    return {
        "class": body.get("class"),
        "equipped": equipped,
        "inventory": dict(inventory),
    }


def derive_baseline_from_config():
    """Build the baseline mapping straight from the authoritative monsters config."""
    monsters = json.loads(MONSTERS_PATH.read_text(encoding="utf-8"))
    return {name: _derive_template_record(body) for name, body in monsters.items()}


def load_known_item_type_ids():
    known = set()
    for path in ITEM_CONFIG_PATHS:
        if not path.exists():
            continue
        known.update(json.loads(path.read_text(encoding="utf-8")).keys())
    return known


class CreatureEquipmentInventoryBaselineTest(unittest.TestCase):
    def setUp(self):
        self.derived = derive_baseline_from_config()
        fixture = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        self.baseline = fixture["templates"]

    def test_derived_baseline_matches_committed_fixture(self):
        """Every template's equipped/inventory identities match the committed baseline."""
        self.assertEqual(
            self.baseline,
            self.derived,
            "Creature equipment/inventory drifted from the committed baseline. "
            "If this change is intentional and design-approved, regenerate "
            "tests/fixtures/creature_equipment_inventory_baseline.json to match.",
        )

    def test_baseline_covers_every_template_exactly_once(self):
        """The fixture covers exactly the templates present in monsters.json."""
        self.assertEqual(
            sorted(self.baseline.keys()),
            sorted(self.derived.keys()),
            "Baseline template set differs from monsters.json template set.",
        )

    def test_each_item_is_attached_exactly_once(self):
        """No starter item identity is attached more than once per template.

        Equipped slots hold a single item each (enforced by the slot id key), and a
        starter item must not appear in both equipped and inventory, nor more than once
        across them. This is the core invariant a later archetype migration must preserve.
        """
        for name, record in self.derived.items():
            equipped_items = list(record["equipped"].values())
            inventory_counter = collections.Counter(record["inventory"])

            # Each equipped slot resolves to exactly one item typeId.
            for slot, item in record["equipped"].items():
                self.assertIsNotNone(
                    item, f"{name}: equipped slot {slot} has no item typeId"
                )

            combined = collections.Counter(equipped_items)
            combined.update(inventory_counter)
            duplicates = {item: count for item, count in combined.items() if count > 1}
            self.assertEqual(
                {},
                duplicates,
                f"{name}: starter item(s) attached more than once: {duplicates}",
            )

    def test_concrete_creature_templates_carry_no_starter_gear(self):
        """class CCreature monster templates carry no equipped/inventory items.

        Starter gear currently lives on the class CPlayer templates only. This pins the
        characterized baseline so a migration cannot silently attach gear to, or strip
        gear from, the concrete CCreature monsters.
        """
        for name, record in self.derived.items():
            if record["class"] == "CCreature":
                self.assertEqual({}, record["equipped"], f"{name}: unexpected equipped gear")
                self.assertEqual({}, record["inventory"], f"{name}: unexpected inventory")

    def test_referenced_starter_items_resolve_to_known_type_ids(self):
        """Every equipped/inventory item typeId resolves to a defined item config."""
        known = load_known_item_type_ids()
        for name, record in self.derived.items():
            for slot, item in record["equipped"].items():
                self.assertIn(
                    item,
                    known,
                    f"{name}: equipped slot {slot} references unknown item typeId {item!r}",
                )
            for item in record["inventory"]:
                self.assertIn(
                    item,
                    known,
                    f"{name}: inventory references unknown item typeId {item!r}",
                )


if __name__ == "__main__":
    unittest.main()
