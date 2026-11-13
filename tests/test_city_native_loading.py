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
        output = self.runChild(
            """
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
            """,
            timeout_seconds=30,
            timeout_observation_seconds=30,
        )
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

        progress = [
            (line, json.loads(line))
            for line in errors.splitlines()
            if line.startswith('{"diagnostic":"serialization-progress"')
        ]
        self.assertTrue(progress, "The enabled second save must expose real traversal progress")
        self.assertLessEqual(len(progress), 32)
        self.assertLessEqual(sum(len(line.encode()) + 1 for line, _row in progress), 32 * 512)
        rows = [row for _line, row in progress]
        self.assertEqual({"write"}, {row["direction"] for row in rows})
        self.assertEqual(1, len({row["session"] for row in rows}))
        self.assertEqual(("begin", "end"), (rows[0]["stage"], rows[-1]["stage"]))
        self.assertTrue(rows[-1]["finished"])
        self.assertTrue(all(row["unwinding"] is False for row in rows))
        self.assertGreater(rows[-1]["objects"], 0)
        self.assertGreater(rows[-1]["properties"], 0)
        self.assertGreater(rows[-1]["arrayEntries"], 0)
        counters = ("objects", "properties", "arrayEntries", "mapEntries", "graphNodes", "initializations")
        self.assertEqual(rows[-1]["visits"], sum(rows[-1][key] for key in counters))
        for key in ("elapsedMicroseconds", "visits", *counters):
            values = [row[key] for row in rows]
            self.assertTrue(all(type(value) is int and value >= 0 for value in values), key)
            self.assertEqual(sorted(values), values, key)


class CityNativeLoadingSourceTest(unittest.TestCase):
    def testSerializationProgressCountsExistingVisitsWithoutNewGraphWork(self):
        from pathlib import Path
        import re

        root = Path(__file__).resolve().parents[1]
        source = (root / "src/core/CSerialization.cpp").read_text(encoding="utf-8")
        header = (root / "src/core/CSerialization.h").read_text(encoding="utf-8")
        self.assertTrue("void CSerializationProgress::begin(" in source)
        helper = source[
            source.index("void CSerializationProgress::begin(") : source.index(
                "class CSerializationWriteContext::State"
            )
        ]
        self.assertEqual(1, helper.count('std::getenv("GAME_SAVE_STAGE_DIAGNOSTICS")'))
        self.assertTrue("if (activeSerializationProgress)" in helper)
        self.assertEqual(2, helper.count("session = activeSerializationProgress;"))
        self.assertTrue("if (!enabled)" in helper)
        disabled_guard = helper.index("if (!enabled)")
        admission = helper.index("activeSerializationProgress = this;")
        self.assertLess(disabled_guard, admission)
        self.assertIn("session = nullptr;", helper[disabled_guard:admission])
        self.assertIn("return;", helper[disabled_guard:admission])
        self.assertIn("#include <algorithm>", source)
        self.assertTrue("activeSerializationProgress = nullptr;" in helper)
        self.assertNotRegex(helper, "(?:meta|getType|getProperty|getTiles|getTile|dump)\\s*\\(")
        self.assertNotRegex(helper, "\\b(?:for|while)\\s*\\(")
        self.assertTrue("if (!session || !session->enabled)" in helper)
        self.assertTrue("if (session == this)" in helper)
        self.assertEqual(2, source.count("context.visit(CSerializationVisit::Object);"))
        self.assertEqual(2, source.count("context.visit(CSerializationVisit::Property);"))
        self.assertEqual(2, source.count("context.visit(CSerializationVisit::ArrayEntry);"))
        self.assertEqual(2, source.count("context.visit(CSerializationVisit::MapEntry);"))
        self.assertEqual(1, source.count("context.visit(CSerializationVisit::GraphNode);"))
        self.assertEqual(2, source.count("context.visit(CSerializationVisit::Initialization);"))
        self.assertRegex(source, "pending\\.pop_back\\(\\);\\s*context\\.visit\\(CSerializationVisit::GraphNode\\);")
        self.assertEqual(2, header.count("const CSerializationProgressCounters &progressCounters() const noexcept"))
        self.assertEqual(2, source.count("progress.join();"))
        join = helper[
            helper.index("void CSerializationProgress::join()") : helper.index("void CSerializationProgress::end()")
        ]
        self.assertNotIn("getenv", join)
        self.assertNotIn("mark(", join)
        self.assertNotIn("activeSerializationProgress =", join)
        loader = (root / "src/core/CLoader.cpp").read_text(encoding="utf-8")
        self.assertEqual(1, loader.count('CSerializationProgress progress("write");'))
        self.assertEqual(1, loader.count('CSerializationProgress progress("read");'))
        self.assertRegex(
            loader, r'CSerializationProgress progress\("write"\);\s*auto result = CSerialization::serializeExpected'
        )
        self.assertRegex(
            loader,
            r'CSerialization::StrictScope strict\(saveConfigKey\);\s*CSerializationProgress progress\("read"\);\s*map = handler->createObject<CMap>',
        )
        self.assertEqual(2, source.count("progress.end();"))
        self.assertEqual(2, source.count("progress.finished();"))

    def testSerializationProgressHasFixedRecordBytesAndDeterministicNativeBudget(self):
        from pathlib import Path
        import json
        import re

        root = Path(__file__).resolve().parents[1]
        source = (root / "src/core/CSerialization.cpp").read_text(encoding="utf-8")
        self.assertTrue("serializationProgressRecordLimit = 32;" in source)
        self.assertTrue("serializationProgressRecordBytes = 512;" in source)
        self.assertTrue("owner.counts.records + 1 < serializationProgressRecordLimit" in source)
        self.assertTrue("owner.nextVisit * 4" in source)
        self.assertTrue("void CSerializationProgress::mark(" in source)
        mark = source[
            source.index("void CSerializationProgress::mark(") : source.index("class CSerializationWriteContext::State")
        ]
        format_begin = mark.index('"{\\"diagnostic')
        format_end = mark.index("direction, static_cast", format_begin)
        packet = "".join(
            (ast.literal_eval(value) for value in re.findall('"(?:[^"\\\\]|\\\\.)*"', mark[format_begin:format_end]))
        )
        fields = re.findall("%llu|%lld|%s", packet)
        arguments = iter(
            (
                "write",
                str(2**64 - 1),
                "progress",
                str(2**63 - 1),
                *[str(2**64 - 1)] * 7,
                "initialization",
                "false",
                "false",
            )
        )
        record = re.sub("%llu|%lld|%s", lambda _match: next(arguments), packet)
        self.assertEqual(14, len(fields))
        self.assertLess(len(record.encode()), 512)
        self.assertEqual("serialization-progress", json.loads(record)["diagnostic"])
        self.assertTrue("std::min(static_cast<std::size_t>(length), sizeof(record) - 1)" in mark)
        self.assertNotIn("json", mark)
        native = (root / "tests/unit/test_serialization_performance.cpp").read_text(encoding="utf-8")
        self.assertTrue("void testSerializationProgressRecordBudget()" in native)
        self.assertEqual(1, native.count("    testSerializationProgressRecordBudget();"))
        self.assertTrue("constexpr std::size_t visits = 65536;" in native)
        thresholds = []
        threshold = 1
        while threshold <= 65536:
            thresholds.append(threshold)
            threshold *= 4
        self.assertEqual(11, 2 + len(thresholds))
        self.assertTrue("counts.records == 11" in native)
        self.assertTrue("counts.bytes <= counts.records * 512" in native)
        self.assertTrue("progress.counters().visits == 0" in native)
        self.assertIn("constexpr int independentRoots = 512;", native)
        self.assertIn("unadmitted-construction-root", native)
        self.assertIn("context.progressCounters().records == 0", native)
        self.assertIn(
            "unadmitted-tile-shaped-operation", (root / "tests/unit/test_core.cpp").read_text(encoding="utf-8")
        )
        core = (root / "tests/unit/test_core.cpp").read_text(encoding="utf-8")
        self.assertTrue("written.visits == 4" in core)
        self.assertTrue("read.visits == 4" in core)
        self.assertTrue("encoded->dump() == unchanged->dump()" in core)
        self.assertTrue("error.getError().code == CSerializationErrorCode::MissingCodec" in core)
        self.assertTrue("failed.progressCounters().records == 2" in core)
        self.assertRegex(
            core,
            r'try \{\s*CSerializationProgress error_admission\("write"\);\s*CSerializationOperation scope\(failed\);',
        )
        self.assertNotIn("error_admission.end();", core)

    def testOnlyObservedMcpSaveAndReloadChildrenOptIntoSerializationProgress(self):
        from pathlib import Path
        import os
        import sys
        import tempfile

        source = (Path(__file__).resolve().parents[1] / "test.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        owner = next((node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "McpServerTest"))
        methods = {node.name: node for node in owner.body if isinstance(node, ast.FunctionDef)}
        start = methods["_start_stdio_mcp_process"]
        self.assertIn("save_stage_diagnostics", {argument.arg for argument in start.args.kwonlyargs})
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            root = Path(directory)
            (root / "mcp.py").write_text("", encoding="utf-8")
            scope = {
                "REPO_ROOT": root,
                "TEST_OUTPUT_DIR": root,
                "CITY_WALKTHROUGH_CASES": {},
                "os": os,
                "sys": sys,
                "Path": Path,
                "build_dir": root,
                "build_config": None,
                "traceback": __import__("traceback"),
            }
            exec(
                compile(
                    ast.Module(body=[start, methods["_run_mcp_walkthrough"]], type_ignores=[]), "mcp-child", "exec"
                ),
                scope,
            )
            emitted = []
            case = unittest.TestCase()
            case._start_stdio_process = lambda command, **kwargs: emitted.append((command, kwargs)) or SimpleNamespace()
            invoke = lambda **kwargs: scope["_start_stdio_mcp_process"](case, **kwargs)
            invoke()
            self.assertIsNone(emitted[-1][1]["env"])
            invoke(save_stage_diagnostics=True)
            self.assertEqual({"GAME_SAVE_STAGE_DIAGNOSTICS": "1"}, emitted[-1][1]["env"])
            invoke(map_name="candlekeep")
            self.assertIsNone(emitted[-1][1]["env"])
            selected = []

            def stopAfterOptions(map_name, **options):
                selected.append((map_name, options))
                raise RuntimeError("source-only child admission stop")

            case._start_stdio_mcp_process = stopAfterOptions
            case._write_mcp_walkthrough_log = lambda *_args: None
            for map_name in ("baldursGate", "candlekeep", "test"):
                scope["_run_mcp_walkthrough"](case, map_name)
            self.assertEqual(
                [("baldursGate", {"save_stage_diagnostics": True}), ("candlekeep", {}), ("test", {})], selected
            )
        random_case = methods["testStdioRandomSaveReloadAndSecondSessionControllerMovement"]
        calls = [
            node
            for node in ast.walk(random_case)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and (node.func.attr == "_start_stdio_mcp_process")
        ]
        self.assertEqual(1, len(calls))
        self.assertEqual(
            {"save_stage_diagnostics": True}, {entry.arg: ast.literal_eval(entry.value) for entry in calls[0].keywords}
        )

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
        expected = (
            {"timeout_seconds": 30, "timeout_observation_seconds": 30}
            if method_name == ("testCityStructuredMetadataAndOwnedItemsSurviveSaveReload")
            else {}
        )
        self.assertEqual(expected, kwargs, "Keep acceptance 30 seconds; observation must remain diagnostic only")
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

    def testScopedSaveConfigBorrowsThePrivateParsedSnapshotAndRetainsRollbackGuards(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        loader = (root / "src/core/CLoader.cpp").read_text(encoding="utf-8")
        scoped = loader.split("class CScopedObjectConfig {", 1)[1].split("bool rehydrate_loaded_map(", 1)[0]
        constructor = scoped.split("~CScopedObjectConfig()", 1)[0]
        self.assertIn("std::shared_ptr<const json> value)", constructor)
        self.assertIn("this->handler->registerConfig(this->name, std::move(value));", constructor)
        for forbidden in ("make_shared", "const_pointer_cast", "shared_ptr<json> value"):
            self.assertNotIn(forbidden, constructor)
        self.assertIn("handler->getConfig(name) != installed", scoped)
        self.assertIn("handler->registerConfig(name, previous);", scoped)
        self.assertIn("handler->unregisterConfig(name);", scoped)
        self.assertIn("CScopedObjectConfig scopedSaveConfig(handler, saveConfigKey, saveDocument.snapshot);", loader)
        handler = (root / "src/handler/CObjectHandler.cpp").read_text(encoding="utf-8")
        mutable = handler.split(
            "void CObjectHandler::registerConfig(const std::string &name, std::shared_ptr<json> value)", 1
        )
        self.assertEqual(2, len(mutable))
        self.assertIn("std::make_shared<const json>(*value)", mutable[1].split("\n}", 1)[0])
        immutable = handler.split(
            "void CObjectHandler::registerConfig(const std::string &name, std::shared_ptr<const json> value)", 1
        )[1].split("\n}", 1)[0]
        self.assertIn("objectConfig.insert_or_assign(name, std::move(value));", immutable)
        self.assertNotIn("make_shared", immutable)
        codec = (root / "src/core/CSaveFormat.cpp").read_text(encoding="utf-8")
        self.assertIn('CJsonUtil::alias(document, (*document)["snapshot"])', codec)
        legacy = codec.split("migrateLegacySchema(", 1)[1].split("\n}", 1)[0]
        self.assertIn("std::make_shared<json>(*source.snapshot)", legacy)

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

    def testPostDeadlineObservationNeverAcceptsALateSuccessfulChild(self):
        import subprocess
        from unittest.mock import Mock

        deadline = subprocess.TimeoutExpired(["native-child"], 30, output=b"deadline stdout", stderr=b"deadline stderr")
        process = Mock(returncode=None)

        def communicate(**kwargs):
            if process.communicate.call_count == 1:
                raise deadline
            process.returncode = 0
            return "city-metadata-phase finished", "observed stderr"

        process.communicate.side_effect = communicate
        process.poll.side_effect = lambda: process.returncode
        case = CityNativeLoadingRuntimeTest("testCityStructuredMetadataAndOwnedItemsSurviveSaveReload")
        with patch("tests.test_python_callback_lifecycle.subprocess.Popen", return_value=process) as start:
            with self.assertRaises(subprocess.TimeoutExpired) as caught:
                case.runChild("pass", timeout_seconds=30, timeout_observation_seconds=30)
        self.assertIs(deadline, caught.exception)
        self.assertEqual(
            [{"timeout": 30}, {"timeout": 30}], [call.kwargs for call in process.communicate.call_args_list]
        )
        process.kill.assert_not_called()
        notes = "\n".join(deadline.__notes__)
        self.assertIn("completed returncode=0", notes)
        self.assertIn("city-metadata-phase finished", notes)
        self.assertEqual(b"deadline stdout", deadline.stdout)
        self.assertEqual(b"deadline stderr", deadline.stderr)
        self.assertEqual("dummy", start.call_args.kwargs["env"]["SDL_VIDEODRIVER"])
        self.assertEqual("software", start.call_args.kwargs["env"]["SDL_RENDER_DRIVER"])

    def testObservationBeforeDeadlineKeepsSuccessAndMissingNativeBehavior(self):
        from unittest.mock import Mock

        for returncode in (0, 77, 1):
            with self.subTest(returncode=returncode):
                process = Mock(returncode=returncode)
                process.communicate.return_value = ("stdout", "stderr")
                process.poll.return_value = returncode
                case = CityNativeLoadingRuntimeTest("testCityStructuredMetadataAndOwnedItemsSurviveSaveReload")
                with patch("tests.test_python_callback_lifecycle.subprocess.Popen", return_value=process):
                    if returncode == 0:
                        self.assertEqual(
                            ("stdout", "stderr"),
                            case.runChild("pass", return_stderr=True, timeout_observation_seconds=30),
                        )
                    else:
                        with self.assertRaises(unittest.SkipTest if returncode == 77 else AssertionError):
                            case.runChild("pass", timeout_observation_seconds=30)
                process.communicate.assert_called_once_with(timeout=30)
                process.kill.assert_not_called()

    def testObservationDeadlineOrFailureKillsDrainsAndKeepsOriginalTimeout(self):
        import subprocess
        from unittest.mock import Mock

        for observation_error in (subprocess.TimeoutExpired(["native-child"], 30), OSError("observer failed")):
            with self.subTest(error=type(observation_error).__name__):
                deadline = subprocess.TimeoutExpired(["native-child"], 30, output=b"original", stderr=b"original-error")
                process = Mock(returncode=None)
                process.communicate.side_effect = [
                    deadline,
                    observation_error,
                    ("x" * 9000 + "drained stdout", "y" * 9000 + "drained stderr"),
                ]
                process.poll.side_effect = lambda: process.returncode
                process.kill.side_effect = lambda: setattr(process, "returncode", -9)
                case = CityNativeLoadingRuntimeTest("testCityStructuredMetadataAndOwnedItemsSurviveSaveReload")
                with patch("tests.test_python_callback_lifecycle.subprocess.Popen", return_value=process):
                    with self.assertRaises(subprocess.TimeoutExpired) as caught:
                        case.runChild("pass", timeout_observation_seconds=30)
                self.assertIs(deadline, caught.exception)
                process.kill.assert_called_once_with()
                self.assertEqual(
                    [{"timeout": 30}, {"timeout": 30}, {"timeout": 5}],
                    [call.kwargs for call in process.communicate.call_args_list],
                )
                notes = "\n".join(deadline.__notes__)
                self.assertIn("drained stdout", notes)
                self.assertIn("drained stderr", notes)
                self.assertLess(len(notes), 17000)
                self.assertEqual(b"original", deadline.stdout)
                self.assertEqual(b"original-error", deadline.stderr)

    def testObservationStalledDrainDefersReaderPipesAndKeepsAcceptanceTimeout(self):
        import subprocess
        from unittest.mock import Mock

        for drain_error in (subprocess.TimeoutExpired(["child"], 5, output=b"latest stdout"), OSError("drain failed")):
            with self.subTest(error=type(drain_error).__name__):
                deadline = subprocess.TimeoutExpired(["child"], 30, output=b"original", stderr=b"original stderr")
                process = Mock(returncode=None)
                process.communicate.side_effect = [deadline, subprocess.TimeoutExpired(["child"], 30), drain_error]
                process.poll.return_value = None
                pipes = [SimpleNamespace(buffer=SimpleNamespace(raw=Mock()), close=Mock()) for _ in range(2)]
                process.stdout, process.stderr = pipes
                case = CityNativeLoadingRuntimeTest("testCityStructuredMetadataAndOwnedItemsSurviveSaveReload")
                with patch("tests.test_python_callback_lifecycle.subprocess.Popen", return_value=process):
                    with self.assertRaises(subprocess.TimeoutExpired) as caught:
                        case.runChild("pass", timeout_observation_seconds=30)
                self.assertIs(deadline, caught.exception)
                self.assertEqual(30, deadline.timeout)
                self.assertEqual(b"original", deadline.stdout)
                self.assertEqual(
                    [{"timeout": 30}, {"timeout": 30}, {"timeout": 5}],
                    [call.kwargs for call in process.communicate.call_args_list],
                )
                process.kill.assert_called_once_with()
                for pipe in pipes:
                    pipe.buffer.raw.close.assert_not_called()
                    pipe.close.assert_not_called()
                notes = "\n".join(deadline.__notes__)
                self.assertIn("max 5 seconds", notes)
                self.assertIn("cleanupIncomplete pipesPending=reader-owned", notes)
                self.assertIn(
                    (
                        "drainDeadlineExceeded"
                        if isinstance(drain_error, subprocess.TimeoutExpired)
                        else "drainError=OSError"
                    ),
                    notes,
                )

    def testObservationKillPollAndPipeOwnershipErrorsCannotMaskOriginalTimeout(self):
        import subprocess
        from unittest.mock import Mock

        for scenario in ("kill-error", "already-exited-race", "poll-error", "pipe-owner-poison"):
            with self.subTest(scenario=scenario):
                deadline = subprocess.TimeoutExpired(["child"], 30, output=b"original", stderr=b"original stderr")
                process = Mock(returncode=None)
                process.poll.side_effect = OSError("poll failed") if scenario == "poll-error" else lambda: None
                process.kill.side_effect = (
                    ProcessLookupError("already exited")
                    if scenario == "already-exited-race"
                    else PermissionError("kill failed") if scenario == "kill-error" else None
                )
                drain = ("late stdout", "late stderr") if scenario == "already-exited-race" else OSError("drain failed")
                process.communicate.side_effect = [deadline, subprocess.TimeoutExpired(["child"], 30), drain]
                pipes = [
                    SimpleNamespace(
                        close=Mock(side_effect=OSError("close failed") if scenario == "pipe-owner-poison" else None)
                    )
                    for _ in range(2)
                ]
                process.stdout, process.stderr = pipes
                case = CityNativeLoadingRuntimeTest("testCityStructuredMetadataAndOwnedItemsSurviveSaveReload")
                with patch("tests.test_python_callback_lifecycle.subprocess.Popen", return_value=process):
                    with self.assertRaises(subprocess.TimeoutExpired) as caught:
                        case.runChild("pass", timeout_observation_seconds=30)
                self.assertIs(deadline, caught.exception)
                self.assertEqual(
                    [{"timeout": 30}, {"timeout": 30}, {"timeout": 5}],
                    [call.kwargs for call in process.communicate.call_args_list],
                )
                process.kill.assert_called_once_with()
                notes = "\n".join(deadline.__notes__)
                expected = {
                    "kill-error": "killError=PermissionError",
                    "already-exited-race": "killError=ProcessLookupError",
                    "poll-error": "pollError=OSError",
                    "pipe-owner-poison": "cleanupIncomplete pipesPending=reader-owned",
                }[scenario]
                self.assertIn(expected, notes)
                if scenario != "already-exited-race":
                    for pipe in pipes:
                        pipe.close.assert_not_called()

    def testObservationFailedDrainNeverAccessesThrowingOrBlockingPipeClose(self):
        import subprocess
        from unittest.mock import Mock

        for failure_kind in ("throwing-close", "blocking-close"):
            with self.subTest(failure_kind=failure_kind):
                accesses = []

                class ReaderOwnedRaw:
                    @property
                    def close(self):
                        accesses.append(failure_kind)
                        raise AssertionError("A live reader close must not be accessed")

                raw = ReaderOwnedRaw()
                pipes = [SimpleNamespace(buffer=SimpleNamespace(raw=raw), close=Mock()) for _ in range(2)]
                deadline = subprocess.TimeoutExpired(["child"], 30, output=b"original")
                process = Mock(returncode=None)
                process.stdout, process.stderr = pipes
                process.poll.return_value = None
                process.communicate.side_effect = [
                    deadline,
                    subprocess.TimeoutExpired(["child"], 30),
                    subprocess.TimeoutExpired(["child"], 5),
                ]
                case = CityNativeLoadingRuntimeTest("testCityStructuredMetadataAndOwnedItemsSurviveSaveReload")
                with patch("tests.test_python_callback_lifecycle.subprocess.Popen", return_value=process):
                    with self.assertRaises(subprocess.TimeoutExpired) as caught:
                        case.runChild("pass", timeout_observation_seconds=30)
                self.assertIs(deadline, caught.exception)
                self.assertEqual([], accesses)
                for pipe in pipes:
                    pipe.close.assert_not_called()
                self.assertIn("cleanupIncomplete pipesPending=reader-owned", "\n".join(deadline.__notes__))

    def testObservationFirstCommunicationErrorAlsoUsesOneBoundedCleanup(self):
        from unittest.mock import Mock

        original = OSError("initial communication failed")
        process = Mock(returncode=None)
        process.poll.return_value = None
        process.kill.side_effect = PermissionError("kill failed")
        process.communicate.side_effect = [original, OSError("drain failed")]
        process.stdout, process.stderr = SimpleNamespace(close=Mock()), SimpleNamespace(close=Mock())
        case = CityNativeLoadingRuntimeTest("testCityStructuredMetadataAndOwnedItemsSurviveSaveReload")
        with patch("tests.test_python_callback_lifecycle.subprocess.Popen", return_value=process):
            with self.assertRaises(OSError) as caught:
                case.runChild("pass", timeout_observation_seconds=30)
        self.assertIs(original, caught.exception)
        self.assertEqual(
            [{"timeout": 30}, {"timeout": 5}], [call.kwargs for call in process.communicate.call_args_list]
        )
        process.kill.assert_called_once_with()
        process.stdout.close.assert_not_called()
        process.stderr.close.assert_not_called()

    def testObservationIsBoundedAndOnlyTheMetadataProbeOptsIn(self):
        from pathlib import Path
        import subprocess
        from unittest.mock import Mock

        case = CityNativeLoadingRuntimeTest("testCityStructuredMetadataAndOwnedItemsSurviveSaveReload")
        for value in (True, 30.0, -1, 31, 60):
            with self.subTest(value=value):
                with patch("tests.test_python_callback_lifecycle.subprocess.Popen") as start:
                    with self.assertRaises(ValueError):
                        case.runChild("pass", timeout_observation_seconds=value)
                start.assert_not_called()
        with self.assertRaises(ValueError):
            case.runChild("pass", timeout_seconds=60, timeout_observation_seconds=30)
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        opted = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "CityNativeLoadingRuntimeTest":
                for method in node.body:
                    for call in ast.walk(method):
                        if (
                            isinstance(call, ast.Call)
                            and isinstance(call.func, ast.Attribute)
                            and call.func.attr == "runChild"
                        ):
                            keywords = {keyword.arg: ast.literal_eval(keyword.value) for keyword in call.keywords}
                            if "timeout_observation_seconds" in keywords:
                                opted.append((method.name, keywords))
        self.assertEqual(
            [
                (
                    "testCityStructuredMetadataAndOwnedItemsSurviveSaveReload",
                    {"timeout_seconds": 30, "timeout_observation_seconds": 30},
                )
            ],
            opted,
        )

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
