# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Source-backed dialogue and crafting regressions; no display or native module is required."""

import ast
import copy
import importlib.util
import json
import sys
import types
import unittest
from tests.hook_flow_support import installHookFlows
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def readJson(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def dialogueStates(path, dialog_id):
    return {
        state["properties"]["stateId"]: state["properties"]
        for state in readJson(path)[dialog_id]["properties"]["states"]
    }


def loadClasses(path, names, namespace):
    installHookFlows(namespace)
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    classes = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    body = []
    for name in names:
        node = copy.deepcopy(classes[name])
        node.decorator_list = []
        body.append(node)
    module = ast.fix_missing_locations(ast.Module(body=body, type_ignores=[]))
    exec(compile(module, str(path), "exec"), namespace)
    return namespace


class FakeItem:
    def __init__(self, item_id):
        self.item_id = item_id

    def getTypeId(self):
        return self.item_id

    def getStringProperty(self, name):
        return self.item_id


class FakePlayer:
    def __init__(self):
        self.items = []
        self.flags = {}
        self.gold = 10
        self.quests = []
        self.game_map = None

    def getItems(self):
        return self.items

    def getEquipped(self):
        return {}

    def getGold(self):
        return self.gold

    def getExp(self):
        return 0

    def countItems(self, item_id):
        return sum(item.getTypeId() == item_id for item in self.items)

    def hasItem(self, predicate):
        return any(predicate(item) for item in self.items)

    def removeItem(self, predicate, *_args):
        for item in self.items:
            if predicate(item):
                self.items.remove(item)
                return

    def addItem(self, item):
        self.items.append(FakeItem(item) if isinstance(item, str) else item)

    def checkQuests(self):
        pass

    def isPlayer(self):
        return True

    def getNumericProperty(self, name):
        return self.gold if name == "gold" else 0

    def setNumericProperty(self, name, value):
        if name == "gold":
            self.gold = value

    def getBoolProperty(self, name):
        return bool(self.flags.get(name))

    def getMap(self):
        return self.game_map


class FakeMap:
    def __init__(self, player):
        self.flags = {}
        self.player = player
        player.game_map = self
        self.standing = 0

    def getBoolProperty(self, name):
        return bool(self.flags.get(name))

    def setBoolProperty(self, name, value):
        self.flags[name] = value

    def getPlayer(self):
        return self.player


class FakeDialog:
    def getGame(self):
        return self.game


def custodyScriptedActorFacts(prison):
    """The 23 deferred source spawns; existing prison actors such as Neb are not additions."""
    districts = ("AR0100", "AR0200", "AR0300", "AR0600", "AR0700", "AR0800", "AR1100", "AR1200", "AR1300")
    if set(prison["patrols"]) != set(districts):
        raise ValueError("The audited nine custody patrol wards must remain explicit")
    facts = {}

    def add(source_id, native_id, area, creature, position, role):
        if source_id in facts or any(row["nativeId"] == native_id for row in facts.values()):
            raise ValueError("Duplicate custody source or native identity")
        facts[source_id] = {
            "sourceId": source_id,
            "nativeId": native_id,
            "areas": [area],
            "creature": creature,
            "position": list(position),
            "custodyRole": role,
            "phase": 7,
            "requiresFlag": "" if role == "patrol" else "custodyHearing",
            "dialogue": "FLAMC7" if creature == "FLAME4" else prison["creatures"][creature]["dialogue"],
        }

    for area in districts:
        patrol = prison["patrols"][area]
        offsets = patrol["spawnRecordOffsets"]
        if patrol["count"] != 2 or len(offsets) != 2 or len(set(offsets)) != 2:
            raise ValueError("Each source patrol must retain its two distinct CreateCreature offsets")
        chapter = [condition for condition in patrol["conditions"] if condition["strings"][0] == "GLOBALChapter"]
        if (
            len(chapter) != 1
            or chapter[0]["opcode"] != 16399
            or chapter[0]["signature"] != "Global(S:Name*,S:Area*,I:Value*)"
            or chapter[0]["negated"]
            or chapter[0]["integerFields"][0] != 7
        ):
            raise ValueError("Custody patrols require the audited chapter-seven condition")
        for offset, suffix in zip(offsets, ("One", "Two")):
            if type(offset) is not int or offset < 0:
                raise ValueError("A custody spawn requires an actual record offset")
            add(
                f"{area}.BCS#offset{offset}",
                "cityCustodyPatrol" + area.title() + suffix,
                area,
                "FFHUNT",
                patrol["position"],
                "patrol",
            )
    for creature, native_id, scene in [
        ("ANGELO", "cityCustodyAngelo", "CAPCUT03"),
        *(("FLAME" + str(index), "cityCustodyEscortFlame" + str(index), "CAPCUT01") for index in range(1, 5)),
    ]:
        matches = [
            row
            for row in prison["scenes"][scene]
            if row["op"] == "CreateCreature" and row["strings"][0].upper() == creature
        ]
        if len(matches) != 1:
            raise ValueError("Custody cutscene actor evidence must resolve exactly once: " + creature)
        row = matches[0]
        if row["kind"] != "AC" or type(row["offset"]) is not int or row["offset"] < 0:
            raise ValueError("A custody cutscene actor requires an actual action record")
        add(
            f"{scene}.BCS#offset{row['offset']}",
            native_id,
            "AR0607",
            creature,
            row["integers"][1:3],
            "angelo" if creature == "ANGELO" else "escort",
        )
    if len(facts) != 23:
        raise ValueError("The reviewed custody addition is exactly 18 patrol and five hearing actors")
    return facts


def assertCustodyDialogueProvenance(test, definitions, prison):
    facts = custodyScriptedActorFacts(prison)
    expected = {row["nativeId"] for row in facts.values()}
    actual = {
        name
        for name, entry in definitions.items()
        if isinstance(entry, dict) and entry.get("properties", {}).get("custodyRole") in {"patrol", "angelo", "escort"}
    }
    test.assertEqual(expected, actual)
    for fact in facts.values():
        name = fact["nativeId"]
        actor = definitions[name]
        properties = actor["properties"]
        test.assertEqual("CCreature", actor["class"])
        test.assertEqual(fact["sourceId"], properties["sourceSpawnFact"])
        test.assertEqual(fact["sourceId"], properties["sourceActor"])
        test.assertEqual(fact["creature"], properties["sourceCreature"])
        test.assertEqual(fact["areas"], [properties["sourceArea"]])
        test.assertEqual(fact["custodyRole"], properties["custodyRole"])
        test.assertEqual((7, 7), (properties["phaseMin"], properties["phaseMax"]))
        test.assertEqual(fact["dialogue"], properties["sourceDialogue"])
        dialog = definitions[name + "Dialog"]
        test.assertEqual("BaldursGateDialog", dialog["class"])
        test.assertEqual(name, dialog["properties"]["actorId"])
        test.assertEqual(properties["label"], dialog["properties"]["speaker"])
        test.assertTrue(dialog["properties"]["states"])
    quest = definitions["cityCustodyQuest"]
    test.assertEqual("BaldursGateCustodyQuest", quest["class"])
    test.assertNotIn("questKey", quest["properties"])
    return facts


class DialogueContentTest(unittest.TestCase):
    def synchronousStoryReaderFixture(self):
        fixture = self.storyReaderFixture()
        fixture.state.update(syncCalls=0, syncError=None, syncTitle=None)

        def synchronous_screen(_handler, title, body, action_label):
            fixture.state["syncCalls"] += 1
            fixture.installPanel(fixture.state["syncTitle"] or title, body, action_label)
            try:
                if fixture.state["syncError"] is not None:
                    raise fixture.state["syncError"]
                for _ in range(4):
                    if fixture.state["panel"] is None:
                        return
                    fixture.pump()
                self.fail("The synchronous native reader was not acknowledged")
            finally:
                fixture.close()

        self.enterContext(patch.object(type(fixture.owner.getGuiHandler()), "showCampaignScreen", synchronous_screen))
        return fixture

    def testStoryReaderDirectJournalCallbackAcknowledgesActualSynchronousReceipt(self):
        fixture = self.synchronousStoryReaderFixture()
        bridge = sys.modules["game"]
        state = {"gold": 1000, "events": [], "flags": {"captain_defeated": True}}

        def addGold(amount):
            state["gold"] += amount
            state["events"].append(("gold", amount))

        player = types.SimpleNamespace(
            getGold=lambda: state["gold"],
            addGold=addGold,
            getItems=lambda: set(),
            getEquipped=lambda: {},
            getNumericProperty=lambda _key: 0,
            checkQuests=lambda: state["events"].append(("checkQuests",)),
        )
        game_map = types.SimpleNamespace(
            getBoolProperty=lambda key: state["flags"].get(key, False),
            setBoolProperty=lambda key, value: state["flags"].__setitem__(key, value),
            getPlayer=lambda: player,
        )
        fixture.owner.getMap = lambda: game_map
        fixture.owner.createWeakResolver = lambda: lambda: fixture.owner

        def complete_scenarioFlow(owner, outcome, *, fallback_map):
            self.assertIs(fixture.owner, owner)
            state["events"].append(("complete", outcome, fallback_map))
            yield from ()

        campaign = types.SimpleNamespace(
            prepareCompletion=lambda owner, outcome, **kwargs: state["events"].append(("prepare", outcome, kwargs)),
            complete_scenarioFlow=complete_scenarioFlow,
        )
        source = ast.parse((ROOT / "res/maps/hearthfall/script.py").read_text(encoding="utf-8"))
        dialog = copy.deepcopy(
            next(node for node in ast.walk(source) if isinstance(node, ast.ClassDef) and node.name == "ElderDialog")
        )
        dialog.decorator_list = []
        dialog.body = [
            node
            for node in dialog.body
            if isinstance(node, ast.FunctionDef) and node.name in {"captain_down", "report_victory"}
        ]
        namespace = dict(
            CDialog=type("DialogBase", (), {"getGame": lambda _self: fixture.owner}),
            resumableHook=fixture.ui.resumableHook,
            flowGame=fixture.ui.flowGame,
            uiRequest=fixture.ui.uiRequest,
            claim_once=bridge.claim_once,
            rewardSnapshot=bridge.rewardSnapshot,
            showRewardReceiptFlow=bridge.showRewardReceiptFlow,
            campaign=campaign,
            VICTORY_GOLD_REWARD=150,
        )
        exec(compile(ast.Module(body=[dialog], type_ignores=[]), "actual_elder_report_callback", "exec"), namespace)
        receiver = namespace["ElderDialog"]()
        fixture.owner.createObject = lambda name: receiver if name == "elderDialog" else None
        runner = ast.parse(fixture.source)
        journal = next(
            node
            for node in ast.walk(runner)
            if isinstance(node, ast.FunctionDef)
            and node.name == "test_quest_journal_keeps_active_and_completed_entries_after_travel"
        )
        direct = next(
            node
            for node in journal.body
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "run_blocking_gui_action"
            and any(
                isinstance(argument, ast.Attribute) and argument.attr == "report_victory"
                for argument in node.value.args
            )
        )
        scope = dict(fixture.namespace, game=fixture.api, g=fixture.owner)
        action = compile(ast.Module(body=[direct], type_ignores=[]), "actual_direct_journal_action", "exec")
        exec(action, scope)
        self.assertEqual(1150, state["gold"])
        self.assertTrue(state["flags"]["victory_reported"])
        self.assertEqual(1, fixture.state["syncCalls"])
        self.assertEqual(1, fixture.state["clicks"])
        self.assertEqual("Hearthfall liberated", fixture.observed[0][0])
        self.assertIn("Gold: +150", fixture.observed[0][1])
        self.assertEqual(("complete", "completed", "gravemoor"), state["events"][-1])
        self.assertEqual(1, state["events"].count(("checkQuests",)))
        exec(action, scope)
        self.assertEqual(1150, state["gold"])
        self.assertEqual(1, fixture.state["clicks"])
        self.assertEqual([], fixture.queue)
        fixture.cleanups[0]()

    def testStoryReaderSynchronousPrimaryFailureCancelsInspectionAndRestoresBothPatches(self):
        fixture = self.synchronousStoryReaderFixture()
        primary = RuntimeError("original synchronous reader failed")
        fixture.state["syncError"] = primary
        with self.assertRaises(RuntimeError) as caught:
            fixture.ui.showReader(fixture.owner, "Title", "Body")
        self.assertIs(primary, caught.exception)
        self.assertEqual(1, len(fixture.queue))
        fixture.pump()
        self.assertEqual(0, fixture.state["reads"])
        self.assertIsNone(fixture.state["panel"])
        with self.assertRaisesRegex(AssertionError, "original synchronous reader failed"):
            fixture.cleanups[0]()
        fixture.cleanups[-1]()
        self.assertEqual(
            ("showReader", "showReaderFlow"), (fixture.ui.showReader.__name__, fixture.ui.showReaderFlow.__name__)
        )

    def testStoryReaderSynchronousRepeatedCallsCaptureRealTextAndRejectForeignPanel(self):
        fixture = self.synchronousStoryReaderFixture()
        fixture.ui.showReader(fixture.owner, "First", "First body")
        fixture.ui.uiTarget("showReader")(fixture.owner, "Second", "Second body")
        self.assertEqual([("First", "First body"), ("Second", "Second body")], fixture.observed)
        self.assertEqual(2, fixture.state["clicks"])
        self.assertEqual([], fixture.queue)
        fixture.state["syncTitle"] = "Foreign panel"
        with self.assertRaises(AssertionError) as caught:
            fixture.ui.showReader(fixture.owner, "Expected", "Third body")
        self.assertIn("Foreign panel", str(caught.exception))
        self.assertEqual(2, fixture.state["clicks"])
        self.assertIsNone(fixture.state["panel"])
        with self.assertRaises(AssertionError):
            fixture.cleanups[0]()

    def testStoryReaderSynchronousRejectedQueueStopsBeforeNativeScreen(self):
        fixture = self.synchronousStoryReaderFixture()
        fixture.state["acceptQueue"] = False
        with self.assertRaises(AssertionError):
            fixture.ui.showReader(fixture.owner, "Title", "Body")
        self.assertEqual(0, fixture.state["syncCalls"])
        self.assertEqual(0, fixture.state["clicks"])
        self.assertEqual([], fixture.queue)

    def storyReaderFixture(self):
        import traceback
        from functools import wraps
        from weakref import ref

        source = (ROOT / "test.py").read_text(encoding="utf-8")
        names = {
            "captureStoryReaders",
            "queuePanelInspection",
            "finishPanelInspection",
            "run_blocking_panel_inspection",
            "run_blocking_gui_action",
            "queue_sdl_inputs",
        }
        selected = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name in names]
        queue, cleanups = [], []
        state = {"panel": None, "reads": 0, "clicks": 0, "shutdown": False, "acceptQueue": True}

        def invoke(callback):
            if not state["acceptQueue"]:
                return False
            queue.append(callback)
            return True

        def pump():
            self.assertTrue(queue, "The native request is still pending without a staged panel acknowledgment")
            queue.pop(0)()

        class NativeHandler:
            def showCampaignScreen(self, *_args):
                raise AssertionError("The native async dispatcher must not call the patched synchronous method")

        def findPanel(_owner, class_name):
            state["reads"] += 1
            panel = state["panel"]
            return panel if panel is not None and panel.kind == class_name else None

        def close():
            state["panel"] = None

        def shutdown():
            state["shutdown"] = True
            close()

        gui = types.SimpleNamespace(notify=lambda _text: None, removeChild=lambda _panel: close())
        handler = NativeHandler()
        owner = types.SimpleNamespace(
            getGuiHandler=lambda: handler,
            getGui=lambda: gui,
            getContext=lambda: types.SimpleNamespace(shutdown=shutdown),
        )
        api = types.SimpleNamespace(
            CGuiHandler=NativeHandler,
            event_loop=types.SimpleNamespace(instance=lambda: types.SimpleNamespace(invoke=invoke)),
        )
        ui = types.ModuleType("ui")
        ui.__dict__.update(wraps=wraps, ref=ref)
        ui_source = ast.parse((ROOT / "res/ui.py").read_text(encoding="utf-8"))
        ui_nodes = [
            node
            for node in ui_source.body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))
            and node.name
            in {
                "uiRequest",
                "uiGame",
                "UiFlowGame",
                "flowGame",
                "ResumableHook",
                "resumableHook",
                "showReader",
                "showReaderFlow",
                "uiTarget",
                "runUiFlow",
            }
        ]
        exec(compile(ast.Module(body=ui_nodes, type_ignores=[]), "actual_reader_flow", "exec"), ui.__dict__)
        game_nodes = [
            node
            for node in ast.parse((ROOT / "res/game.py").read_text(encoding="utf-8")).body
            if isinstance(node, ast.FunctionDef)
            and node.name
            in {"showReader", "rewardSnapshot", "rewardReceiptText", "showRewardReceiptFlow", "claim_once"}
        ]
        bridge = types.ModuleType("game")
        bridge.__dict__.update(flowGame=ui.flowGame, uiRequest=ui.uiRequest)
        exec(compile(ast.Module(body=game_nodes, type_ignores=[]), "actual_reader_bridge", "exec"), bridge.__dict__)
        self.enterContext(patch.dict(sys.modules, {"ui": ui, "game": bridge}))

        def activate(button, actual_gui):
            self.assertIs(gui, actual_gui)
            self.assertIs(state["panel"].button, button)
            state["clicks"] += 1
            close()

        namespace = {
            "traceback": traceback,
            "find_top_level_panel": findPanel,
            "find_descendants_by_type": lambda panel, _kind: [panel.button],
            "activate_widget": activate,
            "pump_event_loop": lambda _count: None,
        }
        exec(compile(ast.Module(body=selected, type_ignores=[]), "actual_story_reader_helpers", "exec"), namespace)
        receiver = types.SimpleNamespace(addCleanup=lambda callback: cleanups.append(callback))
        for name in ("assertFalse", "assertEqual", "assertTrue", "assertIn", "assertLessEqual"):
            setattr(receiver, name, getattr(self, name))
        observed = namespace["captureStoryReaders"](receiver, api, owner)
        self.addCleanup(lambda: [callback() for callback in reversed(cleanups[1:])])

        def installPanel(title, body, action="Continue"):
            properties = {"title": title, "body": body, "actionLabel": action}
            button = types.SimpleNamespace(getStringProperty=lambda key: "clickAction" if key == "click" else "")
            state["panel"] = types.SimpleNamespace(
                kind="CGameCampaignPanel",
                getStringProperty=lambda key: properties[key],
                button=button,
                close=close,
            )

        def begin(title="Actual title", body="Actual story body"):
            flow = ui.uiTarget("showReader", resumable=True)(owner, title, body)
            request = next(flow)
            self.assertEqual(
                {"operation": "gui.showCampaignScreen", "args": (title, body, "Continue"), "kwargs": {}}, request
            )
            return flow

        return types.SimpleNamespace(
            source=source,
            namespace=namespace,
            queue=queue,
            state=state,
            pump=pump,
            ui=ui,
            owner=owner,
            api=api,
            observed=observed,
            installPanel=installPanel,
            begin=begin,
            cleanups=cleanups,
            close=close,
            gui=gui,
        )

    def testStoryReaderCaptureAcknowledgesActualResumablePanel(self):
        fixture = self.storyReaderFixture()
        flow = fixture.begin()
        fixture.installPanel("Actual title", "Actual story body")
        fixture.pump()
        self.assertIsNone(fixture.state["panel"])
        with self.assertRaises(StopIteration):
            flow.send(None)
        self.assertEqual([("Actual title", "Actual story body")], fixture.observed)
        self.assertEqual(1, fixture.state["clicks"])
        self.assertEqual([], fixture.queue)
        fixture.cleanups[0]()

    def testStoryReaderCaptureChecksActualPanelTextAndSurfacesFailure(self):
        fixture = self.storyReaderFixture()
        flow = fixture.begin()
        fixture.installPanel("Foreign title", "Actual story body")
        fixture.pump()
        failure = None
        try:
            flow.send(None)
        except AssertionError as error:
            failure = error
        except StopIteration:
            pass
        self.assertIsNotNone(failure, "A foreign reader must fail its actual panel proof")
        self.assertEqual([], fixture.observed)
        self.assertEqual(0, fixture.state["clicks"])
        self.assertIsNone(fixture.state["panel"])
        with self.assertRaises(AssertionError):
            fixture.cleanups[0]()

    def testStoryReaderCaptureCancelsQueuedInspectorWhenFlowCloses(self):
        fixture = self.storyReaderFixture()
        flow = fixture.begin()
        self.assertEqual(1, len(fixture.queue))
        flow.close()
        fixture.pump()
        self.assertEqual(0, fixture.state["reads"])
        self.assertEqual(0, fixture.state["clicks"])
        fixture.cleanups[0]()

    def testStoryReaderCapturePreservesPrimaryFlowErrorAndRestoresPatch(self):
        fixture = self.storyReaderFixture()
        flow = fixture.begin()
        primary = RuntimeError("original reader failed")
        with self.assertRaises(RuntimeError) as caught:
            flow.throw(primary)
        self.assertIs(primary, caught.exception)
        fixture.pump()
        self.assertEqual(0, fixture.state["reads"])
        with self.assertRaisesRegex(AssertionError, "original reader failed"):
            fixture.cleanups[0]()
        fixture.cleanups[-1]()
        self.assertEqual("showReaderFlow", fixture.ui.showReaderFlow.__name__)

    def testStoryReaderCaptureRefusesRejectedQueueAndBoundsMissingPanel(self):
        fixture = self.storyReaderFixture()
        fixture.state["acceptQueue"] = False
        with self.assertRaises(AssertionError):
            fixture.begin()
        self.assertEqual([], fixture.queue)
        fixture.state["acceptQueue"] = True
        flow = fixture.begin()
        for _ in range(1001):
            fixture.pump()
        self.assertTrue(fixture.state["shutdown"])
        self.assertEqual([], fixture.queue)
        with self.assertRaisesRegex(AssertionError, "not visible"):
            flow.send(None)

    def testJournalTravelStagesNumericInputAfterActualElderDialog(self):
        fixture = self.storyReaderFixture()
        method = next(
            node
            for node in ast.walk(ast.parse(fixture.source))
            if isinstance(node, ast.FunctionDef)
            and node.name == "test_quest_journal_keeps_active_and_completed_entries_after_travel"
        )
        move = next(node for node in method.body if isinstance(node, ast.FunctionDef) and node.name == "moveToObject")
        state = {"position": None, "premature": 0, "selected": 0}

        def choose():
            if fixture.state["panel"] is None:
                state["premature"] += 1
                return
            state["selected"] += 1
            fixture.close()

        def moveTo(*target):
            for _ in range(3):
                if fixture.queue:
                    fixture.pump()
            fixture.state["panel"] = types.SimpleNamespace(
                kind="CGameDialogPanel",
                close=fixture.close,
                getObjectProperty=lambda key: (
                    types.SimpleNamespace(getTypeId=lambda: "elderDialog") if key == "dialog" else None
                ),
            )
            for _ in range(6):
                if fixture.state["panel"] is None:
                    state["position"] = target
                    return
                if fixture.queue:
                    fixture.pump()
            self.fail("The real dialog was left pending after movement")

        namespace = dict(fixture.namespace)
        namespace.update(
            self=self,
            game=fixture.api,
            g=fixture.owner,
            player=types.SimpleNamespace(moveTo=moveTo, getCoords=lambda: state["position"]),
            find_map_object_definition=lambda *_args: {"x": 96, "y": 64},
            coords_tuple=lambda value: value,
        )
        exec(compile(ast.Module(body=[move], type_ignores=[]), "actual_journal_travel_move", "exec"), namespace)
        namespace["moveToObject"]("hearthfall", "elderMaren", choose)
        self.assertEqual({"position": (3, 2, 0), "premature": 0, "selected": 1}, state)

    def testJournalTravelUsesFlowReadersWithoutPrequeuedSpace(self):
        source = (ROOT / "test.py").read_text(encoding="utf-8")
        method = next(
            node
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.FunctionDef)
            and node.name == "test_quest_journal_keeps_active_and_completed_entries_after_travel"
        )
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
        self.assertEqual(
            1, sum(isinstance(node.func, ast.Name) and node.func.id == "captureStoryReaders" for node in calls)
        )
        self.assertFalse(any(isinstance(node, ast.Name) and node.id == "push_space_key" for node in ast.walk(method)))
        self.assertIn("push_digit_key(2)", ast.unparse(method))

    def testStoryReaderNativeDispatchBypassesSynchronousPythonPatch(self):
        cpp = (ROOT / "src/handler/CGuiHandler.cpp").read_text(encoding="utf-8")
        start = cpp.index('operation == "showCampaignScreen"')
        branch = cpp[start : cpp.index("} else if", start)]
        self.assertIn("co_await self->showCampaignScreenAsync", branch)
        self.assertNotIn('attr("showCampaignScreen")', branch)
        ui_source = (ROOT / "res/ui.py").read_text(encoding="utf-8")
        tree = ast.parse(ui_source)
        target = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "uiTarget")
        self.assertIn("globals()", ast.unparse(target))
        flow = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "showReaderFlow")
        self.assertIn("gui.showCampaignScreen", ast.unparse(flow))

    def testDialoguePunctuationHasValidUnicodeInsteadOfMojibake(self):
        text = (ROOT / "res/maps/nouraajd/dialog.json").read_text(encoding="utf-8")
        self.assertIn("Matulog\u2019s", text)
        self.assertIn("Hmph\u2026", text)
        for path in (ROOT / "res/maps").glob("*/*.json"):
            definitions = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(definitions, dict):
                continue
            for name, definition in definitions.items():
                if not isinstance(definition, dict) or not definition.get("properties", {}).get("states"):
                    continue
                dialogue = json.dumps(definition, ensure_ascii=False)
                for marker in ("\ufffd", "\u00e2\u0080", "\u00e2\u20ac", "\u00c3\u00a2", "\u00ef\u00bf\u00bd"):
                    self.assertNotIn(marker, dialogue, (path.name, name, ascii(marker)))

    def testAcceptanceCommitsAtPromiseAndFarewellHasNoAction(self):
        states = dialogueStates("res/maps/nouraajd/config.json", "questDialog")
        promise = next(
            option["properties"]
            for option in states["OLD_WOMAN_HELLO"]["options"]
            if option["properties"].get("nextStateId") == "ACCEPT_QUEST"
        )
        self.assertEqual("start_amulet_quest", promise.get("action"))
        for option in states["ACCEPT_QUEST"]["options"]:
            self.assertFalse(option.get("properties", {}).get("action"))
        decline = next(
            option["properties"]
            for option in states["OLD_WOMAN_HELLO"]["options"]
            if option["properties"].get("nextStateId") == "DECLINE_QUEST"
        )
        self.assertFalse(decline.get("action"))

    def testHandInNamesTheActionAndReward(self):
        states = dialogueStates("res/maps/nouraajd/config.json", "questReturnDialog")
        hand_in = states["ENTRY"]["options"][0]["properties"]
        self.assertEqual("complete_amulet_quest", hand_in["action"])
        self.assertIn("amulet", hand_in.get("text", "").lower())
        self.assertIn("50 gold", hand_in.get("actionLabel", ""))

    def testEveryAuthoredDialogueHasASpeakerAndValidRoutes(self):
        counts = {}
        custody_facts = {}
        base = {}
        for path in (ROOT / "res/config").glob("*.json"):
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                base.update(value)
        for map_dir in (ROOT / "res/maps").iterdir():
            if not map_dir.is_dir():
                continue
            definitions = dict(base)
            documents = []
            script_path = map_dir / "script.py"
            classes = (
                {
                    node.name: node
                    for node in ast.walk(ast.parse(script_path.read_text(encoding="utf-8")))
                    if isinstance(node, ast.ClassDef)
                }
                if script_path.exists()
                else {}
            )
            for path in map_dir.glob("*.json"):
                value = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    definitions.update(value)
                    documents.append(value)

            if map_dir.name == "baldursGate":
                custody_facts = assertCustodyDialogueProvenance(
                    self, definitions, readJson("tests/fixtures/baldurs_gate_city_prison_source.json")
                )

            def resolve(option, seen=()):
                ref = option.get("ref")
                result = resolve(definitions[ref], seen + (ref,)) if ref and ref not in seen else {}
                result.update(option.get("properties", {}))
                return result

            for document in documents:
                for dialog_id, definition in document.items():
                    if not isinstance(definition, dict):
                        continue
                    properties = definition.get("properties", {})
                    states = properties.get("states")
                    if not isinstance(states, list):
                        continue
                    counts[map_dir.name] = counts.get(map_dir.name, 0) + 1
                    self.assertTrue(properties.get("speaker"), (map_dir.name, dialog_id))
                    state_ids = {state["properties"]["stateId"] for state in states} | {"EXIT", ""}
                    self.assertIn("ENTRY", state_ids)
                    for state in states:
                        numbers = []
                        for option in state["properties"].get("options", []):
                            option = resolve(option)
                            self.assertIn(option.get("nextStateId", ""), state_ids)
                            self.assertIn(option.get("afterStateId", ""), state_ids)
                            for hook in ("action", "condition", "afterCondition"):
                                name = option.get(hook)
                                if name:
                                    class_node = classes[definition["class"]]
                                    methods = {
                                        method.name for method in class_node.body if isinstance(method, ast.FunctionDef)
                                    }
                                    self.assertIn(name, methods, (map_dir.name, dialog_id, hook))
                            numbers.append(option["number"])
                            if option.get("text") == "Leave":
                                self.assertFalse(option.get("action"), (map_dir.name, dialog_id))
                        self.assertEqual(len(numbers), len(set(numbers)))
        self.assertEqual(
            {
                "baldursGate": 2124 + len(custody_facts),
                "candlekeep": 84,
                "castleGriffinCliff": 2,
                "castleGuardianAngels": 2,
                "castleHomecoming": 2,
                "gravemoor": 1,
                "hearthfall": 1,
                "kadath": 2,
                "ninemarches": 5,
                "nouraajd": 9,
                "ritual": 3,
                "sunderedmarch": 1,
                "usurpergate": 1,
                "vhulmarn": 2,
            },
            counts,
            "Every authored map's conversations must be included in the structural audit.",
        )

    def companionEnvironment(self):
        player = FakePlayer()
        game_map = FakeMap(player)
        messages = []
        game = types.SimpleNamespace(
            getMap=lambda: game_map,
            getGui=lambda: None,
            getGuiHandler=lambda: types.SimpleNamespace(
                showCampaignScreen=lambda *args: messages.append(args), notify=messages.append
            ),
        )
        namespace = {
            "CDialog": FakeDialog,
            "has_item": lambda player, item: player.countItems(item) > 0,
            "ensure_quest": lambda player, quest: player.quests.append(quest),
            "reputation": lambda game_map: game_map.standing,
            "adjust_reputation": lambda game_map, amount: setattr(game_map, "standing", game_map.standing + amount),
        }
        from tests.test_ui_presentation import loadPresentation

        namespace.update(loadPresentation())
        loadClasses(
            "res/maps/ninemarches/script.py",
            ["CompanionDialog", "KnightDialog", "WitchDialog", "SellswordDialog"],
            namespace,
        )
        return namespace, game, game_map, player

    def testCompanionReminderExistsOnlyWhileTheItemIsOutstanding(self):
        for class_name in ("KnightDialog", "WitchDialog", "SellswordDialog"):
            namespace, game, game_map, player = self.companionEnvironment()
            dialog = namespace[class_name]()
            dialog.game = game
            self.assertFalse(dialog.questInProgress())
            dialog.start()
            self.assertTrue(dialog.questInProgress())
            player.addItem(dialog.ITEM)
            self.assertFalse(dialog.questInProgress())
            dialog.recruit()
            self.assertFalse(dialog.questInProgress())
            self.assertTrue(game_map.getBoolProperty(dialog.JOINED_FLAG))

    def testDepartureRoutesToDepartureSpeechAfterBanter(self):
        for class_name, dialog_id, standing in (
            ("KnightDialog", "knightDialog", -5),
            ("WitchDialog", "witchDialog", -5),
            ("SellswordDialog", "sellswordDialog", 5),
        ):
            namespace, game, game_map, _player = self.companionEnvironment()
            dialog = namespace[class_name]()
            dialog.game = game
            game_map.setBoolProperty(dialog.JOINED_FLAG, True)
            game_map.standing = standing
            dialog.banter()
            states = dialogueStates("res/maps/ninemarches/dialog.json", dialog_id)
            banter = next(
                option["properties"]
                for option in states["ENTRY"]["options"]
                if option.get("properties", {}).get("action") == "banter"
            )
            self.assertTrue(getattr(dialog, banter["afterCondition"])())
            self.assertEqual("GONE", banter["afterStateId"])

    def testSeerReminderDisappearsWhenBannerCanBeReturned(self):
        player = FakePlayer()
        game_map = FakeMap(player)
        namespace = {
            "CDialog": FakeDialog,
            "has_item": lambda player, item: player.countItems(item) > 0,
            "ensure_quest": lambda player, quest: player.quests.append(quest),
        }
        loadClasses("res/maps/sunderedmarch/script.py", ["SeerDialog"], namespace)
        dialog = namespace["SeerDialog"]()
        dialog.game = types.SimpleNamespace(getMap=lambda: game_map)
        self.assertFalse(dialog.questInProgress())
        dialog.start_seer_hunt()
        self.assertTrue(dialog.questInProgress())
        player.addItem("warBanner")
        self.assertFalse(dialog.questInProgress())
        game_map.setBoolProperty("seer_done", True)
        self.assertFalse(dialog.questInProgress())

    def testVictorReceiptUsesExposedStatePropertiesAndCompletesOnce(self):
        from tests.test_ui_presentation import loadPresentation

        player = FakePlayer()
        game_map = FakeMap(player)
        healing, receipts, trades, cleared = [], [], [], []
        player.addGold = lambda amount: setattr(player, "gold", player.gold + amount)
        player.healProc = healing.append
        authored_text = dialogueStates("res/maps/nouraajd/dialog3.json", "victorRewardDialog")["ENTRY"]["text"]
        # Model the existing Python binding: states expose properties, not native getState/getText methods.
        entry = types.SimpleNamespace(getStringProperty=lambda name: {"stateId": "ENTRY", "text": authored_text}[name])
        reward_dialog = types.SimpleNamespace(getStates=lambda: [entry])
        progress = {"state": "encounter_active"}
        quest_system = types.SimpleNamespace(
            get_state=lambda name: progress["state"],
            mark_victor_good_end=lambda: progress.update(state="good_end"),
        )
        handler = types.SimpleNamespace(showCampaignScreen=lambda *args: receipts.append(args), showTrade=trades.append)
        game = types.SimpleNamespace(
            getMap=lambda: game_map,
            getGui=lambda: None,
            getGuiHandler=lambda: handler,
            createObject=lambda name: reward_dialog if name == "victorRewardDialog" else name,
        )

        def claimOnce(map_instance, flag):
            if map_instance.getBoolProperty(flag):
                return False
            map_instance.setBoolProperty(flag, True)
            return True

        def clearFlow(game_map):
            cleared.append(game_map)
            yield from ()

        namespace = loadPresentation()
        namespace.update(
            CTrigger=FakeDialog,
            _quest_system_from=lambda owner: quest_system,
            claim_once=claimOnce,
            clearVictorEncounterFlow=clearFlow,
            narrative=types.SimpleNamespace(victorResponse=lambda game: ""),
        )
        loadClasses("res/maps/nouraajd/script.py", ["CultLeaderQuestTrigger"], namespace)
        trigger = namespace["CultLeaderQuestTrigger"]()
        trigger.game = game
        trigger.trigger(None, None)
        self.assertEqual("good_end", progress["state"])
        self.assertEqual(510, player.gold)
        self.assertEqual([100], healing)
        self.assertEqual(1, len(receipts))
        self.assertIn(authored_text, receipts[0][1])
        self.assertIn("Gold: +500", receipts[0][1])
        self.assertEqual("Continue", receipts[0][2])
        self.assertEqual(["victorMarket"], trades)
        self.assertEqual([game_map], cleared)
        trigger.trigger(None, None)
        self.assertEqual(510, player.gold)
        self.assertEqual(1, len(receipts))

    def testHazardFeedbackDoesNotBlockTheRitual(self):
        tree = ast.parse((ROOT / "res/maps/ritual/script.py").read_text())
        classes = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        for name in ("HazardNorthTrigger", "HazardCenterTrigger", "HazardSouthTrigger", "RitualTurnTrigger"):
            calls = {
                node.func.attr
                for node in ast.walk(classes[name])
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            }
            self.assertIn("notify", calls)
            self.assertNotIn("showMessage", calls)
        arrival_calls = {
            node.func.id
            for node in ast.walk(classes["StartEvent"])
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertIn("uiRequest", arrival_calls)
        self.assertTrue(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "uiRequest"
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "showReader"
                for node in ast.walk(classes["StartEvent"])
            )
        )

    def testQuestContextReferencesOnlyExistingQuestDefinitions(self):
        conversations = 0
        candlekeep_contexts = {}
        city_contexts = {}
        for map_dir in (ROOT / "res/maps").iterdir():
            if not map_dir.is_dir():
                continue
            config_path = map_dir / "config.json"
            if not config_path.exists():
                continue
            config = json.loads(config_path.read_text(encoding="utf-8"))
            for path in map_dir.glob("*.json"):
                for identity, definition in json.loads(path.read_text(encoding="utf-8")).items():
                    if not isinstance(definition, dict):
                        continue
                    properties = definition.get("properties", {})
                    if "questIds" not in properties:
                        continue
                    conversations += 1
                    if map_dir.name == "baldursGate":
                        city_contexts[identity] = tuple(properties["questIds"].split(","))
                    if map_dir.name == "candlekeep":
                        candlekeep_contexts[identity] = tuple(properties["questIds"].split(","))
                    self.assertIn("states", properties, (map_dir.name, identity))
                    for quest_id in properties["questIds"].split(","):
                        self.assertIn(quest_id, config, (map_dir.name, identity, quest_id))
                        self.assertTrue(config[quest_id]["class"].endswith("Quest"))
        self.assertEqual(
            {
                "firebeadDialog": ("firebeadQuest",),
                "phlydiaDialog": ("phlydiaQuest",),
                "dreppinDialog": ("dreppinQuest",),
                "hullDialog": ("hullQuest",),
                "fullerDialog": ("fullerQuest",),
                "reevorDialog": ("reevorQuest",),
            },
            candlekeep_contexts,
        )
        self.assertEqual(56, len(city_contexts))
        self.assertEqual(24, conversations - len(candlekeep_contexts) - len(city_contexts))
        self.assertEqual(86, conversations)

    def testRitualRecordDescribesActualTurnCadence(self):
        tree = ast.parse((ROOT / "res/maps/ritual/script.py").read_text())
        cadence = {}
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Compare)
                and isinstance(node.left, ast.BinOp)
                and isinstance(node.left.right, ast.Name)
                and node.left.right.id in ("last_wave", "last_tick")
                and isinstance(node.comparators[0], ast.Constant)
            ):
                cadence[node.left.right.id] = node.comparators[0].value
        records = dialogueStates("res/maps/ritual/config.json", "recordsDialog")["ENTRY"]["text"].lower()
        number_words = {4: "four", 5: "five"}
        self.assertIn(f"every {number_words[cadence['last_wave']]} turns", records)
        self.assertIn(f"every {number_words[cadence['last_tick']]} turns", records)

    def testCustodyDialogueCountComesFromDistinctAuditedSpawnRecords(self):
        from copy import deepcopy

        prison = readJson("tests/fixtures/baldurs_gate_city_prison_source.json")
        facts = custodyScriptedActorFacts(prison)
        self.assertEqual(23, len(facts))
        self.assertEqual(18, sum(row["custodyRole"] == "patrol" for row in facts.values()))
        self.assertEqual(1, sum(row["creature"] == "ANGELO" for row in facts.values()))
        self.assertEqual(4, sum(row["custodyRole"] == "escort" for row in facts.values()))
        self.assertNotIn("NEB", {row["creature"] for row in facts.values()})
        for mutation in ("duplicateOffset", "wrongChapter", "unsupportedChapterOpcode", "missingEscort"):
            with self.subTest(mutation=mutation):
                changed = deepcopy(prison)
                if mutation == "duplicateOffset":
                    offsets = changed["patrols"]["AR0100"]["spawnRecordOffsets"]
                    offsets[1] = offsets[0]
                elif mutation in ("wrongChapter", "unsupportedChapterOpcode"):
                    for condition in changed["patrols"]["AR0100"]["conditions"]:
                        if condition["strings"][0] == "GLOBALChapter":
                            if mutation == "wrongChapter":
                                condition["integerFields"][0] = 6
                            else:
                                condition["opcode"] = 1
                else:
                    changed["scenes"]["CAPCUT01"] = [
                        row
                        for row in changed["scenes"]["CAPCUT01"]
                        if not (row["op"] == "CreateCreature" and row["strings"][0] == "FLAME4")
                    ]
                with self.assertRaises(ValueError):
                    custodyScriptedActorFacts(changed)


def loadCrafting():
    fake_game = types.ModuleType("game")
    fake_game.randint = lambda lower, upper: upper
    fake_game.CResourcesProvider = types.SimpleNamespace(
        getInstance=lambda: types.SimpleNamespace(load=lambda filename: "{}")
    )
    fake_game.list_string = lambda game, options: list(options)
    installHookFlows(fake_game)
    with patch.dict(sys.modules, {"game": fake_game}):
        spec = importlib.util.spec_from_file_location("ui_crafting_under_test", ROOT / "res/plugins/crafting.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class CraftingChoiceTest(unittest.TestCase):
    def setUp(self):
        self.module = loadCrafting()
        self.runtime = self.module.CraftingRuntime()
        self.runtime._item_labels = {"Herb": "Herb", "PotionA": "Elixir", "PotionB": "Elixir"}
        self.player = FakePlayer()
        FakeMap(self.player)
        self.player.addItem("Herb")
        self.recipe = {
            "id": "firstRecipe",
            "display_name": "Elixir",
            "station": "alchemy",
            "inputs": [{"item_id": "Herb", "count": 1}],
            "outputs": [{"item_id": "PotionA", "count": 1}],
            "gold": 3,
            "success_chance": 100,
            "unlock": {"type": "none", "value": None},
            "unlock_hint": "",
        }

    def runStation(self, selected_id):
        menus = []

        def choose(title, payload, action, back):
            menus.append((title, json.loads(payload), action, back))
            return selected_id if len(menus) == 1 else ""

        handler = types.SimpleNamespace(showChoice=choose)
        game = types.SimpleNamespace(
            getGuiHandler=lambda: handler,
            getObjectHandler=lambda: types.SimpleNamespace(createObject=lambda game, item_id: FakeItem(item_id)),
        )
        station = types.SimpleNamespace(
            getGame=lambda: game,
            getStringProperty=lambda name: {"craftingStationId": "alchemy", "label": "Alchemy"}.get(name, ""),
        )
        self.module._RUNTIME = self.runtime
        self.module.open_crafting_station(station, self.player)
        return menus

    def testDuplicateLabelsReturnStableIdsAndRefreshCosts(self):
        second = copy.deepcopy(self.recipe)
        second.update(id="secondRecipe", outputs=[{"item_id": "PotionB", "count": 1}])
        self.runtime._recipes = {self.recipe["id"]: self.recipe, second["id"]: second}
        menus = self.runStation("secondRecipe")
        self.assertEqual(["firstRecipe", "secondRecipe"], [choice["id"] for choice in menus[0][1]])
        self.assertEqual(["Elixir", "Elixir"], [choice["label"] for choice in menus[0][1]])
        self.assertEqual(1, self.player.countItems("PotionB"))
        self.assertEqual(0, self.player.countItems("PotionA"))
        self.assertEqual(7, self.player.gold)
        self.assertFalse(menus[1][1][1]["enabled"])
        self.assertEqual([False, True], [choice.get("selected", False) for choice in menus[1][1]])
        self.assertIn("Herb: 0 / 1", menus[1][1][1]["detail"])
        self.assertIn("You crafted Elixir.", menus[1][1][1]["detail"])
        self.assertNotIn("Last result", menus[1][1][0]["detail"])
        self.assertNotIn("secondRecipe", menus[0][1][1]["detail"])

    def testFailedSecondRecipeRetainsSelectionAndItsOwnResult(self):
        second = copy.deepcopy(self.recipe)
        second.update(id="secondRecipe", display_name="Mana potion", gold=7, success_chance=0)
        self.runtime._recipes = {self.recipe["id"]: self.recipe, second["id"]: second}
        menus = self.runStation("secondRecipe")
        self.assertEqual(["firstRecipe", "secondRecipe"], [choice["id"] for choice in menus[1][1]])
        self.assertEqual([False, True], [choice.get("selected", False) for choice in menus[1][1]])
        self.assertFalse(menus[1][1][1]["enabled"], "The consumed recipe remains inspectable with no ingredients left")
        self.assertIn("Herb: 0 / 1", menus[1][1][1]["detail"])
        self.assertIn("Gold: 3 owned / 7 needed", menus[1][1][1]["detail"])
        self.assertIn("The listed reagents and gold were consumed", menus[1][1][1]["detail"])
        self.assertNotIn("Last result", menus[1][1][0]["detail"])
        self.assertEqual(0, self.player.countItems("PotionA"))
        self.assertEqual(3, self.player.gold)

    def testFailedCraftDisclosesAndConsumesItsCost(self):
        self.recipe["success_chance"] = 0
        self.runtime._recipes = {self.recipe["id"]: self.recipe}
        menus = self.runStation("firstRecipe")
        self.assertIn("spent even if crafting fails", menus[0][1][0]["detail"])
        self.assertEqual(0, self.player.countItems("Herb"))
        self.assertEqual(0, self.player.countItems("PotionA"))
        self.assertEqual(7, self.player.gold)
        self.assertIn("The listed reagents and gold were consumed", menus[1][1][0]["detail"])

    def testLockedRecipeExplainsUnlockAndCannotBeCrafted(self):
        self.recipe.update(unlock={"type": "flag", "value": "recipeUnlocked"}, unlock_hint="Speak with Beren.")
        self.runtime._recipes = {self.recipe["id"]: self.recipe}
        menus = self.runStation("firstRecipe")
        self.assertFalse(menus[0][1][0]["enabled"])
        self.assertIn("Speak with Beren.", menus[0][1][0]["detail"])
        self.assertEqual(1, self.player.countItems("Herb"))
        self.assertEqual(10, self.player.gold)
        self.assertEqual(0, self.player.countItems("PotionA"))

    def testBackOrUnknownChoiceNeverConsumesMaterials(self):
        self.runtime._recipes = {self.recipe["id"]: self.recipe}
        self.runStation("unknownRecipe")
        self.assertEqual(1, self.player.countItems("Herb"))
        self.assertEqual(10, self.player.gold)


if __name__ == "__main__":
    unittest.main()
