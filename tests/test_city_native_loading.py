# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real staged city construction/fallback regression; no model or original-parity credit."""

import ast
import textwrap
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.test_python_callback_lifecycle import PythonCallbackLifecycleTest


class CityNativeLoadingRuntimeTest(unittest.TestCase):
    runChild = PythonCallbackLifecycleTest.runChild

    def testCityLoadsNativePlacedAndDeferredActorsWithBlockedLayerFallback(self):
        output = self.runChild("""
            import time
            from collections import Counter
            import json
            def decodeCityData(encoded):
                return json.loads(encoded.removeprefix('city-json:'))
            started = time.perf_counter()
            instance = game.CGameLoader.loadGame()
            try:
                game.CGameLoader.startGameWithPlayer(instance, 'baldursGate', 'Warrior')
                loop.run()
                world = instance.getMap()
                assert world.getStringProperty('mapName') == 'baldursGate'
                assert world.getPlayer() is not None
                assert sum(isinstance(actor, game.CPlayer) for actor in world.getObjects()) == 1
                marek = world.getObjectByName('cityAr0300Actor29')
                assert isinstance(marek, game.CCreature)
                assert marek.getType() == 'CCreature', marek.getType()
                assert marek.getTypeId() == 'cityAr0300Actor29'
                assert marek.getStringProperty('sourceCreature') == 'MAREK'
                assert marek.getStringProperty('sourceArea') == 'AR0300'
                assert marek.getStringProperty('sourceInventory')
                inventory = decodeCityData(marek.getStringProperty('sourceInventory'))
                assert inventory and isinstance(inventory, list)
                assert len(decodeCityData(marek.getStringProperty('sourceItemSlots'))) == 40
                assert marek.getBoolProperty('plugin_cityInventoryInitialized')
                owned = {id(item): item for item in (*marek.getItems(), *marek.getEquipped().values()) if item}
                assert Counter(item.getStringProperty('plugin_citySourceItem') for item in owned.values()) == Counter(
                    row['item'] for row in inventory if row['item'] != 'MISC07'
                )
                clock = world.getObjectByName('cityClock')
                assert decodeCityData(clock.getStringProperty('questDefinitions'))['quests']
                assert 'AR0800' in decodeCityData(clock.getStringProperty('areaAtlas'))
                assert decodeCityData(clock.getStringProperty('actorDefinitions'))
                assert isinstance(decodeCityData(clock.getStringProperty('regionDefinitions')), dict)
                assert world.getStringProperty('plugin_cityStartingProfile').startswith('city-json:')
                clone = marek.clone()
                assert clone.getStringProperty('sourceInventory') == marek.getStringProperty('sourceInventory')
                assert clone.getStringProperty('sourceItemSlots') == marek.getStringProperty('sourceItemSlots')
                assert clone.getBoolProperty('plugin_cityInventoryInitialized')
                for suffix in ('Noblpa', 'Noblpa1', 'Noblpa2', 'Noblpa3', 'Noblpa4', 'Noblpa5'):
                    name = 'cityAr0108ScriptActor' + suffix
                    actor = instance.createObject(name)
                    assert isinstance(actor, game.CCreature)
                    assert actor.getType() == 'CCreature', actor.getType()
                    assert actor.getTypeId() == name
                    assert actor.getStringProperty('sourceCreature') == suffix.upper()
                    assert actor.getStringProperty('sourceArea') == 'AR0108'
                    assert isinstance(actor.getFightController(), game.CFightController)
                    assert actor.getFightController().getType() == 'CMonsterFightController'
                for level in range(5):
                    for x, y in ((223, 191), (-1, 0), (224, 192)):
                        tile = world.getTile(x, y, level)
                        point = tuple(tile.getNumericProperty(key) for key in ('posx', 'posy', 'posz'))
                        assert point == (x, y, level), point
                        assert tile.getTypeId() == 'cityWallTile', tile.getTypeId()
                        assert not world.canStep(game.Coords(x, y, level)), (x, y, level)
                print(
                    'native city construction and five-level blocked fallback verified',
                    time.perf_counter() - started,
                    flush=True,
                )
            finally:
                instance.getContext().shutdown()
            """)
        self.assertIn("native city construction and five-level blocked fallback verified", output)

    def testCityStructuredMetadataAndOwnedItemsSurviveSaveReload(self):
        output = self.runChild("""
            import os
            from pathlib import Path
            import time
            import json
            def decodeCityData(encoded):
                return json.loads(encoded.removeprefix('city-json:'))
            os.environ['GAME_SAVE_STAGE_DIAGNOSTICS'] = '1'
            slot = 'city-metadata-' + str(os.getpid()) + '-' + str(time.time_ns())
            started = time.monotonic()
            def phase(name):
                print(
                    'city-metadata-phase', name,
                    'elapsedSeconds=' + format(time.monotonic() - started, '.3f'),
                    flush=True,
                )
            phase('loadGame')
            instance = game.CGameLoader.loadGame()
            phase('gameLoaded')
            restored = None
            completed = False
            try:
                phase('startMap')
                game.CGameLoader.startGameWithPlayer(instance, 'baldursGate', 'Warrior')
                loop.run()
                phase('mapReady')
                world = instance.getMap()
                marek = world.getObjectByName('cityAr0300Actor29')
                clock = world.getObjectByName('cityClock')
                def snapshot(actor):
                    owned = {id(item): item for item in (*actor.getItems(), *actor.getEquipped().values()) if item}
                    return sorted(
                        (item.getStringProperty('plugin_citySourceItem'), item.getNumericProperty('plugin_cityQuantity'))
                        for item in owned.values()
                    )
                before = snapshot(marek)
                assert before and marek.getBoolProperty('plugin_cityInventoryInitialized')
                inventory = marek.getStringProperty('sourceInventory')
                definitions = clock.getStringProperty('questDefinitions')
                profile = world.getStringProperty('plugin_cityStartingProfile')
                assert all(value.startswith('city-json:') for value in (inventory, definitions, profile))
                phase('save')
                assert game.CMapLoader.saveWithResult(world, slot)
                phase('saved')
                phase('restoreGame')
                restored = game.CGameLoader.loadGame()
                phase('loadSavedGame')
                game.CGameLoader.loadSavedGame(restored, slot)
                loop.run()
                phase('savedMapLoaded')
                saved_world = restored.getMap()
                assert saved_world.getStringProperty('mapName') == 'baldursGate'
                saved_actor = saved_world.getObjectByName('cityAr0300Actor29')
                saved_clock = saved_world.getObjectByName('cityClock')
                assert saved_actor.getStringProperty('sourceInventory') == inventory
                assert saved_clock.getStringProperty('questDefinitions') == definitions
                assert saved_world.getStringProperty('plugin_cityStartingProfile') == profile
                assert decodeCityData(saved_actor.getStringProperty('sourceInventory'))
                assert decodeCityData(saved_clock.getStringProperty('questDefinitions'))['quests']
                assert saved_actor.getBoolProperty('plugin_cityInventoryInitialized')
                assert snapshot(saved_actor) == before
                phase('verified')
                completed = True
                print('native city metadata and item ownership survived save reload', flush=True)
            finally:
                if restored is not None:
                    phase('restoredShutdown')
                    restored.getContext().shutdown()
                phase('primaryShutdown')
                instance.getContext().shutdown()
                if completed:
                    for suffix in ('.json', '.json.bak'):
                        (Path('save') / (slot + suffix)).unlink(missing_ok=True)
                phase('finished')
            """)
        self.assertIn("native city metadata and item ownership survived save reload", output)

    def testNativeSaveDiagnosticsAreSilentByDefaultAndPreserveTheSavedDocument(self):
        import json

        output, errors = self.runChild(
            """
            import json
            import os
            from pathlib import Path
            import time
            os.environ.pop('GAME_SAVE_STAGE_DIAGNOSTICS', None)
            prefix = 'save-stage-' + str(os.getpid()) + '-' + str(time.time_ns())
            slots = (prefix + '-disabled', prefix + '-enabled')
            instance = game.CGameLoader.loadGame()
            completed = False
            try:
                game.CGameLoader.startGameWithPlayer(instance, 'multilevel', 'Warrior')
                loop.run()
                world = instance.getMap()
                assert game.CMapLoader.saveWithResult(world, slots[0])
                os.environ['GAME_SAVE_STAGE_DIAGNOSTICS'] = '1'
                assert game.CMapLoader.saveWithResult(world, slots[1])
                documents = [json.loads((Path('save') / (slot + '.json')).read_text(encoding='utf-8')) for slot in slots]
                assert documents[0] == documents[1], 'Diagnostics must preserve the actual saved document'
                completed = True
                print('native save diagnostics preserve default silence and saved document', flush=True)
            finally:
                instance.getContext().shutdown()
                if completed:
                    for slot in slots:
                        for suffix in ('.json', '.json.bak'):
                            (Path('save') / (slot + suffix)).unlink(missing_ok=True)
            """,
            return_stderr=True,
        )
        self.assertIn("native save diagnostics preserve default silence and saved document", output)
        records = [json.loads(line) for line in errors.splitlines() if line.startswith('{"diagnostic":"save-stage"')]
        stages = [row["stage"] for row in records]
        self.assertEqual(
            [
                "journal.begin",
                "journal.end",
                "graph.begin",
                "graph.end",
                "envelope.begin",
                "envelope.end",
                "json.begin",
                "json.end",
                "write.begin",
                "write.end",
            ],
            stages,
            errors,
        )
        elapsed = [row["elapsedMicroseconds"] for row in records]
        self.assertTrue(all(type(value) is int and value >= 0 for value in elapsed), records)
        self.assertEqual(sorted(elapsed), elapsed)
        self.assertTrue(all(row["success"] is True for row in records), records)
        graph = records[stages.index("graph.end")]
        self.assertGreater(graph["objects"], 0)
        self.assertGreater(graph["tiles"], 0)
        self.assertTrue(
            all((row["objects"], row["tiles"]) == (graph["objects"], graph["tiles"]) for row in records[3:])
        )
        encoded = records[stages.index("json.end")]["bytes"]
        self.assertGreater(encoded, 0)
        self.assertEqual([encoded, encoded], [row["bytes"] for row in records[-2:]])
        self.assertLessEqual(len(records), 10, "The default-disabled first save must emit no diagnostic records")
        self.assertTrue(
            all(
                set(row) == {"diagnostic", "stage", "elapsedMicroseconds", "objects", "tiles", "bytes", "success"}
                for row in records
            )
        )


class CityNativeLoadingSourceTest(unittest.TestCase):
    def program(self, method_name, marker):
        case = CityNativeLoadingRuntimeTest(method_name)
        programs = []
        with patch.object(
            case, "runChild", side_effect=lambda program, **kwargs: programs.append((program, kwargs)) or marker
        ):
            getattr(case, method_name)()
        self.assertEqual(1, len(programs))
        program, kwargs = programs[0]
        ast.parse(textwrap.dedent(program))
        self.assertEqual({}, kwargs, "Keep the shared bounded child timeout")
        return program

    def testChildCanReturnDiagnosticStderrWithoutChangingItsDefaultResultOrDeadline(self):
        import subprocess

        case = CityNativeLoadingRuntimeTest("testCityStructuredMetadataAndOwnedItemsSurviveSaveReload")
        completed = subprocess.CompletedProcess(["python", "-c", "pass"], 0, "child stdout", "child diagnostics")
        with patch("tests.test_python_callback_lifecycle.subprocess.run", return_value=completed) as run:
            self.assertEqual("child stdout", case.runChild("pass"))
            self.assertEqual(("child stdout", "child diagnostics"), case.runChild("pass", return_stderr=True))
        self.assertEqual([30, 30], [call.kwargs["timeout"] for call in run.call_args_list])
        self.assertTrue(all(call.kwargs["capture_output"] for call in run.call_args_list))

    def testSaveDiagnosticsAreOptInAndBracketExistingSaveStagesWithoutExtraGraphWork(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1] / "src/core/CLoader.cpp").read_text(encoding="utf-8")
        self.assertIn("class SaveStageDiagnostics", source)
        helper = source.split("class SaveStageDiagnostics", 1)[1].split("build_save_envelope", 1)[0]
        self.assertIn('std::getenv("GAME_SAVE_STAGE_DIAGNOSTICS")', helper)
        self.assertIn("if (!enabled)", helper)
        self.assertIn("noexcept", helper)
        self.assertIn("std::fprintf(stderr", helper)
        self.assertIn("std::fflush(stderr)", helper)
        for forbidden in ("getTiles(", "getObjects(", "serializeExpected(", "to_string(", "map->", "slot"):
            self.assertNotIn(forbidden, helper)
        build = source.split("build_save_envelope(", 1)[1].split("void apply_authored_map_metadata", 1)[0]
        self.assertEqual(1, build.count("CSerialization::serializeExpected("))
        for before, operation, after in (
            ('mark("journal.begin")', "player->captureQuestJournal()", 'mark("journal.end")'),
            ('mark("graph.begin")', "CSerialization::serializeExpected(", "diagnostics.graphFinished(*snapshot)"),
            ('mark("envelope.begin")', "CSaveFormat::buildEnvelope(", 'mark("envelope.end"'),
        ):
            self.assertLess(build.index(before), build.index(operation))
            self.assertLess(build.index(operation), build.index(after))
        save = source.split("bool CMapLoader::saveWithResult(", 1)[1].split("void CMapLoader::handleTileLayer", 1)[0]
        self.assertEqual(1, save.count("CJsonUtil::to_string("))
        self.assertEqual(1, save.count("resources->save("))
        self.assertLess(save.index('mark("json.begin")'), save.index("CJsonUtil::to_string("))
        self.assertLess(save.index("CJsonUtil::to_string("), save.index('mark("json.end"'))
        self.assertLess(save.index('mark("write.begin"'), save.index("resources->save("))
        self.assertLess(save.index("resources->save("), save.index('mark("write.end"'))
        program = self.program(
            "testCityStructuredMetadataAndOwnedItemsSurviveSaveReload",
            "native city metadata and item ownership survived save reload",
        )
        self.assertIn("os.environ['GAME_SAVE_STAGE_DIAGNOSTICS'] = '1'", program)

    def testDeferredDiagnosticProbeUsesRealSavesAndKeepsTheExistingChildDeadline(self):
        from pathlib import Path

        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        method = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "testNativeSaveDiagnosticsAreSilentByDefaultAndPreserveTheSavedDocument"
        )
        call = next(
            node
            for node in ast.walk(method)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "runChild"
        )
        self.assertEqual(
            {"return_stderr": True}, {keyword.arg: ast.literal_eval(keyword.value) for keyword in call.keywords}
        )
        program = ast.literal_eval(call.args[0])
        child = ast.parse(textwrap.dedent(program))
        operations = [ast.unparse(node.func) for node in ast.walk(child) if isinstance(node, ast.Call)]
        self.assertEqual(2, operations.count("game.CMapLoader.saveWithResult"))
        self.assertIn("os.environ.pop('GAME_SAVE_STAGE_DIAGNOSTICS', None)", program)
        self.assertIn("os.environ['GAME_SAVE_STAGE_DIAGNOSTICS'] = '1'", program)
        self.assertIn("assert documents[0] == documents[1]", program)
        self.assertIn("if completed:", program)

    def testConstructionProbeChecksActualInitializedItemsAndTextMetadata(self):
        program = self.program(
            "testCityLoadsNativePlacedAndDeferredActorsWithBlockedLayerFallback",
            "native city construction and five-level blocked fallback verified",
        )
        self.assertIn("assert marek.getStringProperty('sourceInventory')", program)
        self.assertIn("marek.getBoolProperty('plugin_cityInventoryInitialized')", program)
        self.assertIn("*marek.getItems(), *marek.getEquipped().values()", program)
        self.assertIn("clock.getStringProperty('questDefinitions')", program)
        self.assertIn("clone = marek.clone()", program)

    def testFallbackCoordinatesUseTheExposedNativeTileProperties(self):
        program = self.program(
            "testCityLoadsNativePlacedAndDeferredActorsWithBlockedLayerFallback",
            "native city construction and five-level blocked fallback verified",
        )
        fallback = next(
            node
            for node in ast.walk(ast.parse(textwrap.dedent(program)))
            if isinstance(node, ast.For) and isinstance(node.target, ast.Name) and node.target.id == "level"
        )
        compiled = compile(ast.Module(body=[fallback], type_ignores=[]), "<actual-city-fallback-probe>", "exec")

        class NativeTile:
            __slots__ = ("properties",)

            def __init__(self, coords, corrupt):
                x, y, z = coords
                self.properties = dict(posx=x, posy=y, posz=z + int(corrupt))

            def getNumericProperty(self, name):
                return self.properties[name]

            def getTypeId(self):
                return "cityWallTile"

        class NativeWorld:
            def __init__(self, corrupt):
                self.corrupt = corrupt
                self.checked = []

            def getTile(self, x, y, z):
                return NativeTile((x, y, z), self.corrupt)

            def canStep(self, coords):
                self.checked.append(coords)
                return False

        namespace = {"game": SimpleNamespace(Coords=lambda x, y, z: (x, y, z))}
        world = NativeWorld(False)
        exec(compiled, {**namespace, "world": world})
        self.assertEqual(
            [(x, y, level) for level in range(5) for x, y in ((223, 191), (-1, 0), (224, 192))], world.checked
        )
        with self.assertRaises(AssertionError):
            exec(compiled, {**namespace, "world": NativeWorld(True)})

    def testChildTimeoutPreservesTheSameExceptionAndBoundedPartialOutput(self):
        import subprocess

        case = CityNativeLoadingRuntimeTest("testCityStructuredMetadataAndOwnedItemsSurviveSaveReload")
        for output, errors, expected in (
            (b"discarded-prefix" + b"x" * 9000 + b"city-metadata-phase saved", b"y" * 9000 + b"stderr-latest", "saved"),
            ("city-metadata-phase restore", "stderr-text", "restore"),
            (None, None, "unavailable"),
        ):
            timeout = subprocess.TimeoutExpired(["python", "-c", "native-child"], 30, output=output, stderr=errors)
            with self.subTest(output_type=type(output).__name__):
                with patch("tests.test_python_callback_lifecycle.subprocess.run", side_effect=timeout) as run:
                    with self.assertRaises(subprocess.TimeoutExpired) as caught:
                        case.runChild("pass")
                self.assertIs(timeout, caught.exception)
                self.assertEqual(30, run.call_args.kwargs["timeout"])
                notes = "\n".join(getattr(timeout, "__notes__", ()))
                self.assertIn("stdout tail", notes)
                self.assertIn("stderr tail", notes)
                self.assertIn(expected, notes)
                if errors is not None:
                    decoded_errors = errors.decode("utf-8", errors="replace") if isinstance(errors, bytes) else errors
                    self.assertIn(decoded_errors[-4096:], notes)
                self.assertNotIn("discarded-prefix", notes)
                self.assertLessEqual(len(notes), 8400)
                self.assertIs(output, timeout.stdout)
                self.assertIs(errors, timeout.stderr)

    def testSaveProbeHasFlushedElapsedBreadcrumbsAroundNativePersistence(self):
        from unittest.mock import Mock

        program = self.program(
            "testCityStructuredMetadataAndOwnedItemsSurviveSaveReload",
            "native city metadata and item ownership survived save reload",
        )
        tree = ast.parse(textwrap.dedent(program))
        phase = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "phase")
        output = Mock()
        namespace = {"print": output, "started": 100.0, "time": SimpleNamespace(monotonic=lambda: 100.125)}
        exec(compile(ast.Module(body=[phase], type_ignores=[]), "<actual-city-phase-breadcrumb>", "exec"), namespace)
        namespace["phase"]("save")
        output.assert_called_once_with("city-metadata-phase", "save", "elapsedSeconds=0.125", flush=True)
        for before, operation, after in (
            ("startMap", "game.CGameLoader.startGameWithPlayer", "mapReady"),
            ("save", "assert game.CMapLoader.saveWithResult(world, slot)", "saved"),
            ("loadSavedGame", "game.CGameLoader.loadSavedGame(restored, slot)", "savedMapLoaded"),
            ("savedMapLoaded", "saved_world = restored.getMap()", "verified"),
        ):
            with self.subTest(phase=before):
                self.assertLess(program.index("phase('" + before + "')"), program.index(operation))
                self.assertLess(program.index(operation), program.index("phase('" + after + "')"))

    def testSaveProbeUsesNativePersistenceAndPreservesFailedDiagnostics(self):
        program = self.program(
            "testCityStructuredMetadataAndOwnedItemsSurviveSaveReload",
            "native city metadata and item ownership survived save reload",
        )
        self.assertIn("assert game.CMapLoader.saveWithResult(world, slot)", program)
        self.assertIn("game.CGameLoader.loadSavedGame(restored, slot)", program)
        self.assertIn("assert snapshot(saved_actor) == before", program)
        self.assertIn("if completed:", program)


if __name__ == "__main__":
    unittest.main()
