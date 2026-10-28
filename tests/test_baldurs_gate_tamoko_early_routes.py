# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual route/callback AST models. Synthetic UI receipts are not native or save/reload evidence."""

import ast
from copy import deepcopy
from functools import lru_cache
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "tests/gameplay_routes_baldurs_gate.py"
EARLY_TEST = ROOT / "tests/test_baldurs_gate_tamoko_early_meetings.py"
SCRIPT = ROOT / "res/maps/baldursGate/script.py"
INVENTORY = ROOT / "tests/fixtures/baldurs_gate_city_tamoko_dialogue.json"
ACTOR = "cityAr0800ScriptActorTamoko"
FIRST = (
    (("rejectSpy", "rejectFamily", "askRelative"), 7),
    (("rejectSpy", "defendGorion", "endRiddles"), 6),
    (("rejectSpy", "askKnowledge", "defendGorion", "askRelative"), 7),
    (("hearInformation", "rejectFamily", "endRiddles"), 6),
    (("askIdentity", "rejectRiddles", "defendGorion", "askRelative"), 7),
    (("askIdentity", "listen", "defendGorion", "endRiddles"), 6),
)
SECOND = (
    (("threaten",), 12),
    (("questionPromise", "refuseUnknown"), 12),
    (("questionPromise", "promise", "mustKill"), 12),
    (("promise", "askHow", "mustKill"), 12),
    (("promise", "askHow", "askDivinity", "mustKill"), 12),
    (("promise", "askHow", "askDivinity", "askLove", "rejectRedemption"), 12),
    (("promise", "askHow", "askDivinity", "askLove", "trySpare", "thankForLead"), 18),
    (("promise", "askHow", "askDivinity", "trySpare", "promiseViolence"), 19),
)


@lru_cache(maxsize=1)
def callbacks():
    spec = importlib.util.spec_from_file_location("actual_early_tamoko_callbacks", EARLY_TEST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SCRIPT = SCRIPT
    module.ROOT = ROOT
    module.QUESTS = ROOT / "tests/fixtures/baldurs_gate_city_quests.json"
    module.INVENTORY = INVENTORY
    return module


@lru_cache(maxsize=1)
def routeMethods():
    names = {
        "read",
        "state",
        "upperFirst",
        "tamokoJournalSnapshot",
        "tamokoEarlyActor",
        "tamokoEarlySnapshot",
        "tamokoEarlyNativeChoice",
        "tamokoEarlyTopology",
        "tamokoQuestUiIds",
    }
    tree = ast.parse(ROUTES.read_text())
    nodes = [deepcopy(node) for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    planner = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "QuestRoute")
    methods = [
        deepcopy(node)
        for node in planner.body
        if isinstance(node, ast.FunctionDef) and node.name in {"accept", "tamokoMeetings", "conditions"}
    ]
    nodes.append(ast.ClassDef(name="ActualPlanner", bases=[], keywords=[], body=methods, decorator_list=[]))
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


class EarlyRouteModel:
    """Model transport runs actual selected callbacks; setup/reconstruction do not earn native credit."""

    def __init__(self, test, *, rescued=0, mutation=None):
        self.test, self.rescued, self.mutation = test, rescued, mutation
        self.module = callbacks()
        self.fixture = self.module.EarlyFixture("first", rescued=rescued)
        self.saves, self.ui_calls, self.contacts, self.batch_reads = [], [], [], []
        self.scalar_source_reads = 0
        self.fixture.player.items = [self.module.SourceObject(self.fixture.game, "alreadyOwnedInventorySentinel")]
        self.fixture.actor.items = [self.module.SourceObject(self.fixture.game, "existingActorInventorySentinel")]
        self.fixture.actor.equipped = {"right": self.fixture.actor.items[0]}
        self.configure()

    def configure(self):
        self.game, self.game_map, self.player = self.fixture.game, self.fixture.game_map, self.fixture.player
        # The native authored property is a document. The compact model preserves that shape.
        self.fixture.namespace["write"](
            self.fixture.registry, "questDefinitions", {"quests": [self.module.selectedQuest()], "excursions": []}
        )
        metadata = self.fixture.namespace["read"](self.fixture.registry, "questDefinitions", {})
        self.test.assertIsInstance(metadata, dict)
        self.test.assertIsInstance(metadata["quests"], list)
        self.fixture.registry.relocateActors()

    def object(self, name, required=True):
        value = self.game_map.getObjectByName(name)
        if required:
            self.test.assertIsNotNone(value, name)
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
        if method == "getItems":
            return list(owner.items)
        if method == "getEquipped":
            return getattr(owner, "equipped", {})
        if method == "getHp":
            return owner.getNumericProperty("hp")
        if method == "getStats":
            return SimpleNamespace(getNumericProperty=lambda key: 12)
        if method == "getNumericProperty" and args == ("exp",):
            return owner.exp
        if method == "getStringProperty" and args == ("sourceCreature",):
            self.scalar_source_reads += 1
        return getattr(owner, method)(*args)

    def stringProperties(self, objects, key):
        self.batch_reads.append((key, len(objects)))
        return [obj.getName() if key == "name" else obj.getStringProperty(key) for obj in objects]

    def number(self, key):
        if key == "plugin_cityReputation":
            return self.game_map.values.get(key, 10)
        return self.game_map.getNumericProperty(key)

    def string(self, key):
        return self.game_map.getStringProperty(key)

    def flag(self, key):
        return self.game_map.getBoolProperty(key)

    def gold(self):
        return self.player.gold

    def questNames(self, completed=False):
        return (
            [entry.getTypeId() for entry in self.player.completed if completed]
            if completed
            else [entry.getTypeId() for entry in self.player.quests]
        )

    def condition(self, dialog, method):
        self.test.assertEqual(ACTOR + "Dialog", dialog)
        return getattr(self.fixture.dialog, method)()

    def choose(self, *_args, **_kwargs):
        raise AssertionError("Legacy early Tamoko shortcut bypassed the actual natural chooser sequence")

    def chooseUi(self, dialog, action, *, dialogue_choices):
        self.test.assertEqual(ACTOR + "Dialog", dialog)
        self.test.assertIn(action, ("discussTamokoFirstMeeting", "discussTamokoSecondMeeting"))
        self.fixture.meeting = "first" if action == "discussTamokoFirstMeeting" else "second"
        self.ui_calls.append((self.fixture.meeting, tuple(dialogue_choices)))
        success, views = self.fixture.settle(dialogue_choices)
        self.test.assertTrue(success, "The actual selected callback did not settle its planned source terminal")
        if self.mutation == "reward":
            self.player.addGold(1)
        if self.mutation == "extraGlobal":
            self.fixture.source.setGlobal("UNAUTHORED", "GLOBAL", 1)
        if self.mutation == "duplicateActor":
            self.game_map.addObject(
                self.module.SourceCreature(self.game, "arbitraryDuplicate", sourceCreature="TAMOKO")
            )
        panels = [
            {"kind": "nativeReader", "title": request["args"][1], "body": request["args"][2]}
            for request in views
            if request["operation"] == "showReader"
        ]
        return {
            "selectedIds": list(dialogue_choices),
            "nativeOptionSeq": 0 if self.mutation == "missingTrace" else 37,
            "panels": panels,
        }

    def saveAndReload(self, label):
        """Explicit fresh model objects; never a native saved graph, clock or UI receipt."""
        self.saves.append(label)
        old = self.fixture
        restored = self.module.EarlyFixture(old.meeting, rescued=self.rescued, properties=deepcopy(old.game_map.values))
        restored.actor.values = deepcopy(old.actor.values)
        restored.player.values = deepcopy(old.player.values)
        restored.player.gold, restored.player.exp = old.player.gold, old.player.exp

        def item(value):
            if value.getTypeId() in {row[1] for row in routeMethods()["TAMOKO_JOURNAL_ENTRIES"]}:
                journal = self.module.modelJournal(restored.game, value.getTypeId())
                journal.values = deepcopy(value.values)
                return journal
            return self.module.SourceObject(restored.game, value.name, **deepcopy(value.values))

        restored.actor.items = [item(value) for value in old.actor.items]
        items = {value.name: value for value in restored.actor.items}
        restored.actor.equipped = {
            slot: items[value.name] for slot, value in getattr(old.actor, "equipped", {}).items()
        }
        restored.player.items = [item(value) for value in old.player.items]
        restored.player.quests = [item(value) for value in old.player.quests]
        restored.player.completed = [item(value) for value in old.player.completed]
        for key, value in old.registry.values.items():
            restored.registry.values[key] = restored.actor if value is old.actor else deepcopy(value)
        self.test.assertIsNot(old.actor, restored.actor)
        self.test.assertIsNot(old.player, restored.player)
        self.fixture = restored
        self.configure()
        if self.mutation == "reloadInventory":
            self.player.items.pop()
        if self.mutation == "reloadGlobal":
            self.fixture.source.setGlobal("OTHER", "GLOBAL", 8)
        if self.mutation == "reloadJournal":
            self.fixture.namespace["write"](self.game_map, "plugin_cityCustodyJournal", [111])
        if self.mutation == "reloadActor":
            self.fixture.registry.setObjectProperty(
                "plugin_cityRelocationActor_tamoko", self.module.SourceCreature(self.game, "replacement")
            )

    def planner(self, namespace, *, refuse=False):
        planner = namespace["ActualPlanner"]()
        planner.d, planner.tamoko_refuse = self, refuse
        planner.quests = {"cythandriaDiary": self.module.selectedQuest()}
        planner.data = {"quests": list(planner.quests.values())}
        planner.pending, planner.pending_outcomes = set(), set()
        planner.actions = 0
        planner.ensurePhase = lambda phase: self.test.assertEqual(7, phase)
        planner.bounded = lambda goal: self.test.assertIn(goal, ({"flags": ["tamokoMove2"]},))

        def actorName(selectors):
            self.test.assertEqual("TAMOKO", selectors[0]["creature"])
            self.test.assertEqual(selectors[0]["area"], self.fixture.actor.getStringProperty("sourceArea"))
            return ACTOR

        def contact(name):
            self.test.assertEqual(ACTOR, name)
            self.contacts.append(name)
            self.game_map.setStringProperty(
                "activeSimulationRegion", self.fixture.actor.getStringProperty("sourceArea")
            )

        planner.actorName, planner.contact = actorName, contact
        return planner


class BaldursGateTamokoEarlyRoutesTest(unittest.TestCase):
    def testAllEightPlansExerciseActualCallbacksAndFreshModelCheckpointObjects(self):
        helper = routeMethods()["tamokoEarlyNativeChoice"]
        for index, (second, second_terminal) in enumerate(SECOND):
            for rescued in (0, 1):
                with self.subTest(pair=index + 1, rescued=rescued):
                    driver = EarlyRouteModel(self, rescued=rescued)
                    first, first_terminal = FIRST[index % len(FIRST)]
                    first_result = helper(driver, ACTOR, "first", first, first_terminal, checkpoint="first")
                    driver.game_map.setStringProperty("activeSimulationRegion", "AR1100")
                    second_result = helper(driver, ACTOR, "second", second, second_terminal, checkpoint="second")
                    self.assertEqual(["first-before", "first-after", "second-before", "second-after"], driver.saves)
                    self.assertEqual(27461, first_result["sourceJournalId"])
                    self.assertEqual(27462 if second_terminal == 12 else 27463, second_result["sourceJournalId"])
                    self.assertEqual(second_terminal in (18, 19), second_result["informedLead"])
                    self.assertFalse(driver.flag("plugin_cityDeparted"))

    def testGenericPlannerUsesBothNaturalSequencesAndNeverLegacyEntryActions(self):
        namespace = routeMethods()
        for refusal in (False, True):
            with self.subTest(refusal=refusal):
                driver = EarlyRouteModel(self)
                planner = driver.planner(namespace, refuse=refusal)
                planner.tamokoMeetings()
                self.assertEqual(2, len(driver.ui_calls))
                self.assertEqual("refuse" if refusal else "accept", driver.string("plugin_cityTamokoSecondChoice"))
                self.assertEqual("notStarted" if refusal else "active", namespace["state"](driver, "cythandriaDiary"))
                previous = list(driver.ui_calls)
                planner.tamokoMeetings()
                self.assertEqual(previous, driver.ui_calls)

    def testDiaryAdmissionCannotBypassASettledSourceRefusal(self):
        namespace = routeMethods()
        driver = EarlyRouteModel(self)
        planner = driver.planner(namespace, refuse=True)
        planner.tamokoMeetings()
        with self.assertRaisesRegex(AssertionError, "refusal cannot be bypassed"):
            planner.accept("cythandriaDiary")
        self.assertEqual(2, len(driver.ui_calls))
        self.assertEqual("notStarted", namespace["state"](driver, "cythandriaDiary"))
        self.assertCountEqual(["cityTamokoWarningJournalQuest", "cityTamokoRefusalJournalQuest"], driver.questNames())

    def testPlannerDiaryAcceptanceAndConditionFlagsUseTheSameInformedFlow(self):
        namespace = routeMethods()
        for condition in (False, True):
            with self.subTest(condition=condition):
                driver = EarlyRouteModel(self)
                planner = driver.planner(namespace)
                if condition:
                    planner.conditions({"flags": ["tamokoMove2"]})
                else:
                    planner.accept("cythandriaDiary")
                self.assertEqual(2, len(driver.ui_calls))
                self.assertCountEqual(
                    ["cityCythandriaDiaryQuest", "cityTamokoWarningJournalQuest", "cityTamokoInformedJournalQuest"],
                    driver.questNames(),
                )

    def testSnapshotScansEverySourceHandleThroughTheExistingBatchFacade(self):
        driver = EarlyRouteModel(self)
        for index in range(1025):
            driver.game_map.addObject(driver.module.SourceObject(driver.game, "unrelated" + str(index)))
        helper = routeMethods()["tamokoEarlySnapshot"]
        helper(driver, ACTOR)
        self.assertEqual([("sourceCreature", 1029)], [row for row in driver.batch_reads if row[0] == "sourceCreature"])
        self.assertEqual(1, driver.scalar_source_reads)
        driver.game_map.addObject(driver.module.SourceCreature(driver.game, "arbitraryName", sourceCreature="TAMOKO"))
        with self.assertRaisesRegex(AssertionError, "extra living"):
            helper(driver, ACTOR)

    def testMissingNativeTraceAndUnplannedResourcesGlobalsOrDuplicateActorsAreRejected(self):
        helper = routeMethods()["tamokoEarlyNativeChoice"]
        for mutation in ("missingTrace", "reward", "extraGlobal", "duplicateActor"):
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                helper(EarlyRouteModel(self, mutation=mutation), ACTOR, "first", FIRST[0][0], 7)

    def testModelReloadRequiresExactSourceIdentityInventoryJournalAndGlobals(self):
        helper = routeMethods()["tamokoEarlyNativeChoice"]
        for mutation in ("reloadActor", "reloadInventory", "reloadGlobal", "reloadJournal"):
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                helper(EarlyRouteModel(self, mutation=mutation), ACTOR, "first", FIRST[0][0], 7, checkpoint=mutation)

    def testQuestUiDependenciesIncludeTransitiveFlagsStagesAndNestedAlternatives(self):
        helper = routeMethods()["tamokoQuestUiIds"]
        quests = [
            {
                "id": "cythandriaDiary",
                "acceptEffects": {"flags": {"diaryAdmitted": True}},
                "outcomes": [{"effects": {"flags": {"diarySecured": True}}}],
            },
            {
                "id": "requiresDiary",
                "acceptConditions": {"any": [{"flags": ["diarySecured"]}]},
                "outcomes": [{"effects": {"flags": {"afterDiary": True}}}],
            },
            {"id": "requiresDependent", "outcomes": [{"conditions": {"all": [{"flags": ["afterDiary"]}]}}]},
            {
                "id": "stageDependent",
                "acceptConditions": {"questStages": {"requiresDependent": "completed"}},
                "outcomes": [],
            },
            {"id": "unrelated", "outcomes": []},
            {"id": "acceptDependent", "acceptConditions": {"flags": ["diaryAdmitted"]}, "outcomes": []},
        ]
        self.assertEqual(
            frozenset(
                {
                    "tamokoMercy",
                    "cythandriaDiary",
                    "requiresDiary",
                    "requiresDependent",
                    "stageDependent",
                    "acceptDependent",
                }
            ),
            helper(list(reversed(quests))),
        )
        actual = json.loads((ROOT / "tests/fixtures/baldurs_gate_city_quests.json").read_text())["quests"]
        self.assertEqual(frozenset({"tamokoMercy", "cythandriaDiary"}), helper(actual))

    def testEightIsolatedPlansCoverThirtyChoiceEdgesWithoutClaimingAutomaticRescuePreparation(self):
        rows = {row["state"]: row for row in json.loads(INVENTORY.read_text())["states"]}
        edges = set()
        for index, (second, terminal) in enumerate(SECOND):
            for start, choices, expected in (
                (0, FIRST[index % len(FIRST)][0], FIRST[index % len(FIRST)][1]),
                (10, second, terminal),
            ):
                state = start
                for reply in choices:
                    (edge,) = [edge for edge in rows[state]["edges"] if edge["replyId"] == reply]
                    edges.add(edge["edge"])
                    state = edge["targetState"]
                self.assertEqual(expected, state)
        expected = {
            edge["edge"]
            for row in rows.values()
            if row["state"] < 20
            for edge in row["edges"]
            if edge["replyId"] is not None
        }
        self.assertEqual(30, len(edges))
        self.assertEqual(expected, edges)
        for row in rows.values():
            if row["state"] >= 20:
                continue
            for edge in row["edges"]:
                plan = edge["plannedNativeRoute"]
                self.assertEqual("tamokoEarlyTopology", plan["method"])
                self.assertEqual("tamokoEarlyNativeChoice", plan["chooser"])
                self.assertIs(False, plan["executed"])
                if edge["replyId"] is not None:
                    self.assertTrue(plan["caseIds"])
                if edge["edge"] in (16, 17, 18):
                    self.assertTrue(plan["caseIds"])
                    self.assertIn("pending", plan["coverage"])
                    self.assertEqual(
                        (
                            ["baldurs-gate-native-early-tamoko-rescued"]
                            if edge["edge"] in (16, 18)
                            else ["baldurs-gate-native-early-tamoko-pair" + str(index) for index in range(1, 9)]
                        ),
                        plan["caseIds"],
                    )
        tree = ast.parse(ROUTES.read_text())
        cases = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "RouteCase"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and str(node.args[0].value).startswith("baldurs-gate-native-early-tamoko-")
        ]
        expected_ids = {"baldurs-gate-native-early-tamoko-pair" + str(index) for index in range(1, 9)}
        expected_ids.add("baldurs-gate-native-early-tamoko-rescued")
        self.assertEqual(9, len(cases))
        self.assertEqual(expected_ids, {node.args[0].value for node in cases})
        for node in cases:
            keywords = {item.arg: item.value for item in node.keywords}
            self.assertIs(ast.literal_eval(keywords["isolated_gui"]), True)
            self.assertEqual(1200, ast.literal_eval(keywords["duration_seconds"]))
            self.assertIn("baldurs_gate_city_tamoko_dialogue.json", ast.unparse(keywords["sources"]))

    def testNaturalRouteHelpersCannotMutateFlagsStatsRewardsOrUseTheFinalActorArea(self):
        tree = ast.parse(ROUTES.read_text())
        methods = [
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith("tamokoEarly")
        ]
        self.assertEqual(4, len(methods))
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
            "tamokoFinalActor",
        }
        for method in methods:
            for node in ast.walk(method):
                if isinstance(node, ast.Call):
                    name = (
                        node.func.id
                        if isinstance(node.func, ast.Name)
                        else node.func.attr if isinstance(node.func, ast.Attribute) else ""
                    )
                    self.assertNotIn(name, forbidden)
                    if (
                        isinstance(node.func, ast.Attribute)
                        and node.func.attr == "call"
                        and len(node.args) > 1
                        and isinstance(node.args[1], ast.Constant)
                    ):
                        self.assertNotIn(node.args[1].value, forbidden)
        actor = next(node for node in methods if node.name == "tamokoEarlyActor")
        self.assertNotIn("AR0123", ast.unparse(actor))
        mapping = next(
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "SOURCE_BRANCHES" for target in node.targets)
        )
        names = {key.value for key in mapping.keys if isinstance(key, ast.Constant)}
        for legacy in (
            "hearTamokoWarning",
            "declineTamokoFirstMeeting",
            "discussTamokoRequest",
            "acceptTamokoRequest",
            "refuseTamokoRequest",
            "canFinishTamokoSecondMeeting",
        ):
            self.assertNotIn("res/maps/baldursGate/script.py:BaldursGateDialog." + legacy, names)

    def testSourceJournalProjectionMustBeOwnedAndAppearInTheNativeShapedPanel(self):
        model = EarlyRouteModel(self)
        methods = routeMethods()
        methods["tamokoEarlyNativeChoice"](model, ACTOR, "first", FIRST[0][0], FIRST[0][1])
        journal = methods["tamokoJournalSnapshot"](model)
        self.assertEqual((27461,), tuple(row[0] for row in journal))
        model.omit_journal_panel = True
        with self.assertRaises(AssertionError):
            methods["tamokoJournalSnapshot"](model)
        model.omit_journal_panel = False
        model.player.quests = [
            entry for entry in model.player.quests if entry.getTypeId() != "cityTamokoWarningJournalQuest"
        ]
        with self.assertRaises(AssertionError):
            methods["tamokoJournalSnapshot"](model)

    def testRescuedTopologyUsesTheActualCarryOutcomeBetweenMeetingsWithoutProgressWrites(self):
        tree = ast.parse(ROUTES.read_text())
        topology = next(
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "tamokoEarlyTopology"
        )

        class Planner:
            def __init__(self, driver):
                self.driver = driver

            def ensurePhase(self, phase):
                self.driver.order.append(("phase", phase))

            def settle(self, key, outcome):
                self.driver.order.append(("settle", key, outcome))

            def actorName(self, selectors):
                return ACTOR

            def contact(self, name):
                self.driver.order.append(("contact", name))

        class Driver:
            def __init__(self, test):
                self.test, self.order, self.receipts = test, [], []
                self.player = object()

            def flag(self, name):
                return name == "plugin_cityFlag_eltanCarried"

            def call(self, owner, method):
                self.test.assertIs(self.player, owner)
                self.test.assertEqual("getItems", method)
                return ["actualCarryItemModel"]

            def stringProperties(self, items, key):
                self.test.assertEqual(["actualCarryItemModel"], items)
                self.test.assertEqual("sourceItem", key)
                return ["MISC55"]

            def check(self, branch, condition, **evidence):
                self.test.assertTrue(condition)
                self.receipts.append((branch, evidence))

        driver = Driver(self)

        def choice(d, name, meeting, choices, terminal, **kwargs):
            d.order.append(("choice", meeting))
            return {"sourceEltanState": 1 if meeting == "second" else None}

        namespace = {
            "QuestRoute": Planner,
            "start": lambda d: d.order.append(("start",)),
            "state": lambda d, key: "active",
            "tamokoEarlyNativeChoice": choice,
        }
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[deepcopy(topology)], type_ignores=[])), str(ROUTES), "exec"
            ),
            namespace,
        )
        namespace["tamokoEarlyTopology"](
            driver,
            identity="rescued",
            first_choices=FIRST[0][0],
            first_terminal=7,
            second_choices=SECOND[-2][0],
            second_terminal=18,
            rescue_before_second=True,
        )
        self.assertLess(driver.order.index(("choice", "first")), driver.order.index(("settle", "rescueEltan", "carry")))
        self.assertLess(
            driver.order.index(("settle", "rescueEltan", "carry")), driver.order.index(("choice", "second"))
        )
        self.assertEqual("baldursGate.tamoko.early.rescued", driver.receipts[0][0])
        self.assertNotIn("setBoolProperty", ast.unparse(topology))
        self.assertNotIn("setNumericProperty", ast.unparse(topology))

    def testJournalContractRowsContainEverySourceHintAndCapturedTextField(self):
        entries = routeMethods()["TAMOKO_JOURNAL_ENTRIES"]
        self.assertEqual(3, len(entries))
        self.assertEqual([27461, 27462, 27463], [row[0] for row in entries])
        for row in entries:
            self.assertEqual(
                5, len(row), "Each source journal contract needs id, type, description, objective and hint"
            )
            self.assertTrue(all(isinstance(field, str) and field for field in row[1:]))
        self.assertEqual("Tamoko departed after you rejected her condition.", entries[1][4])

    def testLegacyDiaryEntryCallbacksDenyBothConditionAndActionAfterRefusal(self):
        model = EarlyRouteModel(self)
        methods = routeMethods()
        methods["tamokoEarlyNativeChoice"](model, ACTOR, "first", FIRST[0][0], FIRST[0][1])
        model.fixture.meeting = "second"
        model.game_map.setStringProperty("activeSimulationRegion", "AR1100")
        methods["tamokoEarlyNativeChoice"](model, ACTOR, "second", SECOND[0][0], SECOND[0][1])
        source = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        owner = next(
            node for node in ast.walk(source) if isinstance(node, ast.ClassDef) and node.name == "BaldursGateDialog"
        )
        names = {"canAcceptQuest", "acceptQuest", "canAcceptCythandriaDiary", "acceptCythandriaDiary"}
        nodes = [deepcopy(node) for node in owner.body if isinstance(node, ast.FunctionDef) and node.name in names]
        self.assertEqual(names, {node.name for node in nodes})
        for node in nodes:
            node.decorator_list = []
        exec(
            compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(SCRIPT), "exec"),
            model.fixture.namespace,
        )
        for name in names:
            setattr(type(model.fixture.dialog), name, model.fixture.namespace[name])
        before = model.fixture.snapshot()
        self.assertIs(False, model.fixture.dialog.canAcceptCythandriaDiary())
        self.assertIs(False, model.fixture.dialog.acceptCythandriaDiary())
        self.assertEqual(before, model.fixture.snapshot())


if __name__ == "__main__":
    unittest.main()
