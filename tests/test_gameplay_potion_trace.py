# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Native potion trace contracts; these fixtures receive no played-route credit."""

import unittest


class GameplayPotionTraceRuntimeTest(unittest.TestCase):
    def runChild(self, code):
        from tests.test_python_callback_lifecycle import PythonCallbackLifecycleTest

        return PythonCallbackLifecycleTest.runChild(self, code)

    def testAcceptedPotionUseRecordsExactNativeRestorationAndSelectedIdentity(self):
        self.runChild("""
            import json
            instance = game.CGameLoader.loadGame()
            try:
                game.CGameLoader.startGameWithPlayer(instance, 'test', 'Warrior')
                world, player = instance.getMap(), instance.getMap().getPlayer()
                for category, type_id in (('life', 'LifePotion'), ('mana', 'ManaPotion')):
                    used, spare = instance.createObject(type_id), instance.createObject(type_id)
                    used.setStringProperty('name', 'trace-used-' + category)
                    spare.setStringProperty('name', 'trace-spare-' + category)
                    player.addItem(used)
                    player.addItem(spare)
                    player.setNumericProperty('hp', player.getHpMax() - 17)
                    player.setNumericProperty('mana', player.getManaMax() - 19)
                    before = set(player.getItems())
                    hp, mana = player.getHp(), player.getMana()
                    maximum_hp, maximum_mana = player.getHpMax(), player.getManaMax()
                    equipped = player.getEquipped()
                    game.configure_playtest_trace(True)
                    game.clear_playtest_trace()
                    player.useItem(used)
                    events = [json.loads(line) for line in game.get_playtest_trace_records()]
                    uses = [event for event in events if event['event'] == 'item_used']
                    assert len(uses) == 1, events
                    event = uses[0]
                    assert event['actor']['name'] == player.getName() and event['actor']['isPlayer'] is True, event
                    assert event['item']['name'] == used.getName() and event['item']['typeId'] == type_id, event
                    assert event['itemNameLength'] == len(used.getName().encode('utf-8')), event
                    assert event['map'] == 'test' and event['turn'] == world.getTurn(), event
                    assert event['power'] == used.getNumericProperty('power'), event
                    assert event['restoresHp'] is (category == 'life'), event
                    assert event['restoresMana'] is (category == 'mana'), event
                    assert event['hpBefore'] == hp and event['manaBefore'] == mana, event
                    assert event['hpMaxBefore'] == event['hpMaxAfter'] == maximum_hp, event
                    assert event['manaMaxBefore'] == event['manaMaxAfter'] == maximum_mana, event
                    expected_hp = min(maximum_hp, hp + max(1, int(maximum_hp * event['power'] * 20 / 100))) if category == 'life' else hp
                    expected_mana = min(maximum_mana, mana + max(1, int(maximum_mana * event['power'] * 20 / 100))) if category == 'mana' else mana
                    assert event['hpAfter'] == player.getHp() == expected_hp, event
                    assert event['manaAfter'] == player.getMana() == expected_mana, event
                    assert event['ownedBefore'] is True and event['ownedAfter'] is False, event
                    assert event['disposable'] is True and event['onlyUsedItemRemoved'] is True, event
                    assert event['removedCount'] == 1 and event['addedCount'] == 0, event
                    assert event['inventoryBeforeCount'] == len(before), event
                    assert event['inventoryAfterCount'] == len(before) - 1, event
                    assert set(player.getItems()) == before - {used} and spare in player.getItems()
                    assert event['equipmentUnchanged'] is True and player.getEquipped() == equipped, event
                    game.configure_playtest_trace(False)
                game.clear_playtest_trace()
                potion = instance.createObject('LifePotion')
                player.addItem(potion)
                player.setNumericProperty('hp', player.getHpMax() - 10)
                player.useItem(potion)
                assert game.get_playtest_trace_records() == []
            finally:
                game.configure_playtest_trace(False)
                instance.getContext().shutdown()
            """)

    def testFullResourcesRefuseConsumptionAndProduceNoAcceptedUseEvent(self):
        self.runChild("""
            import json
            instance = game.CGameLoader.loadGame()
            try:
                game.CGameLoader.startGameWithPlayer(instance, 'test', 'Warrior')
                player = instance.getMap().getPlayer()
                for type_id in ('LifePotion', 'ManaPotion'):
                    potion = instance.createObject(type_id)
                    player.addItem(potion)
                    player.setNumericProperty('hp', player.getHpMax())
                    player.setNumericProperty('mana', player.getManaMax())
                    owned = set(player.getItems())
                    game.configure_playtest_trace(True)
                    game.clear_playtest_trace()
                    player.useItem(potion)
                    assert set(player.getItems()) == owned
                    assert not any(json.loads(line)['event'] == 'item_used' for line in game.get_playtest_trace_records())
                    game.configure_playtest_trace(False)
            finally:
                game.configure_playtest_trace(False)
                instance.getContext().shutdown()
            """)
