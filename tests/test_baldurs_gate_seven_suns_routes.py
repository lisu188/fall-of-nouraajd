# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Route/API planning regressions. These are not executed MCP routes or acceptance receipts."""

import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from tests import gameplay_routes_baldurs_gate as routes
from tests.gameplay_branch_types import PLAYER_CLASSES

ROOT = Path(__file__).resolve().parents[1]


class SevenSunsWarningRoutesTest(unittest.TestCase):
    def testAllPathsAndEdgesHaveRealCasesAcrossExistingHeroes(self):
        cases = routes.sevenSunsWarningCases()
        self.assertEqual(11, len(cases))
        self.assertEqual(len(cases), len({case.id for case in cases}))
        self.assertEqual(set(PLAYER_CLASSES), {hero for case in cases for hero in case.classes})
        self.assertTrue(all(case.isolated_gui and case.group == "baldursGate" for case in cases))
        paths = {tuple(case.run.keywords["path"]) for case in cases}
        facts = json.loads((ROOT / "tests/fixtures/baldurs_gate_seven_suns_warning.json").read_text(encoding="utf-8"))
        self.assertEqual({tuple(path) for path in facts["completePathsByInitialGlobal"]["AskedForTour1"]}, paths)
        branches = {branch for case in cases for branch in case.branches}
        self.assertTrue(
            {routes.SEVEN_SUNS_WARNING_PREFIX + "edge." + str(edge) for edge in facts["reachableEdges"]}.issubset(
                branches
            )
        )
        self.assertTrue({case.id for case in cases}.issubset({case.id for case in routes.CASES}))

    def testTourAlternativeIsEarnedByRealPrefixCancelReopen(self):
        case = next(case for case in routes.sevenSunsWarningCases() if case.id.endswith("tour-cancel-reopen"))
        self.assertEqual((2, 5, 16), case.run.keywords["path"])
        self.assertTrue(case.run.keywords["prepare_tour"])
        source = ast.parse((ROOT / "tests/gameplay_routes_baldurs_gate.py").read_text(encoding="utf-8"))
        callback = next(
            node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "sevenSunsWarningRoute"
        )
        text = ast.get_source_segment(
            (ROOT / "tests/gameplay_routes_baldurs_gate.py").read_text(encoding="utf-8"), callback
        )
        self.assertIn("sevenSunsPrefixCancel(d, (1,))", text)
        self.assertIn('d.saveAndReload("city-seven-suns-before-warning")', text)
        self.assertIn('d.saveAndReload("city-seven-suns-after-warning")', text)
        self.assertIn('receipt["edges"]', text)
        self.assertIn('"getText", gui', (ROOT / "tests/gameplay_routes_baldurs_gate.py").read_text(encoding="utf-8"))

    def testRouteUsesActualDriverSurfaceAndNoProgressMutation(self):
        route_tree = ast.parse((ROOT / "tests/gameplay_routes_baldurs_gate.py").read_text(encoding="utf-8"))
        driver_tree = ast.parse((ROOT / "tests/gameplay_branch_driver.py").read_text(encoding="utf-8"))
        driver = next(
            node for node in driver_tree.body if isinstance(node, ast.ClassDef) and node.name == "GameplayBranchDriver"
        )
        methods = {node.name for node in driver.body if isinstance(node, ast.FunctionDef)}
        source = [
            node for node in route_tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith("sevenSuns")
        ]
        for callback in source:
            for node in ast.walk(callback):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "d":
                        self.assertIn(node.func.attr, methods, (callback.name, node.func.attr))
                        self.assertNotIn(node.func.attr, {"_rawCall", "engine", "tick", "step", "fight"})
                    if node.func.attr == "call" and len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                        self.assertNotIn(
                            node.args[1].value,
                            {
                                "setCoords",
                                "moveTo",
                                "setNumericProperty",
                                "setBoolProperty",
                                "setStringProperty",
                                "addQuest",
                                "addGold",
                                "addExp",
                                "addItem",
                                "addObject",
                                "removeObject",
                                "invokeAction",
                            },
                        )

    def testNewMappingsPreserveOriginalTalkAndPendingSourceObligations(self):
        branches = routes.SOURCE_BRANCHES["res/maps/baldursGate/script.py:BaldursGateDialog.talk"]
        self.assertIn("baldursGate.quest.petrineRing.complete", branches)
        self.assertIn(routes.SEVEN_SUNS_WARNING_PREFIX + "journalVisible", branches)
        pending = routes.PENDING_GAMEPLAY_OBLIGATIONS[routes.SEVEN_SUNS_WARNING_PREFIX + "nativeOwnerAcceptance"]
        self.assertEqual("partial", pending["implementationStatus"])
        self.assertIn("pending", pending["reason"])
        self.assertTrue(any(key.startswith("baldursGate.source.") for key in routes.PENDING_GAMEPLAY_OBLIGATIONS))

    def testPureChecksAreRegisteredOnceInActualFastAndFullRunner(self):
        tree = ast.parse((ROOT / "test.py").read_text(encoding="utf-8"))
        names = {"SevenSunsWarningSourceTest", "SevenSunsWarningPresentationTest", "SevenSunsWarningRoutesTest"}
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
            self.assertIn("_" + name, deleted, "Imported aliases must not duplicate full-suite discovery")
            wrappers = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == name]
            self.assertEqual(1, len(wrappers))
            self.assertEqual("_" + name, wrappers[0].bases[0].id)

    def driverChain(self, *, rows=("3", "4", "5", "6"), finish_after_prefix=False):
        """Run the actual authored driver methods against keyboard/panel doubles only."""
        tree = ast.parse((ROOT / "tests/gameplay_branch_driver.py").read_text(encoding="utf-8"))
        owner = next(
            node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "GameplayBranchDriver"
        )
        wanted = {"_chooseUiRow", "_cancelUiChoice", "_chooseUiDialogue"}
        functions = [node for node in owner.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
        namespace = {}
        exec(compile(ast.Module(body=functions, type_ignores=[]), "actual-driver-ui-methods", "exec"), namespace)
        panels = [
            {"type": "CGameCampaignPanel", "body": "Synthetic first line", "dismissed": False},
            {"type": "CGameCampaignBrowserPanel", "rows": ["0", "1", "2"], "index": 0, "chosen": False},
        ]
        if not finish_after_prefix:
            panels.extend(
                [
                    {"type": "CGameCampaignPanel", "body": "Synthetic refusal line", "dismissed": False},
                    {"type": "CGameCampaignBrowserPanel", "rows": list(rows), "index": 0, "chosen": False},
                ]
            )
        source_panel, gui = {"type": "CGameDialogPanel"}, {"type": "CGui"}
        state = {"index": 0, "keys": []}
        driver = SimpleNamespace(test=self, pump=lambda: None)

        def current():
            return panels[state["index"]] if state["index"] < len(panels) else None

        def call(owner, method, *args):
            if owner is gui and method == "getChildren":
                return [source_panel] + ([current()] if current() is not None else [])
            if method == "getType":
                return owner["type"]
            if method == "getTitle":
                return "Synthetic reader"
            if method == "getBody":
                return owner["body"]
            if method == "isDismissed":
                return owner["dismissed"]
            if method == "hasChoice":
                return owner["chosen"]
            if method == "getParent":
                return None if owner.get("dismissed") or owner.get("chosen") else gui
            if method == "getSelectedId":
                return owner["rows"][owner["index"]]
            if method != "keyboardEvent":
                raise AssertionError(("Invented driver/native method", method))
            self.assertEqual((gui, 768), args[:2])
            key = args[2]
            state["keys"].append(key)
            if owner["type"] == "CGameCampaignPanel":
                self.assertEqual(13, key)
                owner["dismissed"] = True
                state["index"] += 1
            elif key == 1073741898:
                owner["index"] = 0
            elif key == 1073741905:
                owner["index"] = (owner["index"] + 1) % len(owner["rows"])
            elif key == 1073741901:
                owner["index"] = len(owner["rows"]) - 1
            elif key in (13, 27):
                owner["chosen"] = True
                state["index"] += 1
            else:
                raise AssertionError(("Unexpected synthetic key", key))

        driver.call = call

        def nativePanel(kind, *, required=True):
            panel = current()
            result = panel if panel is not None and panel["type"] == kind else None
            if required:
                self.assertIsNotNone(result)
            return result

        driver.nativePanel = nativePanel
        for name, callback in namespace.items():
            if name in wanted:
                setattr(driver, name, callback.__get__(driver))
        return driver, gui, source_panel, state

    def testPrefixCancellationUsesRealDriverEscapeAndInspectsHiddenRows(self):
        driver, gui, source, state = self.driverChain(rows=("3", "4", "6"))
        witness = driver._chooseUiDialogue(
            gui, ["2"], source_panel=source, cancel_after_choices=True, forbidden_choice_ids=("5",)
        )
        self.assertEqual(["2"], witness["selectedIds"])
        self.assertTrue(witness["cancelled"])
        self.assertEqual(["3", "4", "6"], witness["cancelledChoiceIds"])
        self.assertEqual(27, state["keys"][-1])
        self.assertEqual(4, state["index"])

    def testUnexpectedConditionalReplyOrMissingCancelFails(self):
        driver, gui, source, _state = self.driverChain()
        with self.assertRaisesRegex(AssertionError, "Forbidden native chooser row"):
            driver._chooseUiDialogue(
                gui, ["2"], source_panel=source, cancel_after_choices=True, forbidden_choice_ids=("5",)
            )
        driver, gui, source, _state = self.driverChain(finish_after_prefix=True)
        with self.assertRaisesRegex(AssertionError, "never reached its planned cancellation"):
            driver._chooseUiDialogue(gui, ["1"], source_panel=source, cancel_after_choices=True)

    def testLegacyDialogueModeStillRejectsUnplannedChoices(self):
        driver, gui, source, _state = self.driverChain()
        with self.assertRaisesRegex(AssertionError, "Unexpected native dialogue choice"):
            driver._chooseUiDialogue(gui, ["1"], source_panel=source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
