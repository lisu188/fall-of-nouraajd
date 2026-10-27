# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual route/catalog source checks, not executed MCP or accepted stock/gameplay receipts."""

import ast
from copy import deepcopy
import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests import gameplay_routes_baldurs_gate as routes
from tests.gameplay_branch_types import PLAYER_CLASSES

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "tests/gameplay_branch_driver.py"


class SevenSunsMerchantRoutesTest(unittest.TestCase):
    def testAllThirteenSourcePathsAndFourLineagesHaveRealCasesAcrossFiveHeroes(self):
        cases = routes.sevenSunsMerchantCases()
        facts = json.loads((ROOT / "tests/fixtures/baldurs_gate_seven_suns_merchants.json").read_text(encoding="utf-8"))
        paths = [case for case in cases if getattr(case.run, "func", None) is routes.sevenSunsMerchantRoute]
        self.assertEqual((17, 13), (len(cases), len(paths)))
        self.assertEqual(len(cases), len({case.id for case in cases}))
        self.assertEqual(
            {tuple(row["edges"]) for row in facts["completePaths"]},
            {tuple(case.run.keywords["path"]) for case in paths},
        )
        self.assertEqual(set(PLAYER_CLASSES), {hero for case in paths for hero in case.classes})
        self.assertEqual({row["id"] for row in facts["lineages"]}, {case.run.keywords["lineage"] for case in paths})
        self.assertTrue(all(case.isolated_gui and case.duration_seconds <= 1200 for case in cases))
        declared = {branch for case in cases for branch in case.branches}
        self.assertTrue({routes.SEVEN_SUNS_MERCHANT_PREFIX + "edge." + str(index) for index in range(24)} <= declared)
        self.assertTrue({case.id for case in cases} <= {case.id for case in routes.CASES})

    def testPrerequisitesUseNativeUiAndKeepRealThreeFloorFightRequirements(self):
        source = (ROOT / "tests/gameplay_routes_baldurs_gate.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        owner = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "QuestRoute")
        method = next(node for node in owner.body if isinstance(node, ast.FunctionDef) and node.name == "conditions")
        body = ast.get_source_segment(source, method)
        self.assertIn("merchantPrerequisiteTalk(self.d, name)", body)
        self.assertIn("merchantRevealForFloor(self.d, area_id)", body)
        self.assertIn('condition.get("clearedAreas", [])', body)
        self.assertIn("nativeVictory(self.d, name)", body)
        self.assertIn('not self.d.call(actor, "isNpc")', body)
        self.assertIn('condition.get("talked", [])', body)

    def testSettlementUsesActualMovementAndNativeTraceNeverDirectMcpIntent(self):
        source = (ROOT / "tests/gameplay_routes_baldurs_gate.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        callback = next(
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "merchantNaturalTurn"
        )
        body = ast.get_source_segment(source, callback)
        self.assertIn("d.navigateCoords", body)
        self.assertIn("readNewNativeTrace", body)
        self.assertIn('"seven_suns_merchants_settle"', body)
        for callback in (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and (node.name.startswith("merchant") or node.name.startswith("sevenSunsMerchant"))
        ):
            self.assertNotIn('"gui.settleSevenSunsMerchants"', ast.get_source_segment(source, callback))

    def testNewRoutesUseActualDriverApisWithoutProgressManufacturing(self):
        tree = ast.parse((ROOT / "tests/gameplay_routes_baldurs_gate.py").read_text(encoding="utf-8"))
        driver = next(
            node
            for node in ast.parse(DRIVER.read_text(encoding="utf-8")).body
            if isinstance(node, ast.ClassDef) and node.name == "GameplayBranchDriver"
        )
        methods = {node.name for node in driver.body if isinstance(node, ast.FunctionDef)}
        forbidden = {
            "setCoords",
            "moveTo",
            "setNumericProperty",
            "setBoolProperty",
            "setStringProperty",
            "addQuest",
            "addGold",
            "addExp",
            "addObject",
            "removeObject",
            "invokeAction",
        }
        for callback in (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and (node.name.startswith("merchant") or node.name.startswith("sevenSunsMerchant"))
        ):
            for node in ast.walk(callback):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "d"
                ):
                    self.assertIn(node.func.attr, methods, (callback.name, node.func.attr))
                    self.assertNotIn(node.func.attr, {"_rawCall", "engine", "tick", "step", "fight"})
                    if node.func.attr == "call" and len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                        self.assertNotIn(node.args[1].value, forbidden)

    def testCancellationSharedGlobalsAndCombatPersistenceAreConcreteFunctions(self):
        source = (ROOT / "tests/gameplay_routes_baldurs_gate.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = {
            node.name: ast.get_source_segment(source, node) for node in tree.body if isinstance(node, ast.FunctionDef)
        }
        self.assertIn("cancel_after_dialogue_choices=True", functions["merchantCounterRoute"])
        self.assertIn('"CheckedSevenSuns"', functions["merchantCounterRoute"])
        self.assertIn('"4", "5", "6"', functions["merchantCounterRoute"])
        self.assertIn("Committed prefix survives cancel", functions["merchantCounterRoute"])
        self.assertIn("dialogue_dialog_ids=()", functions["merchantCounterRoute"])
        self.assertIn('dialogue_choices=["1", "5"]', functions["merchantSharedGlobalRoute"])
        self.assertIn('travel(d, "AR0602")', functions["merchantScheduleRoute"])
        self.assertIn("nativeVictory(d, lineage)", functions["merchantCombatPersistenceRoute"])
        self.assertIn("actual-combat-owned-state", functions["merchantCombatPersistenceRoute"])
        self.assertNotIn("merchantStockCertificate", functions["merchantCombatPersistenceRoute"])

    def testExistingMappingsAndPendingSourceRecordsAreNotRemoved(self):
        talk = routes.SOURCE_BRANCHES["res/maps/baldursGate/script.py:BaldursGateDialog.talk"]
        self.assertIn("baldursGate.quest.petrineRing.complete", talk)
        self.assertIn("baldursGate.sevenSunsWarning.journalVisible", talk)
        clock = routes.SOURCE_BRANCHES["res/maps/baldursGate/script.py:BaldursGateClock.onTurn"]
        self.assertIn("baldursGate.travel.AR0700", clock)
        self.assertTrue(any(key.startswith("baldursGate.source.") for key in routes.PENDING_GAMEPLAY_OBLIGATIONS))
        for name in ("attackedSourceEntry", "stockAbilitiesAndClassicParity"):
            self.assertIn(routes.SEVEN_SUNS_MERCHANT_PREFIX + name, routes.PENDING_GAMEPLAY_OBLIGATIONS)

    def testOnlySourceDependentGeneratedQuestsBecomeIsolated(self):
        required = routes.sevenSunsUiQuestIds()
        self.assertEqual(
            {
                "cythandriaDiary",
                "ducalAssassins",
                "ducalPalace",
                "eltanIronThrone",
                "rescueEltan",
                "sarevokFinale",
                "scarDoppelgangers",
                "scarSevenSuns",
                "scarSewers",
                "tamokoMercy",
                "thievesMaze",
                "voletaMaze",
                "winskiMaze",
            },
            set(required),
        )
        for case in routes.generatedQuestCases():
            self.assertEqual(case.run.keywords["key"] in required, case.isolated_gui)
        self.assertFalse(any(case.isolated_gui for case in routes.generatedStoreCases()))

    def testConstructorCertificateAllowsRealPostTurnMutableOwnershipWithoutAcceptingPlaceholders(self):
        lineage = routes.SEVEN_SUNS_MERCHANT_LINEAGES[0]
        weapon = {"__handle__": "actual-weapon"}
        actor = {"__handle__": "new-doppss"}
        receipt = {
            "version": 1,
            "lineage": lineage,
            "area": "AR0601",
            "creature": "DOPPSS",
            "originalParity": False,
            "itemAbilitiesEstablished": False,
            "rolls": [{"family": "RNDTRE05", "row": 5, "column": 1, "token": "073"}],
            "outcome": {"kind": "gold", "code": "", "quantity": 0, "gold": 73, "charges": [0, 0, 0]},
            "owned": [
                {
                    "role": "weapon",
                    "name": "actualSword",
                    "resourceId": "citySevenSunsDoppssWeapon",
                    "sourceCode": "S1-12",
                    "quantity": 1,
                    "charges": [0, 0, 0],
                    "undroppable": False,
                }
            ],
            "native": {
                "hpMax": 28,
                "initialHp": 28,
                "mana": 0,
                "killXp": 420,
                "dmgMin": 1,
                "dmgMax": 12,
                "hit": 75,
                "damage": 0,
                "crit": 0,
            },
        }
        code = "S1-12"
        calls = []

        def call(owner, method, *args):
            calls.append((owner, method, args))
            if owner == actor:
                if method == "getStringProperty":
                    return "city-json:" + json.dumps(receipt)
                return {"getItems": [], "getEquipped": {"0": weapon}}[method]
            if owner == weapon:
                if method == "getStringProperty":
                    return "city-json:[0,0,0]" if args[0] == "plugin_cityCharges" else code
                return {"getName": "actualSword", "getTypeId": "citySevenSunsDoppssWeapon", "getNumericProperty": 1}[
                    method
                ]
            raise AssertionError((owner, method, args))

        driver = SimpleNamespace(test=self, call=call)
        with patch.object(routes, "currentArea", return_value="AR0601"):
            self.assertEqual(receipt, routes.merchantStockCertificate(driver, actor, lineage))
            self.assertFalse(any(method in ("getHp", "getGold") for _, method, _ in calls))
            receipt["native"]["initialHp"] = 29
            with self.assertRaises(AssertionError):
                routes.merchantStockCertificate(driver, actor, lineage)
            receipt["native"]["initialHp"] = 28
            code = "RNDTRE05"
            with self.assertRaises(AssertionError):
                routes.merchantStockCertificate(driver, actor, lineage)

    def testNaturalMovementReadsBoundedNativeCoordinatorTraceAndRejectsWrongArea(self):
        import tests.gameplay_branch_driver as branch_driver

        current = [(0, 0, 0)]
        turn = [8]
        calls = []

        def navigate(point, limit):
            calls.append((point, limit))
            current[0] = point
            turn[0] += 1

        driver = SimpleNamespace(
            test=self,
            coords=lambda: current[0],
            game_map="map",
            trace_path=Path("unused"),
            call=lambda owner, method: turn[0],
            canStep=lambda point: True,
            navigateCoords=navigate,
        )
        row = {
            "seq": 12,
            "event": "seven_suns_merchants_settle",
            "status": "settled",
            "capabilityVersion": 1,
            "turn": 9,
            "area": "AR0601",
            "checked": 2,
            "replaced": 0,
            "attackRevealSupported": False,
        }
        trace = {"positions": {}, "sequence": 11}
        with patch.object(routes, "currentArea", return_value="AR0601"), patch.object(
            routes, "cityMovementCells", return_value=({(1, 0, 0), (2, 0, 0)}, set())
        ), patch.object(branch_driver, "readNewNativeTrace", return_value=[row]):
            self.assertEqual([row], routes.merchantNaturalTurn(driver, trace))
            self.assertEqual([((1, 0, 0), 128)], calls)
            self.assertEqual(12, trace["sequence"])
            row["area"] = "AR0602"
            with self.assertRaises(AssertionError):
                routes.merchantNaturalTurn(driver, trace)

    def testSourceChecksAreRegisteredOnceInFastAndFullRunner(self):
        tree = ast.parse((ROOT / "test.py").read_text(encoding="utf-8"))
        names = {
            "SevenSunsMerchantSourceTest",
            "SevenSunsMerchantPresentationTest",
            "SevenSunsMerchantRoutesTest",
            "BaldursGateMerchantStockTest",
        }
        fast = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "FAST_TEST_PREFIXES" for target in node.targets)
        )
        deleted = {
            target.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Delete)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        for name in names:
            self.assertIn(name + ".", fast)
            self.assertIn("_" + name, deleted)
            wrappers = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == name]
            self.assertEqual(1, len(wrappers))


if __name__ == "__main__":
    unittest.main(verbosity=2)
