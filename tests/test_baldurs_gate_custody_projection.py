# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Execute selected actual projection/protection nodes over the bounded custody fixture only."""

import ast
from copy import deepcopy
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def selectedDefinitions(tree, names, constants=()):
    selected = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            selected.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in constants for target in node.targets
        ):
            selected.append(node)
    if len([node for node in selected if isinstance(node, ast.FunctionDef)]) != len(names):
        raise ValueError("Selected pure helper missing or duplicated")
    return ast.Module(body=selected, type_ignores=[])


def actualNodes():
    tree = ast.parse((ROOT / "scripts/build_baldurs_gate_city.py").read_bytes())
    city = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "compileCity")
    appends = [
        node
        for node in ast.walk(city)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "append"
        and isinstance(node.value.func.value, ast.Name)
        and node.value.func.value.id == "actor_definitions"
    ]
    assert len(appends) == 1
    clock_values = [
        node.value for node in ast.walk(city) if isinstance(node, ast.keyword) and node.arg == "actorDefinitions"
    ]
    geometry_values = [
        value
        for node in ast.walk(city)
        if isinstance(node, ast.Dict)
        for key, value in zip(node.keys, node.values)
        if isinstance(key, ast.Constant) and key.value == "scriptedActorPlacements"
    ]
    config_loops = [
        node
        for node in ast.walk(city)
        if isinstance(node, ast.For)
        and isinstance(node.iter, ast.Tuple)
        and [item.value for item in node.iter.elts if isinstance(item, ast.Constant)] == ["custodyRole", "patrolArea"]
    ]
    assert len(clock_values) == len(geometry_values) == len(config_loops) == 1
    namespace = {"json": json}
    exec(
        compile(
            selectedDefinitions(
                tree, {"protectCityData", "protectCityDefinitions", "definition"}, {"CITY_JSON_PREFIX"}
            ),
            "selected_definition_helpers",
            "exec",
        ),
        namespace,
    )
    return appends[0], clock_values[0], geometry_values[0], config_loops[0], namespace


def projected(actor, policy=None):
    append, _, _, _, _ = actualNodes()
    namespace = {
        "actor": actor,
        "policy": policy or {"phase": 7},
        "actor_definitions": [],
        "name": actor.get("nativeId", "ordinaryActor"),
        "area_id": "AR0607",
        "position": [10, 11, 3],
    }
    exec(compile(ast.Module(body=[append], type_ignores=[]), "selected_actual_actor_projection", "exec"), namespace)
    return namespace["actor_definitions"][0]


class BaldursGateCustodyRoleSourceTest(unittest.TestCase):
    def testOrdinaryScriptedRowsHaveNoEmptyCustodyRole(self):
        for extra in ({}, {"custodyRole": ""}, {"custodyRole": None}):
            with self.subTest(extra=extra):
                row = projected({"creature": "ORDINARY", **extra})
                self.assertEqual(
                    {
                        "id": "ordinaryActor",
                        "sourceCreature": "ORDINARY",
                        "sourceArea": "AR0607",
                        "x": 10,
                        "y": 11,
                        "z": 3,
                        "phase": 7,
                    },
                    row,
                )

    def testAllBoundedCustodyRolesAndExistingNebAreRetained(self):
        helper = ast.parse((ROOT / "scripts/build_baldurs_gate_city_custody.py").read_bytes())
        namespace = {}
        exec(
            compile(
                selectedDefinitions(
                    helper,
                    {"patrolIds", "identity", "namedActorIds", "sceneSpawn", "prepareCustodyActors"},
                    {"DISTRICTS", "ANGELO_ID", "ESCORT_IDS"},
                ),
                "selected_actual_custody_preparation",
                "exec",
            ),
            namespace,
        )
        audit = json.loads((ROOT / "tests/fixtures/baldurs_gate_city_prison_source.json").read_bytes())
        source = {
            "areas": {area: {"actors": []} for area in (*namespace["DISTRICTS"], "AR0607")},
            "creatures": {name: {} for name in ("FFHUNT", "ANGELO", "FLAME1", "FLAME2", "FLAME3", "FLAME4")},
        }
        source["areas"]["AR0607"]["actors"] = deepcopy(audit["prison"]["actors"])
        namespace["prepareCustodyActors"](source, audit)
        additions = [actor for area in source["areas"].values() for actor in area["actors"] if actor.get("nativeId")]
        self.assertEqual(23, len(additions))
        self.assertEqual({"patrol", "angelo", "escort"}, {actor["custodyRole"] for actor in additions})
        for actor in additions:
            row = projected(actor, actor["scriptedPolicy"])
            self.assertEqual(actor["custodyRole"], row["custodyRole"])
        neb = next(actor for actor in source["areas"]["AR0607"]["actors"] if actor["creature"] == "NEB")
        self.assertEqual("neb", neb["custodyRole"])
        _, _, _, config_loop, _ = actualNodes()
        for actor in [neb, *additions]:
            data = {"actor": actor, "props": {}}
            exec(
                compile(ast.Module(body=[config_loop], type_ignores=[]), "selected_actual_config_properties", "exec"),
                data,
            )
            self.assertEqual(actor["custodyRole"], data["props"]["custodyRole"])

    def testActualClockAndGeometryProjectionsShareExactRefinedRows(self):
        _, clock_value, geometry_value, _, namespace = actualNodes()
        rows = [projected({"creature": "ORDINARY"}), projected({"creature": "FFHUNT", "custodyRole": "patrol"})]
        namespace["actor_definitions"] = rows
        encoded = eval(compile(ast.Expression(clock_value), "selected_actual_clock_projection", "eval"), namespace)
        geometry = eval(
            compile(ast.Expression(geometry_value), "selected_actual_geometry_projection", "eval"), namespace
        )
        document = namespace["definition"]("CEvent", actorDefinitions=encoded)
        namespace["protectCityDefinitions"](document)
        protected = document["properties"]["actorDefinitions"]
        self.assertTrue(protected.startswith("city-json:"))
        self.assertEqual(rows, json.loads(protected.removeprefix("city-json:")))
        self.assertIs(rows, geometry)
        self.assertNotIn("custodyRole", geometry[0])
        self.assertEqual("patrol", geometry[1]["custodyRole"])

    def testExistingRuntimeTreatsMissingAndEmptyRolesAsOrdinary(self):
        source = ast.parse((ROOT / "res/maps/baldursGate/script.py").read_bytes())
        spawn = [node for node in ast.walk(source) if isinstance(node, ast.FunctionDef) and node.name == "spawnActors"]
        self.assertEqual(1, len(spawn))
        guards = [
            node
            for node in ast.walk(spawn[0])
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Call)
            and isinstance(node.test.func, ast.Attribute)
            and node.test.func.attr == "get"
            and node.test.args
            and isinstance(node.test.args[0], ast.Constant)
            and node.test.args[0].value == "custodyRole"
        ]
        self.assertEqual(1, len(guards))
        for row, custody in (({}, False), ({"custodyRole": ""}, False), ({"custodyRole": "patrol"}, True)):
            value = eval(compile(ast.Expression(guards[0].test), "selected_actual_spawn_guard", "eval"), {"row": row})
            self.assertEqual(custody, bool(value))


if __name__ == "__main__":
    unittest.main()
