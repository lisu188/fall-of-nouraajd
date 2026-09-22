# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


def loadPresentation():
    path = Path(__file__).resolve().parents[1] / "res/game.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {"showReader", "rewardSnapshot", "showRewardReceipt", "requirementMessage"}
    module = ast.Module(
        body=[node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names], type_ignores=[]
    )
    namespace = {}
    exec(compile(module, str(path), "exec"), namespace)
    return namespace


class RewardReceiptTest(unittest.TestCase):
    def testReceiptReportsOnlyObservedGainsAndAcknowledgmentCannotGrantAgain(self):
        presentation = loadPresentation()

        class Item:
            def __init__(self, identity, label):
                self.identity, self.label = identity, label

            def getTypeId(self):
                return self.identity

            def getStringProperty(self, _name):
                return self.label

        old = Item("oldSword", "Old sword")
        crown = Item("crown", "The crown")
        potion = Item("potion", "Life Potion")
        inventory = [old]
        equipment = {}
        resources = {"gold": 100, "experience": 50}
        player = SimpleNamespace(
            getItems=lambda: inventory,
            getEquipped=lambda: equipment,
            getGold=lambda: resources["gold"],
            getNumericProperty=lambda name: resources["experience"],
        )
        screens, history = [], []
        handler = SimpleNamespace(showCampaignScreen=lambda *args: screens.append(args))
        instance = SimpleNamespace(
            getMap=lambda: SimpleNamespace(getPlayer=lambda: player),
            getGui=lambda: SimpleNamespace(notify=history.append),
            getGuiHandler=lambda: handler,
        )
        before = presentation["rewardSnapshot"](player)
        resources.update(gold=400, experience=800)
        inventory.append(potion)
        equipment[1] = crown
        equipment[2] = crown
        for _acknowledgment in range(2):
            presentation["showRewardReceipt"](instance, "The captive is free", before, "The rescued soul thanks you.")
        self.assertEqual({"gold": 400, "experience": 800}, resources)
        self.assertEqual([old, potion], inventory)
        self.assertEqual(2, len(screens))
        title, body, action = screens[0]
        self.assertEqual("The captive is free", title)
        self.assertEqual("Continue", action)
        self.assertIn("Gold: +300", body)
        self.assertIn("Experience: +750", body)
        self.assertIn("Life Potion: +1", body)
        self.assertIn("The crown: +1", body)
        self.assertNotIn("Old sword", body)
        self.assertEqual([title + "\n" + body] * 2, history)

    def testSpentItemsAndGoldAreNotMisreportedAsRewards(self):
        presentation = loadPresentation()
        player = SimpleNamespace(
            getItems=lambda: [], getEquipped=lambda: {}, getGold=lambda: 50, getNumericProperty=lambda name: 0
        )
        screens = []
        instance = SimpleNamespace(
            getMap=lambda: SimpleNamespace(getPlayer=lambda: player),
            getGui=lambda: None,
            getGuiHandler=lambda: SimpleNamespace(showCampaignScreen=lambda *args: screens.append(args)),
        )
        before = {"gold": 100, "experience": 0, "items": {"amulet": {"label": "Amulet", "count": 1}}}
        presentation["showRewardReceipt"](instance, "A receipt", before)
        self.assertEqual("No new rewards.", screens[0][1])

    def testRequirementsUseTheirResolvedTargetAndHeadlessFallback(self):
        presentation = loadPresentation()
        anchored, messages = [], []
        target = object()
        gui = SimpleNamespace(notifyAt=lambda *args: anchored.append(args))
        instance = SimpleNamespace(getGui=lambda: gui, getGuiHandler=lambda: SimpleNamespace(notify=messages.append))
        presentation["requirementMessage"](instance, target, "Requires 1 mage-wand.")
        self.assertEqual([(target, "Requires 1 mage-wand.")], anchored)
        self.assertFalse(messages)
        gui = None
        presentation["requirementMessage"](instance, target, "Requires 1 mage-wand.")
        self.assertEqual(["Requires 1 mage-wand."], messages)


class ArtifactPreviewTest(unittest.TestCase):
    def testReceiptReadsNativeInventoryEquipmentAndExperience(self):
        import test as harness
        from unittest.mock import patch

        try:
            game = harness.load_game_module()
        except (ImportError, ModuleNotFoundError) as error:
            self.skipTest(str(error))
        instance = game.CGameLoader.loadGame()
        self.addCleanup(instance.getContext().shutdown)
        game.CGameLoader.startGameWithPlayer(instance, "test", "Warrior")
        player = instance.getMap().getPlayer()
        before = game.rewardSnapshot(player)
        player.addGold(50)
        potion = instance.createObject("LifePotion")
        player.addItem(potion)
        player.addExp(750)
        screens = []
        with patch.object(game.CGuiHandler, "showCampaignScreen", lambda self, *args: screens.append(args)):
            game.showRewardReceipt(instance, "An observed reward", before)
        self.assertEqual(1, len(screens))
        self.assertEqual("Continue", screens[0][2])
        self.assertIn("Gold: +50", screens[0][1])
        self.assertIn("Experience: +750", screens[0][1])
        self.assertIn(potion.getStringProperty("label") + ": +1", screens[0][1])

    def testAssemblyPreviewUsesActualBonusesAbilitiesAndNamedSlots(self):
        import test as harness

        try:
            game = harness.load_game_module()
        except (ImportError, ModuleNotFoundError) as error:
            self.skipTest(str(error))
        import artifact_sets

        instance = game.CGameLoader.loadGame()
        self.addCleanup(instance.getContext().shutdown)
        runtime = artifact_sets.ArtifactSetRuntime()
        for item_id, required in (
            ("ArmorOfTheDamned", ("Armor +250", "Doom", "Right hand, Left hand, Head, Chest")),
            ("DragonFatherWrath", ("Armor +820", "Fireball", "Head, Chest, Feet, Legs")),
        ):
            definition = runtime.set_for_combined(item_id)
            preview = runtime.assemblyDetail(definition, game_instance=instance)
            self.assertIn("Resulting bonuses", preview)
            self.assertIn("Granted ability", preview)
            self.assertIn("Occupied slots", preview)
            actual = instance.createObject(item_id).getObjectProperty("interaction")
            self.assertIn(f"Mana cost: {actual.getNumericProperty('manaCost')}", preview)
            for expected in required:
                self.assertIn(expected, preview)
            for piece in definition["pieces"]:
                self.assertIn(runtime.itemPresentation(piece)[0], preview)
            disassembly = runtime.assemblyDetail(definition, disassembling=True, game_instance=instance)
            self.assertIn("Bonuses removed", disassembly)
            self.assertIn("Ability removed", disassembly)
            self.assertIn("Slots released", disassembly)


if __name__ == "__main__":
    unittest.main()
