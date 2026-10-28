# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Selected actual route/callback models. No native, engine, generator or full city-document imports."""

import ast
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "tests/gameplay_routes_baldurs_gate.py"
CALLBACK_TEST = ROOT / "tests/test_baldurs_gate_tamoko_final_meeting.py"
ACTOR = "cityAr0800ScriptActorTamoko"


def callbacks():
    spec = importlib.util.spec_from_file_location("tamoko_actual_callback_models", CALLBACK_TEST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def routeMethods():
    names = {
        "read",
        "state",
        "tamokoJournalSnapshot",
        "tamokoFinalScore",
        "tamokoFinalActor",
        "tamokoFinalSnapshot",
        "tamokoFinalNativeChoice",
    }
    tree = ast.parse(ROUTES.read_text())
    nodes = [deepcopy(node) for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    if len(nodes) != len(names):
        raise AssertionError("Actual natural Tamoko route helpers are missing")
    journal_definition = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "TAMOKO_JOURNAL_ENTRIES" for target in node.targets)
    )
    nodes.insert(0, deepcopy(journal_definition))
    namespace = {"json": json, "decodeCityData": lambda value: json.loads(value.removeprefix("city-json:"))}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(ROUTES), "exec"), namespace)
    return namespace


class TamokoRouteSourceFixture:
    """Fresh model worlds exercise actual callbacks; these witnesses are not native receipts."""

    def __init__(self, test, *, score=12, mutation=None):
        self.test, self.score, self.mutation = test, score, mutation
        self.module = callbacks()
        self.fixture = self.module.TamokoFixture(score=score)
        self.configure()
        self.saves, self.ui_calls, self.inspected = [], [], []
        self.batch_reads, self.scalar_source_reads = [], 0

    def configure(self):
        self.game, self.game_map, self.player = self.fixture.game, self.fixture.game_map, self.fixture.player
        self.fixture.registry.setStringProperty(
            "relocationDefinitions",
            'city-json:[{"id":"tamoko","canonicalActorId":"' + ACTOR + '","sourceCreature":"TAMOKO"}]',
        )

    def object(self, name, required=True):
        value = self.game_map.getObjectByName(name)
        if required:
            self.test.assertIsNotNone(value)
        return value

    def enableIsolatedGui(self):
        return self.game

    def journalPanelText(self):
        rows = []
        for entry in self.player.getQuests():
            if entry.getTypeId() in {row[1] for row in routeMethods()["TAMOKO_JOURNAL_ENTRIES"]}:
                if not getattr(self, "omit_journal_panel", False):
                    rows.append(
                        entry.getStringProperty("description") + "\n" + entry.getObjective() + "\n" + entry.getHint()
                    )
        if getattr(self, "stale_journal_panel", False):
            rows.append("Tamoko's warning")
        return "\n\n".join(rows)

    def call(self, owner, method, *args):
        if owner is self.game and method == "createObject" and args == ("questPanel",):
            return SimpleNamespace(tamoko_journal_panel=True)
        if getattr(owner, "tamoko_journal_panel", False):
            if method == "getType":
                return "CGameQuestPanel"
            if method == "getText":
                self.test.assertEqual((self.game,), args)
                return self.journalPanelText()
            raise AssertionError("Unexpected model journal panel request: " + method)
        if method == "getStringProperty" and args == ("sourceCreature",):
            self.scalar_source_reads += 1
        if method == "getObjectProperty":
            self.test.assertIs(owner, self.fixture.registry)
            self.test.assertEqual(("plugin_cityRelocationActor_tamoko",), args)
            return self.fixture.actor
        if method == "getHp":
            return owner.getNumericProperty("hp")
        if method == "isNpc":
            return owner.getBoolProperty("npc")
        return getattr(owner, method)(*args)

    def stringProperties(self, objects, key):
        self.batch_reads.append((key, len(objects)))
        return [owner.getName() if key == "name" else owner.getStringProperty(key) for owner in objects]

    def gold(self):
        return self.player.getGold()

    def number(self, key):
        return self.game_map.getNumericProperty(key)

    def flag(self, key):
        return self.game_map.getBoolProperty(key)

    def string(self, key):
        return self.game_map.getStringProperty(key)

    def questNames(self, completed=False):
        entries = self.player.getCompletedQuests() if completed else self.player.getQuests()
        return [entry.getName() for entry in entries]

    def condition(self, dialog_id, condition):
        self.test.assertEqual((ACTOR + "Dialog", "canDiscussTamokoFinalMeeting"), (dialog_id, condition))
        self.inspected.append((len(self.saves), condition))
        return self.fixture.dialog.canDiscussTamokoFinalMeeting()

    def chooseUi(self, dialog_id, action, *, dialogue_choices):
        self.test.assertEqual((ACTOR + "Dialog", "discussTamokoFinalMeeting"), (dialog_id, action))
        self.ui_calls.append(list(dialogue_choices))
        success, offered, readers = self.fixture.settle(dialogue_choices)
        self.test.assertTrue(success, "The actual callback did not reach the planned terminal")
        self.test.assertEqual(len(dialogue_choices), len(offered))
        if self.mutation == "reward":
            self.player.addGold(1)
        if self.mutation == "extraGlobal":
            self.fixture.source.setGlobal("UNAUTHORED", "GLOBAL", 1)
        if self.mutation == "duplicateActor":
            clone = self.module.SourceCreature(
                self.fixture.game, "duplicateTamoko", sourceCreature="TAMOKO", sourceArea="AR0123", npc=True
            )
            self.game_map.addObject(clone)
        return {
            "selectedIds": list(dialogue_choices),
            "nativeOptionSeq": 0 if self.mutation == "missingTrace" else 37,
            "panels": [{"kind": "nativeReader", "title": "Tamoko", "body": text} for text in readers],
        }

    def saveAndReload(self, label):
        """Explicit model reconstruction; never evidence of a native save or restored resource graph."""
        self.saves.append(label)
        old = self.fixture
        restored = self.module.TamokoFixture(score=self.score)
        restored.game_map.properties = deepcopy(old.game_map.properties)
        restored.actor.properties = deepcopy(
            {key: value for key, value in old.actor.properties.items() if key != "controller"}
        )
        controller = old.actor.properties.get("controller")
        if controller is not None:
            restored.actor.properties["controller"] = self.module.SourceObject(
                restored.game, controller.getName(), **deepcopy(controller.properties)
            )

        def item(value):
            if value.getTypeId() in {row[1] for row in routeMethods()["TAMOKO_JOURNAL_ENTRIES"]}:
                journal = self.module.modelJournal(restored.game, value.getTypeId())
                journal.properties = deepcopy(value.properties)
                return journal
            return self.module.SourceObject(restored.game, value.getName(), **deepcopy(value.properties))

        restored.actor.items = [item(value) for value in old.actor.items]
        by_name = {value.getName(): value for value in restored.actor.items}
        restored.actor.equipped = {slot: by_name[value.getName()] for slot, value in old.actor.equipped.items()}
        restored.player.items = [item(value) for value in old.player.items]
        restored.player.properties = deepcopy(old.player.properties)
        restored.player.quests = [item(value) for value in old.player.quests]
        restored.player.completed = [item(value) for value in old.player.completed]
        if old.actor.getName() not in old.game_map.objects:
            restored.game_map.objects.pop(restored.actor.name)
            restored.parked.append(restored.actor)
        self.test.assertIsNot(old.actor, restored.actor)
        self.test.assertIsNot(old.player, restored.player)
        self.fixture = restored
        self.configure()
        if len(self.saves) == 2:
            if self.mutation == "reloadName":
                restored.actor.name = "replacementTamoko"
            if self.mutation == "reloadInventory":
                restored.actor.items.pop()
            if self.mutation == "reloadGlobal":
                restored.source.setGlobal("OTHER", "GLOBAL", 8)
            if self.mutation == "reloadJournal":
                restored.namespace["write"](restored.game_map, "plugin_cityCustodyJournal", [111])


class BaldursGateTamokoFinalRoutesTest(unittest.TestCase):
    def testSnapshotScansAllSourceActorsThroughTheExistingBatchFacade(self):
        fixture = TamokoRouteSourceFixture(self)
        for index in range(1025):
            fixture.game_map.addObject(fixture.module.SourceObject(fixture.fixture.game, "unrelated" + str(index)))
        helper = routeMethods()["tamokoFinalSnapshot"]
        helper(fixture, ACTOR)
        self.assertEqual([("sourceCreature", 1029)], [row for row in fixture.batch_reads if row[0] == "sourceCreature"])
        self.assertEqual(
            1, fixture.scalar_source_reads, "Only the selected retained actor needs a scalar identity read"
        )
        duplicate = fixture.module.SourceCreature(
            fixture.fixture.game, "unrelatedName", sourceCreature="TAMOKO", sourceArea="AR0123", npc=True
        )
        fixture.game_map.addObject(duplicate)
        with self.assertRaisesRegex(AssertionError, "extra living"):
            helper(fixture, ACTOR)

    def testAllSevenNaturalPlansRunActualCallbacksAndBothModelCheckpoints(self):
        rows = (
            ("threaten",),
            ("appealChoice", "removeObstacle"),
            ("appealChoice", "unavoidableFight"),
            ("refuseHarm", "forgivingFight"),
            ("appealChoice", "notEnemy", "forgivingFight"),
            ("refuseHarm", "philosophy"),
            ("appealChoice", "notEnemy", "philosophy"),
        )
        helper = routeMethods()["tamokoFinalNativeChoice"]
        for index, choices in enumerate(rows):
            with self.subTest(choices=choices):
                fixture = TamokoRouteSourceFixture(self)
                result = helper(
                    fixture,
                    ACTOR,
                    choices,
                    outcome_key="complete" if "philosophy" in choices else "fight",
                    checkpoint=str(index),
                )
                self.assertEqual(12, result["social"])
                self.assertEqual([str(index) + "-before", str(index) + "-after"], fixture.saves)
                self.assertEqual([list(choices)], fixture.ui_calls)
                self.assertEqual([27461, 27462, 27463], result["sourceJournalIdsPresentBefore"])
                self.assertEqual(3, len(fixture.fixture.actor.items))

    def testSourceModelBoundaryScoresRemainSeparateFromNativePreparationCredit(self):
        helper = routeMethods()["tamokoFinalNativeChoice"]
        for score in (6, 7, 11, 12):
            with self.subTest(score=score):
                fixture = TamokoRouteSourceFixture(self, score=score)
                choice = "philosophy" if score >= 7 else "forgivingFight"
                receipt = helper(
                    fixture, ACTOR, ("refuseHarm", choice), outcome_key="complete" if score >= 12 else "fight"
                )
                self.assertEqual(score, receipt["social"])
                self.assertFalse(receipt["saveReload"])
        fixture = TamokoRouteSourceFixture(self, score=6)
        with self.assertRaisesRegex(AssertionError, "has not earned"):
            helper(fixture, ACTOR, ("refuseHarm", "philosophy"), outcome_key="fight")
        self.assertEqual([], fixture.ui_calls)

    def testRoutesRejectMissingNativeReceiptAndUnplannedRewardsGlobalsOrActorsInModel(self):
        helper = routeMethods()["tamokoFinalNativeChoice"]
        for mutation in ("missingTrace", "reward", "extraGlobal", "duplicateActor"):
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                helper(TamokoRouteSourceFixture(self, mutation=mutation), ACTOR, ("threaten",), outcome_key="fight")

    def testBothModelCheckpointImagesRejectRestoredIdentityInventoryJournalAndGlobalChanges(self):
        helper = routeMethods()["tamokoFinalNativeChoice"]
        for mutation in ("reloadName", "reloadInventory", "reloadGlobal", "reloadJournal"):
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                helper(
                    TamokoRouteSourceFixture(self, mutation=mutation),
                    ACTOR,
                    ("threaten",),
                    outcome_key="fight",
                    checkpoint=mutation,
                )

    def testGenericPlannerUsesTheSequenceAndOnlyTamokoGeneratedCasesNeedGui(self):
        tree = ast.parse(ROUTES.read_text())
        settle = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "settle")
        special = [
            node
            for node in ast.walk(settle)
            if isinstance(node, ast.If) and ast.unparse(node.test) == "key == 'tamokoMercy'"
        ]
        self.assertEqual(1, len(special), "Generic quest route still bypasses the natural final choices")
        calls = [
            node for node in ast.walk(ast.Module(body=special[0].body, type_ignores=[])) if isinstance(node, ast.Call)
        ]
        self.assertTrue(
            any(isinstance(node.func, ast.Name) and node.func.id == "tamokoFinalNativeChoice" for node in calls)
        )
        self.assertFalse(any(isinstance(node.func, ast.Attribute) and node.func.attr == "choose" for node in calls))
        factory = next(
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "generatedQuestCases"
        )
        gui = [node for node in ast.walk(factory) if isinstance(node, ast.keyword) and node.arg == "isolated_gui"]
        self.assertEqual(1, len(gui))
        self.assertEqual("quest['id'] in ui_quests", ast.unparse(gui[0].value))

    def testEightLiteralNativePlansPreserveSevenPathsAndDeclareTheMiddleReactionFight(self):
        tree = ast.parse(ROUTES.read_text())
        cases = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "RouteCase":
                identity = node.args[0]
                if isinstance(identity, ast.Constant) and str(identity.value).startswith("baldurs-gate-native-tamoko-"):
                    cases.append(node)
        self.assertEqual(8, len(cases))
        self.assertEqual(8, len({node.args[0].value for node in cases}))
        branches = {branch for node in cases for branch in ast.literal_eval(node.args[3])}
        self.assertEqual(8, len(branches))
        middle = next(node for node in cases if node.args[0].value == "baldurs-gate-native-tamoko-philosophyFight")
        planned = {entry.arg: ast.literal_eval(entry.value) for entry in middle.args[4].keywords}
        self.assertEqual(("refuseHarm", "philosophy"), planned["choices"])
        self.assertEqual("fight", planned["outcome_key"])
        self.assertIs(planned["ordinary_reaction"], True)
        self.assertEqual(("Warrior",), ast.literal_eval(next(k.value for k in middle.keywords if k.arg == "classes")))
        for node in cases:
            kwargs = {entry.arg: entry.value for entry in node.keywords}
            self.assertIs(ast.literal_eval(kwargs["isolated_gui"]), True)
            self.assertEqual(1200, ast.literal_eval(kwargs["duration_seconds"]))
        mapping = next(
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "SOURCE_BRANCHES" for target in node.targets)
        )
        entries = {
            key.value: ast.literal_eval(value)
            for key, value in zip(mapping.keys, mapping.values, strict=True)
            if isinstance(key, ast.Constant)
            and str(key.value).endswith(
                (".canDiscussTamokoFinalMeeting", ".discussTamokoFinalMeeting", ".commitTamokoFinalMeeting")
            )
        }
        for name in ("canDiscussTamokoFinalMeeting", "discussTamokoFinalMeeting", "commitTamokoFinalMeeting"):
            self.assertEqual(branches, set(entries["res/maps/baldursGate/script.py:BaldursGateDialog." + name]))

    def testMiddleReactionPreparationUsesTheAuthoredOutcomeAndObservedScoreBeforeChoices(self):
        tree = ast.parse(ROUTES.read_text())
        actual = next(
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "tamokoFinalTopology"
        )
        for score in (6, 7, 11, 12):
            with self.subTest(score=score):
                events = []
                driver = SimpleNamespace(test=self, check=lambda *a, **k: events.append("check"))
                row = {"outcomes": [{"id": "fight", "conditions": {}}], "givers": []}
                planner = SimpleNamespace(
                    quests={"tamokoMercy": row},
                    settle=lambda *args: events.append(("settle", args)),
                    accept=lambda *args: events.append(("accept", args)),
                    conditions=lambda *args: events.append("conditions"),
                    actorName=lambda *args: ACTOR,
                    contact=lambda *args: events.append("contact"),
                )

                def nativeChoice(*args, **kwargs):
                    events.append("choice")
                    return {}

                namespace = {
                    "start": lambda d: events.append("start"),
                    "QuestRoute": lambda d: planner,
                    "state": lambda d, key: "completed",
                    "tamokoFinalScore": lambda d: score,
                    "tamokoFinalNativeChoice": nativeChoice,
                    "nativeVictory": lambda *args: events.append("victory"),
                }
                exec(
                    compile(
                        ast.fix_missing_locations(ast.Module(body=[deepcopy(actual)], type_ignores=[])),
                        str(ROUTES),
                        "exec",
                    ),
                    namespace,
                )
                invoke = lambda: namespace["tamokoFinalTopology"](
                    driver,
                    identity="philosophyFight",
                    choices=("refuseHarm", "philosophy"),
                    outcome_key="fight",
                    ordinary_reaction=True,
                )
                if 7 <= score < 12:
                    invoke()
                    self.assertLess(
                        events.index(("settle", ("scarDoppelgangers", "jhassoDead"))),
                        events.index(("accept", ("tamokoMercy",))),
                    )
                    self.assertLess(events.index("contact"), events.index("choice"))
                    self.assertLess(events.index("choice"), events.index("victory"))
                else:
                    with self.assertRaises(AssertionError):
                        invoke()
                    self.assertNotIn("choice", events)
                    self.assertNotIn("victory", events)

    def testFinalHelperDoesNotRewriteEarlierMeetingPreparationOrInventScoreMutation(self):
        tree = ast.parse(ROUTES.read_text())
        wanted = {
            "tamokoFinalScore",
            "tamokoFinalActor",
            "tamokoFinalSnapshot",
            "tamokoFinalNativeChoice",
            "tamokoFinalTopology",
        }
        methods = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
        self.assertEqual(len(wanted), len(methods))
        forbidden = {
            "setNumericProperty",
            "setBoolProperty",
            "setStringProperty",
            "addGold",
            "addExp",
            "addItem",
            "createObject",
            "seed",
            "randint",
        }
        for method in methods:
            for node in ast.walk(method):
                if isinstance(node, ast.Call):
                    name = (
                        node.func.attr
                        if isinstance(node.func, ast.Attribute)
                        else node.func.id if isinstance(node.func, ast.Name) else ""
                    )
                    self.assertNotIn(name, forbidden)
                    if (
                        isinstance(node.func, ast.Attribute)
                        and node.func.attr == "call"
                        and len(node.args) > 1
                        and isinstance(node.args[1], ast.Constant)
                    ):
                        self.assertNotIn(node.args[1].value, forbidden)

    def testFinalSourceEraseMustRemoveVisibleJournalTextAndKeepUnrelatedQuestMembership(self):
        model = TamokoRouteSourceFixture(self)
        unrelated_active = model.module.SourceObject(model.fixture.game, "unrelatedActiveQuest")
        unrelated_completed = model.module.SourceObject(model.fixture.game, "unrelatedCompletedQuest")
        model.player.quests.append(unrelated_active)
        model.player.completed.append(unrelated_completed)
        methods = routeMethods()
        before = methods["tamokoJournalSnapshot"](model)
        self.assertEqual({27461, 27462, 27463}, {row[0] for row in before})
        methods["tamokoFinalNativeChoice"](model, ACTOR, ("refuseHarm", "philosophy"), outcome_key="complete")
        self.assertEqual((), methods["tamokoJournalSnapshot"](model))
        self.assertTrue(any(entry is unrelated_active for entry in model.player.getQuests()))
        self.assertTrue(any(entry is unrelated_completed for entry in model.player.getCompletedQuests()))
        model.stale_journal_panel = True
        with self.assertRaises(AssertionError):
            methods["tamokoJournalSnapshot"](model)

    def testGenericDiaryRepeatUsesAuthoredInventoryInspectionAndStillRejectsDuplicateReward(self):
        from collections import deque

        config = json.loads((ROOT / "res/maps/baldursGate/config.json").read_text(encoding="utf-8"))
        document = json.loads((ROOT / "tests/fixtures/baldurs_gate_city_quests.json").read_text(encoding="utf-8"))
        row = next(entry for entry in document["quests"] if entry["id"] == "cythandriaDiary")
        outcome = row["outcomes"][0]
        self.assertEqual({"flags": {"sarevokDiarySecured": True}}, outcome["effects"])
        self.assertEqual({"TAMOKO"}, {giver["creature"] for giver in row["givers"]})
        route_tree = ast.parse(ROUTES.read_text(encoding="utf-8"))
        route_nodes = [
            node
            for node in route_tree.body
            if isinstance(node, ast.FunctionDef) and node.name in ("questRoute", "upperFirst")
        ]
        driver_tree = ast.parse((ROOT / "tests/gameplay_branch_driver.py").read_text(encoding="utf-8"))
        choose = deepcopy(
            next(node for node in ast.walk(driver_tree) if isinstance(node, ast.FunctionDef) and node.name == "choose")
        )
        namespace = {"deque": deque}
        exec(compile(ast.Module(body=[choose], type_ignores=[]), "actual-driver-choice", "exec"), namespace)
        actual_choose = namespace["choose"]
        ordinary_dialog = next(
            name
            for name, value in sorted(config.items())
            if name != ACTOR + "Dialog"
            and value.get("class") == "BaldursGateDialog"
            and any(
                option["properties"].get("action") == "talk"
                for state in value["properties"].get("states", [])
                for option in state["properties"].get("options", [])
            )
        )

        def run(name, *, duplicate_reward=False, completed_available=False):
            actor, game, dialog = object(), object(), object()
            calls, choices, balance = [], [], [17, 23, ("SCRL3F",)]
            states = {
                state["properties"]["stateId"]: state["properties"]
                for state in config[name + "Dialog"]["properties"]["states"]
            }
            driver = SimpleNamespace(test=self, game=game, map_name="baldursGate", _dialog_positions={})

            def call(owner, method, *args):
                if owner is game and method == "createObject":
                    self.assertEqual((name + "Dialog",), args)
                    return dialog
                if owner is dialog and method == "invokeCondition":
                    return False
                if owner is dialog and method == "invokeAction":
                    calls.append(args[0])
                    if duplicate_reward:
                        balance[0] += 1
                    return None
                raise AssertionError((method, args))

            driver.call = call
            driver._dialogStates = lambda _identity: states
            driver.record = lambda record, **_kwargs: choices.append(record)
            driver.pump = lambda: None
            driver.choose = lambda *args, **kwargs: actual_choose(driver, *args, **kwargs)
            driver.object = lambda _name, **_kwargs: actor
            driver.condition = lambda *_args: completed_available
            driver.saveAndReload = lambda _label: None
            driver.check = lambda _branch, condition, **_kwargs: self.assertTrue(condition)
            planner = SimpleNamespace(
                quests={"cythandriaDiary": row}, settle=lambda *_args: (name, outcome), contact=lambda _name: None
            )
            namespace.update(
                start=lambda _driver: None,
                QuestRoute=lambda _driver: planner,
                state=lambda *_args: "completed",
                resources=lambda _driver: tuple(balance),
            )
            exec(
                compile(ast.Module(body=route_nodes, type_ignores=[]), "actual-generic-quest-route", "exec"), namespace
            )
            namespace["questRoute"](driver, "cythandriaDiary", "complete")
            return calls, choices, tuple(balance)

        calls, choices, balance = run(ACTOR)
        self.assertEqual(["showInventory"], calls)
        self.assertEqual(["showInventory"], [choice["action"] for choice in choices])
        self.assertEqual((17, 23, ("SCRL3F",)), balance)
        self.assertEqual(["talk"], run(ordinary_dialog.removesuffix("Dialog"))[0])
        with self.assertRaisesRegex(AssertionError, "Returning after a quest reward paid twice"):
            run(ACTOR, duplicate_reward=True)
        with self.assertRaises(AssertionError):
            run(ACTOR, completed_available=True)
