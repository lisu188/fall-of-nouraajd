import ast
import copy
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def loadCanonicalizer():
    source_path = REPO_ROOT / "test.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    function_names = {
        "normalize_save_snapshot",
        "normalize_generated_save_names",
        "normalize_map_load_provenance",
        "canonicalizeEffectActorIds",
        "canonical_save_round_trip_form",
    }
    constant_names = {
        "SAVE_GENERATED_NAME_PATTERN",
        "SAVE_GENERATED_NAME_PLACEHOLDER",
        "SAVE_SLOT_IDENTITY_PREFIX",
        "SAVE_SLOT_IDENTITY_PLACEHOLDER",
        "SAVE_MAP_PROVENANCE_PLACEHOLDER",
    }
    selected = [
        node
        for node in tree.body
        if (isinstance(node, ast.FunctionDef) and node.name in function_names)
        or (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id in constant_names for target in node.targets)
        )
    ]
    namespace = {"json": json, "re": re}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source_path), "exec"), namespace)
    return namespace["canonical_save_round_trip_form"]


def makeGraph():
    def actor(actor_id, name, x):
        return {
            "class": "CCreature",
            "effectActorId": actor_id,
            "properties": {"name": name, "posx": x, "hp": 10},
        }

    player = actor(7, "player", 1)
    player["properties"]["effects"] = [
        {
            "class": "CEffect",
            "effectReferences": {"caster": 12, "victim": 7},
            "properties": {"name": "ward", "timeLeft": 3},
        },
        {
            "class": "CEffect",
            "effectReferences": {"caster": 20, "victim": 7},
            "properties": {"name": "aura", "timeLeft": 2},
        },
    ]
    return {
        "snapshot": {
            "class": "CMap",
            "effectGraph": {"version": 1, "actors": [actor(20, "departed", 3)]},
            "properties": {
                "objects": [player, actor(12, "caster", 2)],
                "trackedActor": {"class": "CCreature", "effectActorReference": 12},
                "effectActorId": 100,
                "effectActorReference": 101,
                "effectReferences": {"caster": 102, "victim": 103},
            },
        }
    }


def relabelAndReverse(value, labels):
    if isinstance(value, dict):
        result = {key: relabelAndReverse(item, labels) for key, item in reversed(list(value.items()))}
        if isinstance(value.get("class"), str):
            for key in ("effectActorId", "effectActorReference"):
                if key in value:
                    result[key] = labels[value[key]]
            if "effectReferences" in value:
                result["effectReferences"] = {
                    key: labels[item] if item is not None else None for key, item in value["effectReferences"].items()
                }
        return result
    if isinstance(value, list):
        return [relabelAndReverse(item, labels) for item in reversed(value)]
    return value


class SaveEffectCanonicalizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonicalize = staticmethod(loadCanonicalizer())

    def testEquivalentReorderedAndRenumberedGraph(self):
        original = makeGraph()
        reordered = relabelAndReverse(original, {7: 90, 12: 2, 20: 1})
        self.assertEqual(self.canonicalize(original), self.canonicalize(reordered))

    def testCasterVictimAndAliasChangesRemainObservable(self):
        original = makeGraph()
        for field in ("caster", "victim", "alias"):
            with self.subTest(field=field):
                changed = copy.deepcopy(original)
                if field == "alias":
                    changed["snapshot"]["properties"]["trackedActor"]["effectActorReference"] = 20
                else:
                    effect = changed["snapshot"]["properties"]["objects"][0]["properties"]["effects"][0]
                    effect["effectReferences"][field] = 20
                self.assertNotEqual(self.canonicalize(original), self.canonicalize(changed))

    def testInputAndMetadataLookingRealPropertiesRemainUnchanged(self):
        original = makeGraph()
        before = copy.deepcopy(original)
        normalized = self.canonicalize(original)
        self.assertEqual(before, original)
        properties = normalized["snapshot"]["properties"]
        self.assertEqual(100, properties["effectActorId"])
        self.assertEqual(101, properties["effectActorReference"])
        self.assertEqual({"caster": 102, "victim": 103}, properties["effectReferences"])

    def testIdenticalActorsWithDistinctReferenceContextsRemainDistinct(self):
        original = makeGraph()
        actors = original["snapshot"]["properties"]["objects"]
        twin = copy.deepcopy(actors[1])
        twin["effectActorId"] = 25
        actors.append(twin)
        original["snapshot"]["properties"]["otherActor"] = {"class": "CCreature", "effectActorReference": 25}
        reordered = relabelAndReverse(original, {7: 90, 12: 2, 20: 1, 25: 18})
        canonical = self.canonicalize(original)
        self.assertEqual(canonical, self.canonicalize(reordered))
        properties = canonical["snapshot"]["properties"]
        self.assertNotEqual(
            properties["trackedActor"]["effectActorReference"], properties["otherActor"]["effectActorReference"]
        )
        changed = copy.deepcopy(original)
        changed["snapshot"]["properties"]["otherActor"]["effectActorReference"] = 12
        self.assertNotEqual(canonical, self.canonicalize(changed))

    def testIndistinguishableActorsFailExplicitlyWithoutConflatingThem(self):
        original = {
            "class": "CMap",
            "effectGraph": {"version": 1, "actors": []},
            "properties": {
                "objects": [
                    {"class": "CCreature", "effectActorId": actor_id, "properties": {"name": "same"}}
                    for actor_id in (5, 8)
                ]
            },
        }
        before = copy.deepcopy(original)
        with self.assertRaisesRegex(ValueError, "Ambiguous effect actor identities"):
            self.canonicalize(original)
        self.assertEqual(before, original)


if __name__ == "__main__":
    unittest.main()
