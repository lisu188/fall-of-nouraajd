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


class DialogueContentTest(unittest.TestCase):
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
        count = 0
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
                    count += 1
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
        self.assertEqual(25, count)

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

        namespace = loadPresentation()
        namespace.update(
            CTrigger=FakeDialog,
            _quest_system_from=lambda owner: quest_system,
            claim_once=claimOnce,
            _clear_victor_encounter=cleared.append,
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
        self.assertIn("showReader", arrival_calls)

    def testQuestContextReferencesOnlyExistingQuestDefinitions(self):
        conversations = 0
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
                    self.assertIn("states", properties, (map_dir.name, identity))
                    for quest_id in properties["questIds"].split(","):
                        self.assertIn(quest_id, config, (map_dir.name, identity, quest_id))
                        self.assertTrue(config[quest_id]["class"].endswith("Quest"))
        self.assertEqual(24, conversations)

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


def loadCrafting():
    fake_game = types.ModuleType("game")
    fake_game.randint = lambda lower, upper: upper
    fake_game.CResourcesProvider = types.SimpleNamespace(
        getInstance=lambda: types.SimpleNamespace(load=lambda filename: "{}")
    )
    fake_game.list_string = lambda game, options: list(options)
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
        self.assertIn("Herb: 0 / 1", menus[1][1][1]["detail"])
        self.assertIn("You crafted Elixir.", menus[1][1][1]["detail"])
        self.assertNotIn("secondRecipe", menus[0][1][1]["detail"])

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
