import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class NouraajdNeutralNpcIdentityTest(unittest.TestCase):
    def test_neutral_nouraajd_npcs_do_not_inherit_cultist_identity(self):
        config = json.loads((REPO_ROOT / "res/maps/nouraajd/config.json").read_text(encoding="utf-8"))
        neutral_template = config["neutralHumanNpc"]

        self.assertEqual("CCreature", neutral_template["class"])
        self.assertEqual("humanRace", neutral_template["properties"]["race"]["ref"])
        self.assertNotIn("creatureClass", neutral_template["properties"])

        cultist_npcs = [
            object_id
            for object_id, entry in config.items()
            if entry.get("ref") == "Cultist" and entry.get("properties", {}).get("npc") is True
        ]
        self.assertEqual([], cultist_npcs)

        for npc_id in ("questGiver", "oldWoman"):
            npc = config[npc_id]
            self.assertEqual("neutralHumanNpc", npc["ref"])
            self.assertTrue(npc["properties"]["npc"])

    def test_hostile_cult_templates_keep_cultist_class(self):
        monsters = json.loads((REPO_ROOT / "res/config/monsters.json").read_text(encoding="utf-8"))

        for template_id in ("Cultist", "CultLeader"):
            properties = monsters[template_id]["properties"]
            self.assertEqual("humanRace", properties["race"]["ref"])
            self.assertEqual("cultistClass", properties["creatureClass"]["ref"])


if __name__ == "__main__":
    unittest.main()
