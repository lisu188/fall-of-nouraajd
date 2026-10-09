# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""MCP equipment access preserves existing native slot and artifact rules."""

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import mcp

ROOT = Path(__file__).resolve().parents[1]


class McpEquipmentContractTest(unittest.TestCase):
    def equipmentServer(self):
        item = object()
        configuration = SimpleNamespace(canFit=Mock(return_value=True))
        game_map = SimpleNamespace(getGame=lambda: SimpleNamespace(getSlotConfiguration=lambda: configuration))

        class CCreature:
            def __init__(self):
                self.items = [item]
                self.equipped = {}
                self.calls = []

            def equipItem(self, slot, item):
                self.calls.append((slot, item))

            def getItems(self):
                return self.items

            def getEquipped(self):
                return self.equipped

            def getMap(self):
                return game_map

        creature = CCreature()
        server = mcp.EngineMcpServer(ROOT, ROOT / "unused-native-build")
        server.handles.update(player=creature, item=item)
        return server, creature, item, configuration

    def testEquipmentAccessUsesTheExistingCreatureSurface(self):
        self.assertTrue(
            {"equipItem", "getEquipped", "getItemAtSlot"}.issubset(mcp.MCP_ALLOWED_HANDLE_METHODS["CCreature"])
        )

    def testEquipmentDispatchResolvesOwnedItemHandlesAndAllowsUnequip(self):
        server, creature, item, configuration = self.equipmentServer()
        for value in ({"__handle__": "item"}, None):
            response = server._engine_handle_call({"handle": "player", "method": "equipItem", "args": ["3", value]})
            self.assertFalse(response["isError"], response)
        self.assertEqual([("3", item), ("3", None)], creature.calls)
        configuration.canFit.assert_called_once_with("3", item)

    def testIncompatibleSlotAndUnownedItemsAreRejectedBeforeNativeDispatch(self):
        server, creature, item, configuration = self.equipmentServer()
        configuration.canFit.return_value = False
        response = server._engine_handle_call(
            {"handle": "player", "method": "equipItem", "args": ["0", {"__handle__": "item"}]}
        )
        self.assertTrue(response["isError"], response)
        self.assertIn("does not fit slot 0", response["structuredContent"]["error"])
        self.assertEqual([], creature.calls)
        self.assertEqual([item], creature.items)
        configuration.canFit.reset_mock()
        configuration.canFit.return_value = True
        creature.items.clear()
        response = server._engine_handle_call(
            {"handle": "player", "method": "equipItem", "kwargs": {"slot": "3", "item": {"__handle__": "item"}}}
        )
        self.assertTrue(response["isError"], response)
        self.assertIn("not owned", response["structuredContent"]["error"])
        self.assertEqual([], creature.calls)
        configuration.canFit.assert_not_called()

    def testSameSlotReequipIsAllowedButOtherSlotsRequireUnequipFirst(self):
        server, creature, item, configuration = self.equipmentServer()
        creature.items.clear()
        creature.equipped["3"] = item
        configuration.canFit.return_value = False
        response = server._engine_handle_call(
            {"handle": "player", "method": "equipItem", "kwargs": {"slot": "3", "item": {"__handle__": "item"}}}
        )
        self.assertFalse(response["isError"], response)
        configuration.canFit.assert_not_called()
        configuration.canFit.return_value = True
        response = server._engine_handle_call(
            {"handle": "player", "method": "equipItem", "args": ["1"], "kwargs": {"item": {"__handle__": "item"}}}
        )
        self.assertTrue(response["isError"], response)
        self.assertIn("current slot first", response["structuredContent"]["error"])
        self.assertEqual([("3", item)], creature.calls)
        configuration.canFit.assert_not_called()
        response = server._engine_handle_call({"handle": "player", "method": "equipItem", "args": ["3", None]})
        self.assertFalse(response["isError"], response)
        creature.equipped.clear()
        creature.items.append(item)
        response = server._engine_handle_call(
            {"handle": "player", "method": "equipItem", "args": ["1"], "kwargs": {"item": {"__handle__": "item"}}}
        )
        self.assertFalse(response["isError"], response)
        self.assertEqual([("3", item), ("3", None), ("1", item)], creature.calls)
        configuration.canFit.assert_called_once_with("1", item)

    def testActualUnequipRequiresAMapButSameInstanceAndEmptySlotNoopsDoNot(self):
        server, creature, item, configuration = self.equipmentServer()
        creature.items.clear()
        creature.equipped["3"] = item
        creature.getMap = Mock(return_value=None)
        response = server._engine_handle_call({"handle": "player", "method": "equipItem", "args": ["3", None]})
        self.assertTrue(response["isError"], response)
        self.assertIn("no map", response["structuredContent"]["error"])
        self.assertEqual([], creature.calls)
        self.assertEqual({"3": item}, creature.equipped)
        creature.getMap.reset_mock()
        for slot, value in (("3", {"__handle__": "item"}), ("2", None)):
            response = server._engine_handle_call({"handle": "player", "method": "equipItem", "args": [slot, value]})
            self.assertFalse(response["isError"], response)
        creature.getMap.assert_not_called()
        configuration.canFit.assert_not_called()
        self.assertEqual([("3", item), ("2", None)], creature.calls)

    def testEquipmentArgumentBindingRejectsMalformedCallsBeforeDispatch(self):
        server, creature, _item, configuration = self.equipmentServer()
        invalid = (
            {},
            {"args": ["3"]},
            {"args": ["3", None, None]},
            {"args": ["3", None], "kwargs": {"slot": "3"}},
            {"args": ["3", None], "kwargs": {"item": None}},
            {"kwargs": {"slot": "3", "item": None, "extra": None}},
            {"kwargs": {"slot": 3, "item": None}},
        )
        for arguments in invalid:
            with self.subTest(arguments=arguments):
                response = server._engine_handle_call({"handle": "player", "method": "equipItem", **arguments})
                self.assertTrue(response["isError"], response)
        self.assertEqual([], creature.calls)
        configuration.canFit.assert_not_called()

    def testEquipmentValidationExceptionsBecomeStructuredErrorsWithoutDispatch(self):
        server, creature, item, configuration = self.equipmentServer()
        for failure in ("compatibility", "inventory", "map"):
            with self.subTest(failure=failure):
                creature.getItems = Mock(return_value=[item])
                creature.getMap = Mock(return_value=None)
                if failure == "compatibility":
                    creature.getMap.return_value = SimpleNamespace(
                        getGame=lambda: SimpleNamespace(getSlotConfiguration=lambda: configuration)
                    )
                    configuration.canFit.side_effect = RuntimeError("unavailable slot table")
                elif failure == "inventory":
                    creature.getItems.side_effect = RuntimeError("unavailable inventory")
                response = server._engine_handle_call(
                    {"handle": "player", "method": "equipItem", "args": ["3", {"__handle__": "item"}]}
                )
                self.assertTrue(response["isError"], response)
                self.assertEqual([], creature.calls)

    def testOwnershipRequiresTheExactInstanceRatherThanEquality(self):
        server, creature, _item, configuration = self.equipmentServer()

        class EqualItem:
            def __eq__(self, other):
                return True

        creature.items[:] = [EqualItem()]
        response = server._engine_handle_call(
            {"handle": "player", "method": "equipItem", "args": ["3", {"__handle__": "item"}]}
        )
        self.assertTrue(response["isError"], response)
        self.assertEqual([], creature.calls)
        configuration.canFit.assert_not_called()

    def testQuestEquipmentIsRejectedForEveryPlayerSubtypeBeforeNativeDispatch(self):
        server, creature, _item, configuration = self.equipmentServer()

        class CPlayer(type(creature)):
            pass

        class ScriptedPlayer(CPlayer):
            pass

        for player_type in (CPlayer, ScriptedPlayer):
            with self.subTest(player_type=player_type.__name__):
                player = player_type()
                item = SimpleNamespace(hasTag=Mock(return_value=True))
                player.items[:] = [item]
                server.handles.update(player=player, item=item)
                response = server._engine_handle_call(
                    {"handle": "player", "method": "equipItem", "args": ["3", {"__handle__": "item"}]}
                )
                self.assertTrue(response["isError"], response)
                self.assertIn("quest-tagged", response["structuredContent"]["error"])
                self.assertEqual([], player.calls)
                self.assertEqual([item], player.items)
                self.assertEqual({}, player.equipped)
                item.hasTag.assert_called_once_with("quest")
                configuration.canFit.assert_not_called()
                player.items.clear()
                player.equipped["3"] = item
                item.hasTag.reset_mock()
                response = server._engine_handle_call(
                    {"handle": "player", "method": "equipItem", "args": ["3", {"__handle__": "item"}]}
                )
                self.assertFalse(response["isError"], response)
                item.hasTag.assert_not_called()
                self.assertEqual([("3", item)], player.calls)

    def testQuestEquipmentOnNonPlayerCreaturesKeepsTheNativeRule(self):
        server, creature, _item, configuration = self.equipmentServer()
        item = SimpleNamespace(hasTag=Mock(return_value=True))
        creature.items[:] = [item]
        server.handles["item"] = item
        response = server._engine_handle_call(
            {"handle": "player", "method": "equipItem", "args": ["3", {"__handle__": "item"}]}
        )
        self.assertFalse(response["isError"], response)
        self.assertEqual([("3", item)], creature.calls)
        configuration.canFit.assert_called_once_with("3", item)
        item.hasTag.assert_not_called()


class McpEquipmentRuntimeTest(unittest.TestCase):
    def runChild(self, code):
        from tests.test_python_callback_lifecycle import PythonCallbackLifecycleTest

        return PythonCallbackLifecycleTest.runChild(self, code)

    def testMcpEquipmentRetainsOwnedItemsAndHonorsSlotsAndCurses(self):
        self.runChild("""
            import mcp
            from pathlib import Path
            instance = game.CGameLoader.loadGame()
            game.CGameLoader.startGameWithPlayer(instance, 'test', 'Warrior')
            player = instance.getMap().getPlayer()
            server = mcp.EngineMcpServer(Path.cwd(), Path.cwd())
            server.handles['player'] = player
            def call(method, *arguments):
                return server._engine_handle_call({'handle': 'player', 'method': method, 'args': list(arguments)})
            try:
                armor = instance.createObject('LeatherArmor')
                player.addItem(armor)
                server.handles['armor'] = armor
                assert armor in player.getItems()
                result = call('equipItem', '3', {'__handle__': 'armor'})
                assert not result['isError'], result
                assert player.getItemAtSlot('3') is armor
                assert armor not in player.getItems()
                equipped = call('getEquipped')['structuredContent']['result']
                assert equipped['3']['__handle__'] in server.handles, equipped
                selected = call('getItemAtSlot', '3')['structuredContent']['result']
                assert server.handles[selected['__handle__']] is armor, selected
                armor.addTag(game.CTag.CURSED)
                for value in ({'__handle__': 'armor'}, None):
                    result = call('equipItem', '3', value)
                    assert not result['isError'], result
                    assert player.getItemAtSlot('3') is armor
                    assert armor not in player.getItems()
                replacement = instance.createObject('LeatherArmor')
                player.addItem(replacement)
                server.handles['replacement'] = replacement
                assert not call('equipItem', '3', {'__handle__': 'replacement'})['isError']
                assert player.getItemAtSlot('3') is armor
                assert replacement in player.getItems()
                foreign = instance.createObject('LeatherArmor')
                server.handles['foreign'] = foreign
                result = call('equipItem', '3', {'__handle__': 'foreign'})
                assert result['isError'] and 'not owned' in result['structuredContent']['error'], result
                assert player.getItemAtSlot('3') is armor
                assert foreign not in player.getItems()
                assert replacement in player.getItems()
                result = call('equipItem', '0', {'__handle__': 'replacement'})
                assert result['isError'], result
                assert 'does not fit slot 0' in result['structuredContent']['error'], result
                assert player.getItemAtSlot('3') is armor
                assert replacement in player.getItems()
                armor.removeTag(game.CTag.CURSED)
                result = server._engine_handle_call({
                    'handle': 'player', 'method': 'equipItem', 'kwargs': {'slot': '3', 'item': None}
                })
                assert not result['isError'], result
                assert player.getItemAtSlot('3') is None
                assert armor in player.getItems()
                quest_armor = instance.createObject('LeatherArmor')
                player.addItem(quest_armor)
                quest_armor.addTag('quest')
                server.handles['questArmor'] = quest_armor
                result = call('equipItem', '3', {'__handle__': 'questArmor'})
                assert result['isError'] and 'quest-tagged' in result['structuredContent']['error'], result
                assert quest_armor in player.getItems()
                assert armor in player.getItems()
                assert player.getItemAtSlot('3') is None
            finally:
                instance.getContext().shutdown()
            """)

    def testMcpEquipmentHonorsCompoundCoveredSlots(self):
        self.runChild("""
            import mcp
            from pathlib import Path
            instance = game.CGameLoader.loadGame()
            game.CGameLoader.startGameWithPlayer(instance, 'test', 'Warrior')
            player = instance.getMap().getPlayer()
            server = mcp.EngineMcpServer(Path.cwd(), Path.cwd())
            server.handles['player'] = player
            def equip(slot, item):
                value = None
                if item is not None:
                    server.handles['item'] = item
                    value = {'__handle__': 'item'}
                result = server._engine_handle_call({'handle': 'player', 'method': 'equipItem', 'args': [slot, value]})
                assert not result['isError'], result
            try:
                for slot in list(player.getEquipped()):
                    equip(slot, None)
                combined = instance.createObject('ArmorOfTheDamned')
                helmet = instance.createObject('ThunderHelmet')
                player.addItem(combined)
                player.addItem(helmet)
                equip('2', helmet)
                equip('3', combined)
                assert player.getItemAtSlot('3') is None
                assert combined in player.getItems()
                equip('2', None)
                equip('3', combined)
                assert player.getItemAtSlot('3') is combined
                assert set(combined.getCoveredSlots()) == {'0', '1', '2'}
                equip('2', helmet)
                assert player.getItemAtSlot('2') is None
                assert helmet in player.getItems()
                equip('3', None)
                equip('2', helmet)
                assert player.getItemAtSlot('2') is helmet
                assert combined in player.getItems()
            finally:
                instance.getContext().shutdown()
            """)

    def testHeadlessTavernCallbackTracesItsActualMarketPricesAndStock(self):
        self.runChild("""
            import campaign
            import json
            for gate_action, expected_sell in (('open_door', 100), ('threatenGate', 105)):
                instance = game.CGameLoader.loadGame()
                try:
                    campaign.start(instance, 'fallOfNouraajd', 'Warrior', 'humanRace')
                    assert instance.getGui() is None
                    instance.createObject('doorDialog').invokeAction(gate_action)
                    loop.run()
                    game.configure_playtest_trace(True, max_records=8)
                    dialog = instance.createObject('tavernDialog1')
                    dialog.invokeAction('sell_beer')
                    loop.run()
                    events = [json.loads(line) for line in game.get_playtest_trace_records()]
                    trades = [event for event in events if event['event'] == 'trade_requested']
                    assert len(trades) == 1, events
                    trade = trades[0]
                    assert trade['map'] == 'nouraajd', trade
                    assert trade['market']['typeId'] == 'tavernBeerMarket', trade
                    assert trade['sell'] == expected_sell and trade['buy'] == 80, trade
                    assert sorted(item['typeId'] for item in trade['items']) == ['DarkBeer', 'DarkBeer', 'SpicedBeer'], trade
                    assert not any(event['event'] == 'gui_panel_opened' for event in events), events
                    game.configure_playtest_trace(False)
                    game.clear_playtest_trace()
                    instance.getGuiHandler().showTrade(instance.createObject('tavernBeerMarket'))
                    assert not game.get_playtest_trace_records()
                finally:
                    game.configure_playtest_trace(False)
                    instance.getContext().shutdown()
            """)

    def testHeadlessAuthoredSignpostAndCraftingEntriesTraceTheirActualRequests(self):
        self.runChild("""
            import json
            instance = game.CGameLoader.loadGame()
            try:
                game.CGameLoader.startGameWithPlayer(instance, 'nouraajd', 'Warrior')
                world = instance.getMap()
                player = world.getPlayer()
                assert instance.getGui() is None
                game.configure_playtest_trace(True, max_records=64)
                sign = world.getObjectByName('nouraajdSign')
                def enter(actor):
                    point = actor.getCoords()
                    player.moveTo(point.x, point.y, point.z)
                    for _ in range(3):
                        loop.run()
                enter(sign)
                enter(world.getObjectByName('market1'))
                enter(sign)
                events = [json.loads(line) for line in game.get_playtest_trace_records()]
                readers = [event for event in events if event['event'] == 'reader_requested']
                assert len(readers) == 2, events
                for event in readers:
                    assert event['headless'] is True and event['map'] == 'nouraajd', event
                    assert event['title'] == 'Signpost' and event['body'] == sign.getStringProperty('text'), event
                    assert event['bodyLength'] == len(event['body'].encode('utf-8')), event
                    assert event['player']['isPlayer'] is True and event['player']['name'] == player.getName(), event
                    assert event['playerCoords'] == {'x': 106, 'y': 110, 'z': 0}, event
                for name, expected_recipe in (('alchemyTable1', 'brew_life_potion'),
                                               ('scribeDesk1', 'craft_town_portal_scroll')):
                    game.clear_playtest_trace()
                    station = world.getObjectByName(name)
                    enter(station)
                    events = [json.loads(line) for line in game.get_playtest_trace_records()]
                    choices = [event for event in events if event['event'] == 'choice_requested']
                    assert len(choices) == 1, events
                    event = choices[0]
                    assert event['headless'] is True and event['map'] == 'nouraajd', event
                    assert event['title'] == station.getStringProperty('label'), event
                    assert event['actionLabel'] == 'Craft' and event['backLabel'] == 'Leave station', event
                    assert event['choicesJsonLength'] == len(event['choicesJson'].encode('utf-8')), event
                    point = station.getCoords()
                    assert event['playerCoords'] == {'x': point.x, 'y': point.y, 'z': point.z}, event
                    payload = json.loads(event['choicesJson'])
                    recipe = next(choice for choice in payload if choice['id'] == expected_recipe)
                    assert recipe['enabled'] is False, recipe
                    assert ('Missing:' if name == 'alchemyTable1' else 'Locked') in recipe['detail'], recipe
                    assert not any(record['event'] == 'gui_panel_opened' for record in events), events
                game.configure_playtest_trace(False)
                game.clear_playtest_trace()
                enter(sign)
                enter(world.getObjectByName('scribeDesk1'))
                assert not game.get_playtest_trace_records()
            finally:
                game.configure_playtest_trace(False)
                instance.getContext().shutdown()
            """)

    def testHeadlessPresentationTraceBoundsUtf8PayloadWithoutChangingChoiceResult(self):
        self.runChild("""
            import json
            instance = game.CGameLoader.loadGame()
            try:
                game.CGameLoader.startGameWithPlayer(instance, 'test', 'Warrior')
                handler = instance.getGuiHandler()
                assert instance.getGui() is None
                game.configure_playtest_trace(True, max_records=8)
                title, body, label = '\u0105' * 200, '\u017c' * 10000, '\u0142' * 100
                handler.showCampaignScreen(title, body, label)
                assert handler.showChoice(title, body, label, label) == ''
                events = [json.loads(line) for line in game.get_playtest_trace_records()]
                assert [event['event'] for event in events] == ['reader_requested', 'choice_requested'], events
                reader, choice = events
                assert reader['bodyLength'] == len(body.encode('utf-8')), reader
                assert len(reader['body'].encode('utf-8')) == 4096, reader
                assert choice['choicesJsonLength'] == len(body.encode('utf-8')), choice
                assert len(choice['choicesJson'].encode('utf-8')) == 16384, choice
                for event in events:
                    assert event['titleLength'] == len(title.encode('utf-8')), event
                    assert len(event['title'].encode('utf-8')) == 256, event
                    assert len(event['actionLabel'].encode('utf-8')) == 128, event
                    assert event['headless'] is True, event
                assert len(choice['backLabel'].encode('utf-8')) == 128, choice
            finally:
                game.configure_playtest_trace(False)
                instance.getContext().shutdown()
            """)


if __name__ == "__main__":
    unittest.main()
