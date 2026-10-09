# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Expose the actual opt-in headless callback market without refreshing its finite stock."""

from pathlib import Path
from types import SimpleNamespace
import unittest
import weakref

import mcp

ROOT = Path(__file__).resolve().parents[1]

CALLBACK_PROGRAM = """
import campaign
import json
import mcp
from pathlib import Path

instance = game.CGameLoader.loadGame()
try:
    campaign.start(instance, 'fallOfNouraajd', 'Warrior', 'humanRace')
    handler = instance.getGuiHandler()
    player = instance.getMap().getPlayer()
    assert instance.getGui() is None
    game.configure_playtest_trace(False)
    assert handler.getRequestedTradeMarket() is None
    dialog = instance.createObject('tavernDialog1')
    dialog.invokeAction('sell_beer')
    loop.run()
    assert handler.getRequestedTradeMarket() is None

    game.configure_playtest_trace(True, max_records=32)
    dialog.invokeAction('sell_beer')
    loop.run()
    market = handler.getRequestedTradeMarket()
    assert market is not None and market is handler.getRequestedTradeMarket()
    assert market.getTypeId() == 'tavernBeerMarket'
    requests = [json.loads(line) for line in game.get_playtest_trace_records()
                if json.loads(line).get('event') == 'trade_requested']
    assert len(requests) == 1 and requests[0]['market']['name'] == market.getName(), requests
    stock = market.getItems()
    assert sorted(item.getTypeId() for item in stock) == ['DarkBeer', 'DarkBeer', 'SpicedBeer']
    server = mcp.EngineMcpServer(Path.cwd(), Path.cwd())
    server.handles.update(handler=handler, player=player)
    def call(handle, method, *args):
        result = server._engine_handle_call({'handle': handle, 'method': method, 'args': list(args)})
        assert not result['isError'], result
        return result['structuredContent']['result']
    exposed = call('handler', 'getRequestedTradeMarket')
    assert server.handles[exposed['__handle__']] is market
    assert call('handler', 'getRequestedTradeMarket')['__handle__'] == exposed['__handle__']
    items = call(exposed['__handle__'], 'getItems')
    item = server.handles[items[0]['__handle__']]
    price = market.getSellCost(item)
    # Contract-only funding isolates market identity/depletion; this is not a gameplay receipt.
    player.addGold(price)
    gold_before = player.getGold()
    assert call(exposed['__handle__'], 'sellItem', {'__handle__': 'player'}, items[0]) is True
    assert player.getGold() == gold_before - price and item in player.getItems()
    assert market is handler.getRequestedTradeMarket() and item not in market.getItems()
    assert len(call(call('handler', 'getRequestedTradeMarket')['__handle__'], 'getItems')) == 2
    assert call(exposed['__handle__'], 'sellItem', {'__handle__': 'player'}, items[0]) is False
    assert player.getGold() == gold_before - price

    # A new authored callback is a real new request, not a getter-created replacement.
    dialog.invokeAction('sell_beer')
    loop.run()
    newer = handler.getRequestedTradeMarket()
    assert newer is not market and len(newer.getItems()) == 3 and len(market.getItems()) == 2
    game.configure_playtest_trace(False)
    assert handler.getRequestedTradeMarket() is None
    game.configure_playtest_trace(True, max_records=32)
    assert handler.getRequestedTradeMarket() is None
    dialog.invokeAction('sell_beer')
    loop.run()
    assert handler.getRequestedTradeMarket() is not None
    handler.showTrade(None)
    assert handler.getRequestedTradeMarket() is None
finally:
    game.configure_playtest_trace(False)
    instance.getContext().shutdown()
"""

LIFETIME_PROGRAM = """
from pathlib import Path
import uuid

instance = game.CGameLoader.loadGame()
save_path = None
try:
    game.CGameLoader.startGameWithPlayer(instance, 'test', 'Warrior')
    handler = instance.getGuiHandler()
    game.configure_playtest_trace(True, max_records=32)
    first_map = instance.getMap()
    market = instance.createObject('CMarket')
    handler.showTrade(market)
    assert handler.getRequestedTradeMarket() is market
    slot = 'mcp-trade-contract-' + uuid.uuid4().hex
    assert game.CMapLoader.saveWithResult(first_map, slot)
    save_path = Path(instance.getResourcesProvider().getPath('save/' + slot + '.json'))
    assert save_path.is_file()
    game.CGameLoader.loadSavedGame(instance, slot)
    assert instance.getMap() is not first_map and handler.getRequestedTradeMarket() is None

    original = instance.getMap()
    handler.showTrade(market)
    assert handler.getRequestedTradeMarket() is market
    away = game.CMapTransitionRequest()
    away.targetMap = 'test'
    away.retainSourceMap = True
    assert instance.requestMapTransition(away)
    loop.run()
    assert instance.getMap() is not original
    back = game.CMapTransitionRequest()
    back.targetMap = 'test'
    back.reuseLoadedMap = True
    assert instance.requestMapTransition(back)
    loop.run()
    assert instance.getMap() is original
    # No getter ran while away: generation must invalidate the retained same-map instance.
    assert handler.getRequestedTradeMarket() is None
    handler.showTrade(market)
    assert handler.getRequestedTradeMarket() is market
    instance.getContext().shutdown()
    assert handler.getRequestedTradeMarket() is None
finally:
    game.configure_playtest_trace(False)
    instance.getContext().shutdown()
    if save_path is not None:
        save_path.unlink(missing_ok=True)
        save_path.with_name(save_path.name + '.bak').unlink(missing_ok=True)
"""

GUI_PROGRAM = """
import gc

instance = game.CGameLoader.loadGame()
try:
    game.configure_playtest_trace(True, max_records=16)
    handler = instance.getGuiHandler()
    market = instance.createObject('CMarket')
    assert handler.getRequestedTradeMarket() is None
    handler.showTrade(market)
    assert handler.getRequestedTradeMarket() is None, 'No active map may retain a request'
    orphan_owner = game.CGameLoader.loadGame()
    orphan = orphan_owner.getGuiHandler()
    orphan_owner.getContext().shutdown()
    del orphan_owner
    gc.collect()
    orphan.showTrade(market)
    assert orphan.getRequestedTradeMarket() is None
    game.CGameLoader.startGameWithPlayer(instance, 'test', 'Warrior')
    handler.showTrade(market)
    assert handler.getRequestedTradeMarket() is market
    game.CGameLoader.loadGui(instance)
    assert instance.getGui() is not None
    assert handler.getRequestedTradeMarket() is None, 'GUI sessions do not expose diagnostic markets'
    handler.showTrade(None)
    assert handler.getRequestedTradeMarket() is None
finally:
    game.configure_playtest_trace(False)
    instance.getContext().shutdown()
"""


class McpTradeMarketContractTest(unittest.TestCase):
    def testOnlyTheReadOnlyGetterIsAddedToTheExistingHandlerSurface(self):
        self.assertIn("getRequestedTradeMarket", mcp.MCP_ALLOWED_HANDLE_METHODS["CGuiHandler"])
        self.assertNotIn("setRequestedTradeMarket", mcp.MCP_ALLOWED_HANDLE_METHODS["CGuiHandler"])
        self.assertNotIn("getRequestedTradeMarket", mcp.MCP_ALLOWED_EXPORTS)

    def testGetterSerializesTheSameActualInstanceAndDepletedStockThroughExistingHandles(self):
        class CMarket:
            def __init__(self):
                self.items = [object(), object()]

            def getItems(self):
                return self.items

        actual = CMarket()

        class CGuiHandler:
            def getRequestedTradeMarket(self):
                return actual

        server = mcp.EngineMcpServer(ROOT, ROOT / "unused-native-build")
        server.handles["handler"] = CGuiHandler()

        def call(handle, method):
            result = server._engine_handle_call({"handle": handle, "method": method})
            self.assertFalse(result["isError"], result)
            return result["structuredContent"]["result"]

        first = call("handler", "getRequestedTradeMarket")
        second = call("handler", "getRequestedTradeMarket")
        self.assertEqual(first["__handle__"], second["__handle__"])
        self.assertIs(actual, server.handles[first["__handle__"]])
        items = call(first["__handle__"], "getItems")
        actual.items.pop(0)
        after = call(call("handler", "getRequestedTradeMarket")["__handle__"], "getItems")
        self.assertEqual(items[1]["__handle__"], after[0]["__handle__"])
        self.assertEqual(1, len(after))

    def testAbsentRequestIsNullAndDoesNotCreateAMarketHandle(self):
        class CGuiHandler:
            def getRequestedTradeMarket(self):
                return None

        server = mcp.EngineMcpServer(ROOT, ROOT / "unused-native-build")
        server.handles["handler"] = CGuiHandler()
        before = dict(server.handles)
        result = server._engine_handle_call({"handle": "handler", "method": "getRequestedTradeMarket"})
        self.assertFalse(result["isError"], result)
        self.assertIsNone(result["structuredContent"]["result"])
        self.assertEqual(before, server.handles)

    def testNativeContractProgramsHaveValidSyntaxWithoutExecutingNativeCode(self):
        for program in (CALLBACK_PROGRAM, LIFETIME_PROGRAM, GUI_PROGRAM):
            compile(program, "<native trade market contract>", "exec")

    def testMissingOwnerFixtureUsesARealContextHandlerAfterOwnerRelease(self):
        owners = []
        requests_without_owner = []
        created_types = []
        trace_enabled = False

        class Handler:
            def __init__(self, owner):
                self.owner = weakref.ref(owner)
                self.market = None

            def showTrade(self, market):
                owner = self.owner()
                self.market = None
                if owner is None:
                    requests_without_owner.append(market)
                elif market is not None and owner.world is not None and owner.gui is None and trace_enabled:
                    self.market = market

            def getRequestedTradeMarket(self):
                owner = self.owner()
                if owner is None or owner.world is None or owner.gui is not None or not trace_enabled:
                    self.market = None
                return self.market

        class Instance:
            def __init__(self):
                self.world = None
                self.gui = None
                self.handler = Handler(self)
                self.active = True

            def createObject(self, type_id):
                created_types.append(type_id)
                return object() if type_id == "CMarket" else None

            def getGuiHandler(self):
                return self.handler

            def getGui(self):
                return self.gui

            def getContext(self):
                return self

            def shutdown(self):
                self.active = False
                self.world = None
                self.handler = None

        def loadGame():
            instance = Instance()
            owners.append(weakref.ref(instance))
            return instance

        def startGameWithPlayer(instance, map_name, class_id):
            self.assertEqual(("test", "Warrior"), (map_name, class_id))
            self.assertTrue(instance.active)
            instance.world = object()

        def configureTrace(enabled, **kwargs):
            nonlocal trace_enabled
            trace_enabled = enabled

        game = SimpleNamespace(
            CGameLoader=SimpleNamespace(
                loadGame=loadGame,
                startGameWithPlayer=startGameWithPlayer,
                loadGui=lambda instance: setattr(instance, "gui", object()),
            ),
            configure_playtest_trace=configureTrace,
        )
        exec(compile(GUI_PROGRAM, "<actual trade market owner fixture>", "exec"), {"game": game})
        self.assertEqual(["CMarket"], created_types)
        self.assertEqual(2, len(owners))
        self.assertTrue(all(owner() is None for owner in owners))
        self.assertEqual(1, len(requests_without_owner))
        self.assertFalse(trace_enabled)


class McpTradeMarketRuntimeTest(unittest.TestCase):
    def runChild(self, program):
        from tests.test_python_callback_lifecycle import PythonCallbackLifecycleTest

        return PythonCallbackLifecycleTest.runChild(self, program, timeout_seconds=90)

    def testActualHeadlessTavernCallbackExposesOneFiniteMarketThroughMcp(self):
        self.runChild(CALLBACK_PROGRAM)

    def testMapReloadPersistentRoundTripAndShutdownInvalidateTheRequest(self):
        self.runChild(LIFETIME_PROGRAM)

    def testMissingMapOrGameAndAnOffscreenGuiNeverExposeTheRequest(self):
        self.runChild(GUI_PROGRAM)


if __name__ == "__main__":
    unittest.main()
