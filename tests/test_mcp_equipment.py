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


if __name__ == "__main__":
    unittest.main()
