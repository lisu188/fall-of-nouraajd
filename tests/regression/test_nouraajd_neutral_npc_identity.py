import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class NouraajdNeutralNpcIdentityTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(
            (REPO_ROOT / "res/maps/nouraajd/config.json").read_text(encoding="utf-8")
        )
        self.monsters = json.loads(
            (REPO_ROOT / "res/config/monsters.json").read_text(encoding="utf-8")
        )

    def test_neutral_nouraajd_npcs_use_non_hostile_human_template(self):
        neutral_template = self.monsters["NeutralHumanNpc"]
        properties = neutral_template["properties"]

        self.assertEqual("CCreature", neutral_template["class"])
        self.assertEqual("humanRace", properties["race"]["ref"])
        self.assertNotIn("creatureClass", properties)
        self.assertNotIn("actions", properties)
        self.assertNotIn("fightController", properties)

        for npc_id in ("questGiver", "oldWoman"):
            npc = self.config[npc_id]
            self.assertEqual("NeutralHumanNpc", npc["ref"])
            self.assertTrue(npc["properties"]["npc"])

    def test_neutral_nouraajd_npcs_do_not_reference_cultist(self):
        cultist_npcs = [
            object_id
            for object_id, entry in self.config.items()
            if entry.get("ref") == "Cultist" and entry.get("properties", {}).get("npc") is True
        ]
        self.assertEqual([], cultist_npcs)

    def test_hostile_cult_templates_keep_cultist_combat_identity(self):
        for template_id in ("Cultist", "CultLeader"):
            properties = self.monsters[template_id]["properties"]
            action_refs = [action["ref"] for action in properties["actions"]]

            self.assertEqual("humanRace", properties["race"]["ref"])
            self.assertEqual("cultistClass", properties["creatureClass"]["ref"])
            self.assertIn("Attack", action_refs)
            self.assertEqual(
                "CMonsterFightController",
                properties["fightController"]["class"],
            )


if __name__ == "__main__":
    unittest.main()
