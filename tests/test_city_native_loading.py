# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real staged city construction/fallback regression; no model or original-parity credit."""

import ast
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import tempfile
import textwrap
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.test_python_callback_lifecycle import ROOT, PythonCallbackLifecycleTest


@contextmanager
def book08RuntimeFixture(root):
    """Enable the component only in a bounded private copy of the active staged runtime."""
    root = Path(root).resolve(strict=True)
    tree = ast.parse((root / "play.py").read_text(encoding="utf8"))
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in {"_default_build_name", "_find_build_dir"}
    ]
    if len(functions) != 2:
        raise AssertionError("The pure play build-discovery helpers must be available")
    namespace = {"Path": Path, "os": os}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "<actual-play-build-discovery>", "exec"), namespace)
    build = namespace["_find_build_dir"](root)
    if build is None or not Path(build).is_dir():
        raise unittest.SkipTest("The compiled _game build is unavailable")
    build = Path(build).resolve(strict=True)
    configurations = ("Release", "Debug", "RelWithDebInfo", "MinSizeRel")
    selected_config = os.environ.get("GAME_BUILD_CONFIG")
    candidates = (
        [build / selected_config, build] if selected_config else [build / name for name in configurations] + [build]
    )
    native = None
    for directory in candidates:
        extensions = list(directory.glob("_game*.so")) + list(directory.glob("_game*.pyd"))
        if len(extensions) > 1:
            raise AssertionError("The active native module is ambiguous")
        if extensions:
            native = directory
            break
    if native is None:
        raise unittest.SkipTest("The compiled _game module is unavailable in the active build")
    resource_candidates = [build]
    if build.name in configurations:
        resource_candidates.append(build.parent)
    resources = next(
        (
            directory
            for directory in resource_candidates
            if all((directory / name).is_dir() for name in ("config", "maps", "plugins"))
        ),
        None,
    )
    if resources is None:
        raise AssertionError("The active build must contain staged config, maps and plugins")
    files = {}
    for name in ("config", "maps", "plugins", "images", "fonts", "campaigns"):
        folder = resources / name
        if folder.is_dir():
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    if path.is_symlink() or not path.resolve().is_relative_to(resources):
                        raise AssertionError("Staged resource links cannot escape the fixture input")
                    files[path.relative_to(resources)] = path
    for path in resources.glob("*.py"):
        files[Path(path.name)] = path
    for directory in dict.fromkeys((resources, native)):
        for path in sorted(directory.iterdir()):
            if path.is_file() and (path.suffix in {".dll", ".pyd", ".dylib"} or ".so" in path.suffixes):
                files[Path(path.name)] = path
    if len(files) > 2000 or sum(path.stat().st_size for path in files.values()) > 512 * 1024 * 1024:
        raise AssertionError("The staged BOOK08 fixture exceeds its 2000-file/512-MiB copy bound")
    config_name = Path("maps/baldursGate/config.json")
    original = json.loads(files[config_name].read_text(encoding="utf8"))
    config = json.loads(json.dumps(original))
    properties = config["cityClock"]["properties"]
    if (
        properties["plugin_cityPoisonSourceEnabled"] is not False
        or properties.get("plugin_cityBook08NativeConversionEnabled", False) is not False
    ):
        raise AssertionError("BOOK08 component tests require the disabled shipping defaults")
    properties["plugin_cityPoisonSourceEnabled"] = True
    properties["plugin_cityBook08NativeConversionEnabled"] = True
    with tempfile.TemporaryDirectory(prefix="book08-native-fixture-", dir=resources) as temporary:
        private = Path(temporary).resolve(strict=True)
        for relative, source in files.items():
            target = private / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        for name in ("config", "maps", "plugins", "save"):
            (private / name).mkdir(exist_ok=True)
        (private / config_name).write_text(
            json.dumps(config, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf8"
        )
        with patch.dict(os.environ, GAME_BUILD_DIR=str(private), GAME_BUILD_CONFIG=""):
            yield private


class CityNativeLoadingRuntimeTest(unittest.TestCase):
    runChild = PythonCallbackLifecycleTest.runChild

    def runBook08Child(self, code, *, return_stderr=False):
        with book08RuntimeFixture(ROOT):
            return self.runChild(code, return_stderr=return_stderr)

    def testCityQuestHintNativeDispatchReadsNonvirtualBackingTextOnce(self):
        output, errors = self.runChild(
            """

        import json
        import os
        from pathlib import Path
        import sys
        import types
        instance = game.CGameLoader.loadGame()
        try:
            game.CGameLoader.startGameWithPlayer(instance, 'baldursGate', 'Warrior')
            loop.run()
            world = instance.getMap()
            player = world.getPlayer()
            candidate = instance.createObject('cityQuinnDaggerQuest')
            assert isinstance(candidate, game.CQuest)
            assert candidate.getGame() is instance
            assert candidate.getStringProperty('questKey') == 'quinnDagger'
            logical_script = 'maps/baldursGate/script.py'
            module_dir = Path(game.__file__).resolve().parent
            roots = ([Path(os.environ['GAME_BUILD_DIR'])] if os.environ.get('GAME_BUILD_DIR') else [])
            roots += [module_dir, module_dir.parent]
            source_path = next((root / logical_script for root in roots if (root / logical_script).is_file()), None)
            if source_path is None:
                raise AssertionError('staged city script is required for profiler source identity')
            source_text = source_path.read_text(encoding='utf8')
            # Match CPluginLoader/pybind exec framing; compile only, never execute a replacement plugin.
            compiled = compile('# -*- coding: utf-8 -*-\\n' + source_text + '\\n', '<string>', 'exec', dont_inherit=True)
            def codes(value):
                result = [value]
                for child in value.co_consts:
                    if isinstance(child, types.CodeType):
                        result.extend(codes(child))
                return result
            expected = [code for code in codes(compiled) if code.co_qualname == 'load.<locals>.BaldursGateQuest.getHint']
            if len(expected) != 1:
                raise AssertionError(('staged authored getHint code must be unique', len(expected)))
            expected_code = expected[0]
            native_identity = game.CGameObject.ptr(candidate)
            candidate_name = game.CGameObject.getName(candidate)
            candidate_type = game.CGameObject.getTypeId(candidate)
            if not candidate_name or game.CGameObject.ptr(candidate) is not native_identity:
                raise AssertionError('candidate canonical native identity is unstable')
            def snapshot():
                return (world.getTurn(), tuple(player.getNumericProperty(key) for key in ('hp', 'mana', 'gold', 'exp')),
                        sorted(item.getName() for item in player.getItems()),
                        sorted((slot, item.getName() if item else None) for slot, item in player.getEquipped().items()),
                        sorted(quest.getName() for quest in player.getQuests()),
                        sorted(quest.getName() for quest in player.getCompletedQuests()))
            before = snapshot()
            for custom, expected_hint in (
                ('', 'Follow the named people, source items and city journal.'),
                ('Ask the named contact about the keepsake.', 'Ask the named contact about the keepsake.'),
            ):
                if custom:
                    candidate.setStringProperty('hintText', custom)
                calls, observed_codes, mismatches = [], [], []
                previous = sys.getprofile()
                def count(frame, event, argument):
                    code = frame.f_code
                    if event != 'call' or code.co_qualname != expected_code.co_qualname:
                        return
                    if (code.co_filename != expected_code.co_filename or code.co_firstlineno != expected_code.co_firstlineno
                            or code != expected_code or frame.f_globals.get('__file__') != logical_script):
                        if len(mismatches) < 8:
                            mismatches.append('source code identity')
                        return
                    owner = frame.f_locals.get('self')
                    if owner is None or game.CGameObject.ptr(owner) is not native_identity:
                        return
                    if (game.CGameObject.getName(owner) != candidate_name
                            or game.CGameObject.getTypeId(owner) != candidate_type
                            or game.CGameObject.getGame(owner) is not instance):
                        if len(mismatches) < 8:
                            mismatches.append('native quest ownership')
                        return
                    if observed_codes and code is not observed_codes[0]:
                        if len(mismatches) < 8:
                            mismatches.append('multiple actual code objects')
                        return
                    if not observed_codes:
                        observed_codes.append(code)
                    calls.append(1)
                game.set_logger_sink('stderr')
                try:
                    sys.setprofile(count)
                    try:
                        actual = game.CQuest.getHint(candidate)
                    finally:
                        sys.setprofile(previous)
                finally:
                    game.set_logger_sink('disabled')
                assert sys.getprofile() is previous, 'quest hint probe must restore the prior profiler'
                print('native city quest hint override calls=' + str(len(calls)), flush=True)
                print('native city quest hint identity=' + json.dumps(dict(
                    filename=expected_code.co_filename, qualname=expected_code.co_qualname,
                    firstLine=expected_code.co_firstlineno, pluginFile=logical_script,
                    nativeName=candidate_name, nativeType=candidate_type,
                    codeObjects=len(observed_codes), mismatches=mismatches)), flush=True)
                if not calls or mismatches:
                    raise AssertionError(('actual authored profiler target was not uniquely bound', len(calls), mismatches))
                if len(calls) != 1:
                    raise AssertionError(('native CQuest.getHint must call the authored override once', len(calls)))
                assert actual == expected_hint, (actual, expected_hint)
                assert snapshot() == before, 'reading a hint must preserve native progress, resources and ownership'
            print('native city quest hint fallback and authored text passed', flush=True)
        finally:
            instance.getContext().shutdown()
                """,
            return_stderr=True,
        )
        self.assertEqual(2, output.count("native city quest hint override calls=1"))
        self.assertIn("native city quest hint fallback and authored text passed", output)
        self.assertNotIn("RecursionError", errors)

    def testOptionalCityReferencesRespectActualNativeMissingPropertyContract(self):
        output = self.runChild("""
            import json
            instance = game.CGameLoader.loadGame()
            try:
                game.CGameLoader.startGameWithPlayer(instance, 'baldursGate', 'Warrior')
                loop.run()
                world = instance.getMap()
                assert world.getStringProperty('mapName') == 'baldursGate'
                clock = world.getObjectByName('cityClock')
                assert clock is not None
                probe = instance.createObject('CGameObject')
                assert not hasattr(probe, 'optionalNativeReference')
                try:
                    game.CGameObject.getObjectProperty(probe, 'optionalNativeReference')
                except IndexError as error:
                    assert 'property not found' in str(error)
                    print('actual native absent object getter throws IndexError', flush=True)
                else:
                    raise AssertionError('native absent object getter contract changed')
                probe.setObjectProperty('optionalNativeReference', None)
                assert hasattr(probe, 'optionalNativeReference')
                assert game.CGameObject.getObjectProperty(probe, 'optionalNativeReference') is None
                probe.setNumericProperty('wrongNativeReference', 17)
                assert hasattr(probe, 'wrongNativeReference')
                try:
                    game.CGameObject.getObjectProperty(probe, 'wrongNativeReference')
                except RuntimeError:
                    pass
                else:
                    raise AssertionError('present wrong native type was hidden')
                # A fresh optional row is absent in both phases even if initialization cached Narlen.
                original_definitions = clock.getStringProperty('relocationDefinitions')
                rows = json.loads(original_definitions.removeprefix('city-json:'))
                probe_id = 'optionalNativeProbe'
                probe_cache = 'plugin_cityRelocationActor_' + probe_id
                assert all(row['id'] != probe_id for row in rows)
                assert not hasattr(clock, probe_cache)
                rows.append(dict(id=probe_id, canonicalActorId='optionalNativeMissingActor', sourceCreature='NARLEN', scenes=[]))
                clock.setStringProperty('relocationDefinitions', 'city-json:' + json.dumps(rows))
                try:
                    # Genuine registered city clock and actual production method; no replacement owner or map.
                    clock.relocateActors()
                    assert not hasattr(clock, probe_cache)
                    row = next(row for row in rows if row['id'] == 'narlen')
                    narlen = clock.getObjectProperty('plugin_cityRelocationActor_narlen')
                    assert isinstance(narlen, game.CCreature)
                    assert narlen.getName() == row['canonicalActorId']
                    assert narlen.getGame() is instance
                    assert narlen.getBoolProperty('plugin_cityRelocationManaged')
                    clock.relocateActors()
                    assert clock.getObjectProperty('plugin_cityRelocationActor_narlen') is narlen
                finally:
                    clock.setStringProperty('relocationDefinitions', original_definitions)
                print('actual city clock relocation/native property cases passed', flush=True)
            finally:
                instance.getContext().shutdown()
            """)
        self.assertIn("actual native absent object getter throws IndexError", output)
        self.assertIn("actual city clock relocation/native property cases passed", output)

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

    def testBook08NativeUseChangesOwnedBaseAndFreshCompositionOnce(self):
        output, errors = self.runBook08Child(
            """
            import json
            import os
            from pathlib import Path

            if not __debug__:
                raise AssertionError('Native BOOK08 assertions require an unoptimized child')
            def decode(value):
                return json.loads(value.removeprefix('city-json:'))
            def numeric(value, key):
                return game.CGameObject.getNumericProperty(value, key)
            def objectProperty(value, key):
                return game.CGameObject.getObjectProperty(value, key)
            def inventory(owner):
                return {item.getName(): item for item in owner.getItems()}
            def equipment(owner):
                return {slot: item for slot, item in owner.getEquipped().items() if item is not None}
            def sameObjects(actual, expected):
                return actual.keys() == expected.keys() and all(actual[key] is expected[key] for key in actual)
            stat_keys = ('strength', 'agility', 'stamina', 'intelligence', 'armor', 'block', 'dmgMin', 'dmgMax',
                'attack', 'hit', 'crit', 'fireResist', 'frostResist', 'normalResist', 'thunderResist',
                'shadowResist', 'damage')
            def stats(value):
                return {key: numeric(value, key) for key in stat_keys}
            def resources(owner):
                active_map = game.CMapObject.getMap(owner)
                return tuple(numeric(owner, key) for key in ('hp', 'mana', 'gold', 'exp')) + tuple(
                    numeric(active_map, key) for key in ('plugin_cityStanding', 'plugin_cityReputation'))
            def use(owner, item):
                game.set_logger_sink('stderr')
                try:
                    owner.useItem(item)
                    for unused in range(3):
                        loop.run()
                finally:
                    game.set_logger_sink('disabled')

            fixture_root = Path(os.environ['GAME_BUILD_DIR']).resolve(strict=True)
            config_path = Path(game.CResourcesProvider.getInstance().getPath('maps/baldursGate/config.json'))
            assert config_path.resolve(strict=True) == (fixture_root / 'maps/baldursGate/config.json').resolve(strict=True), (
                'BOOK08 must use the explicit, fresh private initial-config fixture', str(config_path))
            initial = json.loads(config_path.read_text(encoding='utf8'))['cityClock']['properties']
            assert initial['plugin_cityPoisonSourceEnabled'] is True, 'Source poison must be enabled before map creation'
            assert initial['plugin_cityBook08NativeConversionEnabled'] is True, 'BOOK08 must be enabled before map creation'
            instance = game.CGameLoader.loadGame()
            try:
                game.CGameLoader.startGameWithPlayer(instance, 'baldursGate', 'Warrior', 'wandererRace')
                loop.run()
                world = instance.getMap()
                player = world.getPlayer()
                clock = world.getObjectByName('cityClock')
                assert player.isAlive() and player.getGame() is instance
                assert clock.getBoolProperty('plugin_cityPoisonSourceEnabled')
                assert clock.getBoolProperty('plugin_cityBook08NativeConversionEnabled')
                clock.poisonInitializeSource()
                state = decode(clock.getStringProperty('plugin_cityPoisonSourceState'))
                assert state['sourceVersion'] == 1 and state['receipts']['sourceInitialization']['status'] == 'complete'
                definitions = decode(clock.getStringProperty('poisonSourceDefinitions'))
                rows = [row for row in definitions['initialActors'] if row['resource'] == 'CHANTH']
                assert len(rows) == 1
                donor = world.getObjectByName(rows[0]['id'])
                assert donor is not None and donor.getGame() is instance and donor.isAlive()
                donor_before = inventory(donor)
                books = [item for item in donor_before.values() if item.getStringProperty('plugin_citySourceItem') == 'BOOK08']
                assert len(books) == 1, 'The actual initialized CHANTH must own exactly one original BOOK08'
                book = books[0]
                book_name = book.getName()
                assert book.getTypeId() == 'cityItemBook08' and book.getGame() is instance
                assert numeric(book, 'plugin_cityQuantity') == 1 and numeric(book, 'plugin_citySourceFlags') == 0
                assert decode(book.getStringProperty('plugin_cityCharges')) == [0, 0, 0]
                assert book.getBoolProperty('plugin_cityUnidentified')
                assert book.getBoolProperty('plugin_cityAbilitiesPending')
                assert not book.getBoolProperty('plugin_cityBook08Consumed')
                donor.removeQuestItem(lambda candidate: candidate is book)
                player.addItem(book)
                assert inventory(player)[book_name] is book
                assert sameObjects(inventory(donor), {key: value for key, value in donor_before.items() if value is not book})
                race = objectProperty(player, 'race')
                assert player.getRaceId() == 'wandererRace'
                assert game.CGameObject.getTypeId(race) == 'wandererRace'
                assert numeric(objectProperty(race, 'baseStats'), 'intelligence') == 1
                assert player.getItemAtSlot('2') is None
                without_helmet = numeric(player.getStats(), 'intelligence')
                helmet = instance.createObject('CHelmet')
                assert isinstance(helmet, game.CHelmet) and helmet.getGame() is instance
                game.CGameObject.setStringProperty(helmet, 'name', 'book08-native-helmet-' + str(os.getpid()))
                numeric_bonus = objectProperty(helmet, 'bonus')
                game.CGameObject.setNumericProperty(numeric_bonus, 'intelligence', 4)
                player.addItem(helmet)
                player.equipItem('2', helmet)
                assert player.getItemAtSlot('2') is helmet
                assert numeric(player.getStats(), 'intelligence') == without_helmet + 4
                player.setHp(player.getHpMax())
                player.setMana(player.getManaMax())
                assert player.getHp() == player.getHpMax() and player.getMana() == player.getManaMax()
                base = objectProperty(player, 'baseStats')
                base_before = stats(base)
                base_main_stat = base.getStringProperty('mainStat')
                cached = player.getStats()
                composed_before = stats(cached)
                composed_main_stat = cached.getStringProperty('mainStat')
                resources_before = resources(player)
                inventory_before = inventory(player)
                equipped_before = equipment(player)
                state_before = decode(clock.getStringProperty('plugin_cityPoisonSourceState'))
                assert not any(key.startswith('book08Use:') for key in state_before['receipts'])
                print('book08-native-admitted ' + json.dumps({
                    'item': book_name, 'itemType': book.getType(), 'sourceActor': rows[0]['id'],
                    'sourceVersion': state_before['sourceVersion'], 'raceIntelligence': 1, 'equipmentIntelligence': 4,
                    'storedCharges': [0, 0, 0], 'baseIntelligence': base_before['intelligence'],
                    'composedIntelligence': composed_before['intelligence'],
                    'hp': player.getHp(), 'hpMax': player.getHpMax(), 'mana': player.getMana(),
                    'manaMax': player.getManaMax()}, sort_keys=True), flush=True)
                book.setBoolProperty('plugin_cityUnidentified', False)
                clock.setBoolProperty('plugin_cityBook08NativeConversionEnabled', False)
                use(player, book)
                assert stats(base) == base_before and stats(player.getStats()) == composed_before
                assert sameObjects(inventory(player), inventory_before) and sameObjects(equipment(player), equipped_before)
                assert resources(player) == resources_before
                assert not book.getBoolProperty('plugin_cityBook08Consumed')
                assert decode(book.getStringProperty('plugin_cityCharges')) == [0, 0, 0]
                assert decode(clock.getStringProperty('plugin_cityPoisonSourceState')) == state_before
                book.setBoolProperty('plugin_cityUnidentified', True)
                clock.setBoolProperty('plugin_cityBook08NativeConversionEnabled', True)
                use(player, book)
                assert stats(base) == base_before, 'An unidentified BOOK08 must not alter base stats'
                assert sameObjects(inventory(player), inventory_before) and resources(player) == resources_before
                assert decode(clock.getStringProperty('plugin_cityPoisonSourceState')) == state_before
                assert decode(book.getStringProperty('plugin_cityCharges')) == [0, 0, 0]
                book.setBoolProperty('plugin_cityUnidentified', False)
                use(player, book)
                print('book08-native-effect ' + json.dumps({
                    'baseBefore': base_before['intelligence'], 'baseAfter': numeric(base, 'intelligence'),
                    'composedBefore': composed_before['intelligence'],
                    'composedAfter': numeric(player.getStats(), 'intelligence'),
                    'ownedAfter': any(item is book for item in player.getItems()),
                    'consumedAfter': book.getBoolProperty('plugin_cityBook08Consumed')}, sort_keys=True), flush=True)
                assert numeric(base, 'intelligence') == base_before['intelligence'] + 1, (
                    'BOOK08 native use must increment owned base Intelligence exactly once')
                expected_base = dict(base_before, intelligence=base_before['intelligence'] + 1)
                expected_composed = dict(composed_before, intelligence=composed_before['intelligence'] + 1)
                assert objectProperty(player, 'baseStats') is base and stats(base) == expected_base
                assert base.getStringProperty('mainStat') == base_main_stat
                assert stats(cached) == composed_before and stats(player.getStats()) == expected_composed
                assert player.getStats().getStringProperty('mainStat') == composed_main_stat
                assert resources(player) == resources_before
                assert sameObjects(inventory(player), {key: value for key, value in inventory_before.items() if value is not book})
                assert sameObjects(equipment(player), equipped_before)
                assert book.getBoolProperty('plugin_cityBook08Consumed')
                assert decode(book.getStringProperty('plugin_cityCharges')) == [0, 0, 0]
                assert book.getBoolProperty('plugin_cityAbilitiesPending')
                state_after = decode(clock.getStringProperty('plugin_cityPoisonSourceState'))
                receipt_key = 'book08Use:' + book_name
                receipt = state_after['receipts'][receipt_key]
                assert receipt == {
                    'status': 'complete', 'item': book_name, 'owner': player.getName(), 'chargeBefore': 1,
                    'storedChargesBefore': [0, 0, 0], 'chargePolicy': 'ordinaryBook08SingleUse',
                    'sourceEffect': 'BOOK08.ITM:effect0', 'conversion': 'ownedBaseIntelligencePlusOne',
                    'baseBefore': base_before['intelligence'], 'composedBefore': composed_before['intelligence'],
                    'steps': ['singleEffectiveChargeReserved', 'permanentOwnedBaseIntelligence', 'actualUsedInstanceRemoved']}
                expected_state = json.loads(json.dumps(state_before))
                expected_state['receipts'][receipt_key] = receipt
                assert state_after == expected_state, 'BOOK08 must not grant unrelated quest progress or rewards'
                player.equipItem('2', None)
                assert numeric(player.getStats(), 'intelligence') == composed_before['intelligence'] - 4 + 1
                player.equipItem('2', helmet)
                assert player.getItemAtSlot('2') is helmet and stats(player.getStats()) == expected_composed
                for unused in range(3):
                    loop.run()
                assert instance.getMap() is world and stats(player.getStats()) == expected_composed
                # Reintroduce only the same spent instance as an explicit adversarial unit fixture.
                player.addItem(book)
                for clear_spent_marker in (False, True):
                    if clear_spent_marker:
                        book.setBoolProperty('plugin_cityBook08Consumed', False)
                    use(player, book)
                    assert stats(base) == expected_base and stats(player.getStats()) == expected_composed
                    assert inventory(player)[book_name] is book and resources(player) == resources_before
                    assert decode(book.getStringProperty('plugin_cityCharges')) == [0, 0, 0]
                    assert decode(clock.getStringProperty('plugin_cityPoisonSourceState')) == state_after
                assert sameObjects(equipment(player), equipped_before)
                print('book08-native-use-once passed', flush=True)
            finally:
                instance.getContext().shutdown()
            """,
            return_stderr=True,
        )
        self.assertIn("book08-native-use-once passed", output)
        self.assertNotIn("Traceback", errors)
        self.assertNotIn("PoisonBindingChanged", errors)
        self.assertNotIn("Python callback failed", errors)
        self.assertNotIn("IndexError", errors)
        for line in output.splitlines():
            if line.startswith("book08-native-"):
                self.assertLess(len(line), 8192)
                print(line, flush=True)

    def testBook08SpentStateSurvivesNativeSaveReload(self):
        output, errors = self.runBook08Child(
            """
            import json
            import os
            from pathlib import Path

            if not __debug__:
                raise AssertionError('Native BOOK08 assertions require an unoptimized child')
            def decode(value):
                return json.loads(value.removeprefix('city-json:'))
            def numeric(value, key):
                return game.CGameObject.getNumericProperty(value, key)
            def objectProperty(value, key):
                return game.CGameObject.getObjectProperty(value, key)
            def inventory(owner):
                return {item.getName(): item for item in owner.getItems()}
            def equipment(owner):
                return {slot: item for slot, item in owner.getEquipped().items() if item is not None}
            def sameObjects(actual, expected):
                return actual.keys() == expected.keys() and all(actual[key] is expected[key] for key in actual)
            stat_keys = ('strength', 'agility', 'stamina', 'intelligence', 'armor', 'block', 'dmgMin', 'dmgMax',
                'attack', 'hit', 'crit', 'fireResist', 'frostResist', 'normalResist', 'thunderResist',
                'shadowResist', 'damage')
            def stats(value):
                return {key: numeric(value, key) for key in stat_keys}
            def resources(owner):
                active_map = game.CMapObject.getMap(owner)
                return tuple(numeric(owner, key) for key in ('hp', 'mana', 'gold', 'exp')) + tuple(
                    numeric(active_map, key) for key in ('plugin_cityStanding', 'plugin_cityReputation'))
            def use(owner, item):
                game.set_logger_sink('stderr')
                try:
                    owner.useItem(item)
                    for unused in range(3):
                        loop.run()
                finally:
                    game.set_logger_sink('disabled')

            fixture_root = Path(os.environ['GAME_BUILD_DIR']).resolve(strict=True)
            config_path = Path(game.CResourcesProvider.getInstance().getPath('maps/baldursGate/config.json'))
            assert config_path.resolve(strict=True) == (fixture_root / 'maps/baldursGate/config.json').resolve(strict=True), (
                'BOOK08 must use the explicit, fresh private initial-config fixture', str(config_path))
            initial = json.loads(config_path.read_text(encoding='utf8'))['cityClock']['properties']
            assert initial['plugin_cityPoisonSourceEnabled'] is True, 'Source poison must be enabled before map creation'
            assert initial['plugin_cityBook08NativeConversionEnabled'] is True, 'BOOK08 must be enabled before map creation'

            import time
            slot = 'city-book08-spent-' + str(os.getpid()) + '-' + str(time.time_ns())
            restored = None
            completed = False
            instance = game.CGameLoader.loadGame()
            try:
                game.CGameLoader.startGameWithPlayer(instance, 'baldursGate', 'Warrior', 'wandererRace')
                loop.run()
                world = instance.getMap()
                player = world.getPlayer()
                clock = world.getObjectByName('cityClock')
                assert player.isAlive() and player.getGame() is instance
                assert clock.getBoolProperty('plugin_cityPoisonSourceEnabled')
                assert clock.getBoolProperty('plugin_cityBook08NativeConversionEnabled')
                clock.poisonInitializeSource()
                state = decode(clock.getStringProperty('plugin_cityPoisonSourceState'))
                assert state['sourceVersion'] == 1 and state['receipts']['sourceInitialization']['status'] == 'complete'
                definitions = decode(clock.getStringProperty('poisonSourceDefinitions'))
                rows = [row for row in definitions['initialActors'] if row['resource'] == 'CHANTH']
                assert len(rows) == 1
                donor = world.getObjectByName(rows[0]['id'])
                assert donor is not None and donor.getGame() is instance and donor.isAlive()
                donor_before = inventory(donor)
                books = [item for item in donor_before.values() if item.getStringProperty('plugin_citySourceItem') == 'BOOK08']
                assert len(books) == 1, 'The actual initialized CHANTH must own exactly one original BOOK08'
                book = books[0]
                book_name = book.getName()
                assert book.getTypeId() == 'cityItemBook08' and book.getGame() is instance
                assert numeric(book, 'plugin_cityQuantity') == 1 and numeric(book, 'plugin_citySourceFlags') == 0
                assert decode(book.getStringProperty('plugin_cityCharges')) == [0, 0, 0]
                assert book.getBoolProperty('plugin_cityUnidentified')
                assert book.getBoolProperty('plugin_cityAbilitiesPending')
                assert not book.getBoolProperty('plugin_cityBook08Consumed')
                donor.removeQuestItem(lambda candidate: candidate is book)
                player.addItem(book)
                assert inventory(player)[book_name] is book
                assert sameObjects(inventory(donor), {key: value for key, value in donor_before.items() if value is not book})
                race = objectProperty(player, 'race')
                assert player.getRaceId() == 'wandererRace'
                assert game.CGameObject.getTypeId(race) == 'wandererRace'
                assert numeric(objectProperty(race, 'baseStats'), 'intelligence') == 1
                assert player.getItemAtSlot('2') is None
                without_helmet = numeric(player.getStats(), 'intelligence')
                helmet = instance.createObject('CHelmet')
                assert isinstance(helmet, game.CHelmet) and helmet.getGame() is instance
                game.CGameObject.setStringProperty(helmet, 'name', 'book08-native-helmet-' + str(os.getpid()))
                numeric_bonus = objectProperty(helmet, 'bonus')
                game.CGameObject.setNumericProperty(numeric_bonus, 'intelligence', 4)
                player.addItem(helmet)
                player.equipItem('2', helmet)
                assert player.getItemAtSlot('2') is helmet
                assert numeric(player.getStats(), 'intelligence') == without_helmet + 4
                player.setHp(player.getHpMax())
                player.setMana(player.getManaMax())
                assert player.getHp() == player.getHpMax() and player.getMana() == player.getManaMax()
                base = objectProperty(player, 'baseStats')
                base_before = stats(base)
                base_main_stat = base.getStringProperty('mainStat')
                cached = player.getStats()
                composed_before = stats(cached)
                composed_main_stat = cached.getStringProperty('mainStat')
                resources_before = resources(player)
                inventory_before = inventory(player)
                equipped_before = equipment(player)
                state_before = decode(clock.getStringProperty('plugin_cityPoisonSourceState'))
                assert not any(key.startswith('book08Use:') for key in state_before['receipts'])
                print('book08-native-admitted ' + json.dumps({
                    'item': book_name, 'itemType': book.getType(), 'sourceActor': rows[0]['id'],
                    'sourceVersion': state_before['sourceVersion'], 'raceIntelligence': 1, 'equipmentIntelligence': 4,
                    'storedCharges': [0, 0, 0], 'baseIntelligence': base_before['intelligence'],
                    'composedIntelligence': composed_before['intelligence'],
                    'hp': player.getHp(), 'hpMax': player.getHpMax(), 'mana': player.getMana(),
                    'manaMax': player.getManaMax()}, sort_keys=True), flush=True)
                book.setBoolProperty('plugin_cityUnidentified', False)
                clock.setBoolProperty('plugin_cityBook08NativeConversionEnabled', False)
                use(player, book)
                assert stats(base) == base_before and stats(player.getStats()) == composed_before
                assert sameObjects(inventory(player), inventory_before) and sameObjects(equipment(player), equipped_before)
                assert resources(player) == resources_before
                assert not book.getBoolProperty('plugin_cityBook08Consumed')
                assert decode(book.getStringProperty('plugin_cityCharges')) == [0, 0, 0]
                assert decode(clock.getStringProperty('plugin_cityPoisonSourceState')) == state_before
                book.setBoolProperty('plugin_cityUnidentified', True)
                clock.setBoolProperty('plugin_cityBook08NativeConversionEnabled', True)
                use(player, book)
                assert stats(base) == base_before, 'An unidentified BOOK08 must not alter base stats'
                assert sameObjects(inventory(player), inventory_before) and resources(player) == resources_before
                assert decode(clock.getStringProperty('plugin_cityPoisonSourceState')) == state_before
                assert decode(book.getStringProperty('plugin_cityCharges')) == [0, 0, 0]
                book.setBoolProperty('plugin_cityUnidentified', False)
                use(player, book)
                print('book08-native-effect ' + json.dumps({
                    'baseBefore': base_before['intelligence'], 'baseAfter': numeric(base, 'intelligence'),
                    'composedBefore': composed_before['intelligence'],
                    'composedAfter': numeric(player.getStats(), 'intelligence'),
                    'ownedAfter': any(item is book for item in player.getItems()),
                    'consumedAfter': book.getBoolProperty('plugin_cityBook08Consumed')}, sort_keys=True), flush=True)
                assert numeric(base, 'intelligence') == base_before['intelligence'] + 1, (
                    'BOOK08 native use must increment owned base Intelligence exactly once')
                expected_base = dict(base_before, intelligence=base_before['intelligence'] + 1)
                expected_composed = dict(composed_before, intelligence=composed_before['intelligence'] + 1)
                assert objectProperty(player, 'baseStats') is base and stats(base) == expected_base
                assert base.getStringProperty('mainStat') == base_main_stat
                assert stats(cached) == composed_before and stats(player.getStats()) == expected_composed
                assert player.getStats().getStringProperty('mainStat') == composed_main_stat
                assert resources(player) == resources_before
                assert sameObjects(inventory(player), {key: value for key, value in inventory_before.items() if value is not book})
                assert sameObjects(equipment(player), equipped_before)
                assert book.getBoolProperty('plugin_cityBook08Consumed')
                assert decode(book.getStringProperty('plugin_cityCharges')) == [0, 0, 0]
                assert book.getBoolProperty('plugin_cityAbilitiesPending')
                state_after = decode(clock.getStringProperty('plugin_cityPoisonSourceState'))
                receipt_key = 'book08Use:' + book_name
                receipt = state_after['receipts'][receipt_key]
                assert receipt == {
                    'status': 'complete', 'item': book_name, 'owner': player.getName(), 'chargeBefore': 1,
                    'storedChargesBefore': [0, 0, 0], 'chargePolicy': 'ordinaryBook08SingleUse',
                    'sourceEffect': 'BOOK08.ITM:effect0', 'conversion': 'ownedBaseIntelligencePlusOne',
                    'baseBefore': base_before['intelligence'], 'composedBefore': composed_before['intelligence'],
                    'steps': ['singleEffectiveChargeReserved', 'permanentOwnedBaseIntelligence', 'actualUsedInstanceRemoved']}
                expected_state = json.loads(json.dumps(state_before))
                expected_state['receipts'][receipt_key] = receipt
                assert state_after == expected_state, 'BOOK08 must not grant unrelated quest progress or rewards'
                player.equipItem('2', None)
                assert numeric(player.getStats(), 'intelligence') == composed_before['intelligence'] - 4 + 1
                player.equipItem('2', helmet)
                assert player.getItemAtSlot('2') is helmet and stats(player.getStats()) == expected_composed
                for unused in range(3):
                    loop.run()
                assert instance.getMap() is world and stats(player.getStats()) == expected_composed

                assert game.CMapLoader.saveWithResult(world, slot), 'Actual native BOOK08 save must succeed'
                restored = game.CGameLoader.loadGame()
                game.CGameLoader.loadSavedGame(restored, slot)
                loop.run()
                saved_world = restored.getMap()
                saved_player = saved_world.getPlayer()
                saved_clock = saved_world.getObjectByName('cityClock')
                saved_donor = saved_world.getObjectByName(rows[0]['id'])
                assert saved_world.getStringProperty('mapName') == 'baldursGate'
                assert saved_player.getGame() is restored and saved_player.isAlive()
                assert saved_clock.getBoolProperty('plugin_cityPoisonSourceEnabled')
                assert saved_clock.getBoolProperty('plugin_cityBook08NativeConversionEnabled')
                assert saved_player.getRaceId() == 'wandererRace'
                assert game.CGameObject.getTypeId(objectProperty(saved_player, 'race')) == 'wandererRace'
                assert numeric(objectProperty(objectProperty(saved_player, 'race'), 'baseStats'), 'intelligence') == 1
                assert saved_player.getItemAtSlot('2').getName() == helmet.getName()
                assert numeric(objectProperty(saved_player.getItemAtSlot('2'), 'bonus'), 'intelligence') == 4
                assert saved_donor is not None and saved_donor.getGame() is restored
                assert sorted(inventory(saved_donor)) == sorted(key for key, value in donor_before.items() if value is not book)
                assert not any(item.getStringProperty('plugin_citySourceItem') == 'BOOK08' for item in saved_donor.getItems())

                assert stats(objectProperty(saved_player, 'baseStats')) == expected_base
                assert stats(saved_player.getStats()) == expected_composed
                assert objectProperty(saved_player, 'baseStats').getStringProperty('mainStat') == base_main_stat
                assert resources(saved_player) == resources_before
                assert sorted(inventory(saved_player)) == sorted(key for key, value in inventory_before.items() if value is not book)
                assert sorted((slot_id, item.getName()) for slot_id, item in equipment(saved_player).items()) == sorted(
                    (slot_id, item.getName()) for slot_id, item in equipped_before.items())
                assert not any(item.getStringProperty('plugin_citySourceItem') == 'BOOK08' for item in saved_player.getItems())
                assert decode(saved_clock.getStringProperty('plugin_cityPoisonSourceState')) == state_after
                # The retained spent original is the sole replay fixture; no new tome or charge is minted.
                assert book.getGame() is instance and book.getBoolProperty('plugin_cityBook08Consumed')
                assert decode(book.getStringProperty('plugin_cityCharges')) == [0, 0, 0]
                print('book08-native-spent-reload ' + json.dumps({
                    'baseIntelligence': numeric(objectProperty(saved_player, 'baseStats'), 'intelligence'),
                    'composedIntelligence': numeric(saved_player.getStats(), 'intelligence'),
                    'bookOwned': False, 'receipt': decode(saved_clock.getStringProperty('plugin_cityPoisonSourceState'))[
                        'receipts'][receipt_key]}, sort_keys=True), flush=True)
                completed = True
                print('book08-native-spent-save-reload passed', flush=True)

            finally:
                if restored is not None:
                    restored.getContext().shutdown()
                instance.getContext().shutdown()
                if completed:
                    owned_save = fixture_root / 'save'
                    assert owned_save.resolve(strict=True) == owned_save and owned_save.is_dir()
                    for suffix in ('.json', '.json.bak'):
                        owned_path = owned_save / (slot + suffix)
                        assert not owned_path.is_symlink() and owned_path.resolve().parent == owned_save
                        owned_path.unlink(missing_ok=True)
            """,
            return_stderr=True,
        )
        self.assertIn("book08-native-spent-save-reload passed", output)
        self.assertNotIn("Traceback", errors)
        self.assertNotIn("PoisonBindingChanged", errors)
        self.assertNotIn("Python callback failed", errors)
        self.assertNotIn("IndexError", errors)
        for line in output.splitlines():
            if line.startswith("book08-native-"):
                self.assertLess(len(line), 8192)
                print(line, flush=True)

    def testBook08UnspentSubclassSurvivesNativeSaveReloadThenUses(self):
        output, errors = self.runBook08Child(
            """
            import json
            import os
            from pathlib import Path

            if not __debug__:
                raise AssertionError('Native BOOK08 assertions require an unoptimized child')
            def decode(value):
                return json.loads(value.removeprefix('city-json:'))
            def numeric(value, key):
                return game.CGameObject.getNumericProperty(value, key)
            def objectProperty(value, key):
                return game.CGameObject.getObjectProperty(value, key)
            def inventory(owner):
                return {item.getName(): item for item in owner.getItems()}
            def equipment(owner):
                return {slot: item for slot, item in owner.getEquipped().items() if item is not None}
            def sameObjects(actual, expected):
                return actual.keys() == expected.keys() and all(actual[key] is expected[key] for key in actual)
            stat_keys = ('strength', 'agility', 'stamina', 'intelligence', 'armor', 'block', 'dmgMin', 'dmgMax',
                'attack', 'hit', 'crit', 'fireResist', 'frostResist', 'normalResist', 'thunderResist',
                'shadowResist', 'damage')
            def stats(value):
                return {key: numeric(value, key) for key in stat_keys}
            def resources(owner):
                active_map = game.CMapObject.getMap(owner)
                return tuple(numeric(owner, key) for key in ('hp', 'mana', 'gold', 'exp')) + tuple(
                    numeric(active_map, key) for key in ('plugin_cityStanding', 'plugin_cityReputation'))
            def use(owner, item):
                game.set_logger_sink('stderr')
                try:
                    owner.useItem(item)
                    for unused in range(3):
                        loop.run()
                finally:
                    game.set_logger_sink('disabled')

            fixture_root = Path(os.environ['GAME_BUILD_DIR']).resolve(strict=True)
            config_path = Path(game.CResourcesProvider.getInstance().getPath('maps/baldursGate/config.json'))
            assert config_path.resolve(strict=True) == (fixture_root / 'maps/baldursGate/config.json').resolve(strict=True), (
                'BOOK08 must use the explicit, fresh private initial-config fixture', str(config_path))
            initial = json.loads(config_path.read_text(encoding='utf8'))['cityClock']['properties']
            assert initial['plugin_cityPoisonSourceEnabled'] is True, 'Source poison must be enabled before map creation'
            assert initial['plugin_cityBook08NativeConversionEnabled'] is True, 'BOOK08 must be enabled before map creation'

            import time
            slot = 'city-book08-unspent-' + str(os.getpid()) + '-' + str(time.time_ns())
            restored = None
            completed = False
            instance = game.CGameLoader.loadGame()
            try:
                game.CGameLoader.startGameWithPlayer(instance, 'baldursGate', 'Warrior', 'wandererRace')
                loop.run()
                world = instance.getMap()
                player = world.getPlayer()
                clock = world.getObjectByName('cityClock')
                assert player.isAlive() and player.getGame() is instance
                assert clock.getBoolProperty('plugin_cityPoisonSourceEnabled')
                assert clock.getBoolProperty('plugin_cityBook08NativeConversionEnabled')
                clock.poisonInitializeSource()
                state = decode(clock.getStringProperty('plugin_cityPoisonSourceState'))
                assert state['sourceVersion'] == 1 and state['receipts']['sourceInitialization']['status'] == 'complete'
                definitions = decode(clock.getStringProperty('poisonSourceDefinitions'))
                rows = [row for row in definitions['initialActors'] if row['resource'] == 'CHANTH']
                assert len(rows) == 1
                donor = world.getObjectByName(rows[0]['id'])
                assert donor is not None and donor.getGame() is instance and donor.isAlive()
                donor_before = inventory(donor)
                books = [item for item in donor_before.values() if item.getStringProperty('plugin_citySourceItem') == 'BOOK08']
                assert len(books) == 1, 'The actual initialized CHANTH must own exactly one original BOOK08'
                book = books[0]
                book_name = book.getName()
                assert book.getTypeId() == 'cityItemBook08' and book.getGame() is instance
                assert numeric(book, 'plugin_cityQuantity') == 1 and numeric(book, 'plugin_citySourceFlags') == 0
                assert decode(book.getStringProperty('plugin_cityCharges')) == [0, 0, 0]
                assert book.getBoolProperty('plugin_cityUnidentified')
                assert book.getBoolProperty('plugin_cityAbilitiesPending')
                assert not book.getBoolProperty('plugin_cityBook08Consumed')
                donor.removeQuestItem(lambda candidate: candidate is book)
                player.addItem(book)
                assert inventory(player)[book_name] is book
                assert sameObjects(inventory(donor), {key: value for key, value in donor_before.items() if value is not book})
                race = objectProperty(player, 'race')
                assert player.getRaceId() == 'wandererRace'
                assert game.CGameObject.getTypeId(race) == 'wandererRace'
                assert numeric(objectProperty(race, 'baseStats'), 'intelligence') == 1
                assert player.getItemAtSlot('2') is None
                without_helmet = numeric(player.getStats(), 'intelligence')
                helmet = instance.createObject('CHelmet')
                assert isinstance(helmet, game.CHelmet) and helmet.getGame() is instance
                game.CGameObject.setStringProperty(helmet, 'name', 'book08-native-helmet-' + str(os.getpid()))
                numeric_bonus = objectProperty(helmet, 'bonus')
                game.CGameObject.setNumericProperty(numeric_bonus, 'intelligence', 4)
                player.addItem(helmet)
                player.equipItem('2', helmet)
                assert player.getItemAtSlot('2') is helmet
                assert numeric(player.getStats(), 'intelligence') == without_helmet + 4
                player.setHp(player.getHpMax())
                player.setMana(player.getManaMax())
                assert player.getHp() == player.getHpMax() and player.getMana() == player.getManaMax()
                base = objectProperty(player, 'baseStats')
                base_before = stats(base)
                base_main_stat = base.getStringProperty('mainStat')
                cached = player.getStats()
                composed_before = stats(cached)
                composed_main_stat = cached.getStringProperty('mainStat')
                resources_before = resources(player)
                inventory_before = inventory(player)
                equipped_before = equipment(player)
                state_before = decode(clock.getStringProperty('plugin_cityPoisonSourceState'))
                assert not any(key.startswith('book08Use:') for key in state_before['receipts'])
                print('book08-native-admitted ' + json.dumps({
                    'item': book_name, 'itemType': book.getType(), 'sourceActor': rows[0]['id'],
                    'sourceVersion': state_before['sourceVersion'], 'raceIntelligence': 1, 'equipmentIntelligence': 4,
                    'storedCharges': [0, 0, 0], 'baseIntelligence': base_before['intelligence'],
                    'composedIntelligence': composed_before['intelligence'],
                    'hp': player.getHp(), 'hpMax': player.getHpMax(), 'mana': player.getMana(),
                    'manaMax': player.getManaMax()}, sort_keys=True), flush=True)

                expected_class = type(book).__name__
                assert expected_class == 'BaldursGateUnderstandingTome', 'Fresh AFTER tome must be the actual registered subclass'
                unspent_name = book.getName()
                unspent_source_fields = (
                    book.getStringProperty('plugin_citySourceItem'), numeric(book, 'plugin_cityQuantity'),
                    numeric(book, 'plugin_citySourceFlags'), book.getBoolProperty('plugin_cityUnidentified'),
                    book.getBoolProperty('plugin_cityAbilitiesPending'))

                assert game.CMapLoader.saveWithResult(world, slot), 'Actual native BOOK08 save must succeed'
                restored = game.CGameLoader.loadGame()
                game.CGameLoader.loadSavedGame(restored, slot)
                loop.run()
                saved_world = restored.getMap()
                saved_player = saved_world.getPlayer()
                saved_clock = saved_world.getObjectByName('cityClock')
                saved_donor = saved_world.getObjectByName(rows[0]['id'])
                assert saved_world.getStringProperty('mapName') == 'baldursGate'
                assert saved_player.getGame() is restored and saved_player.isAlive()
                assert saved_clock.getBoolProperty('plugin_cityPoisonSourceEnabled')
                assert saved_clock.getBoolProperty('plugin_cityBook08NativeConversionEnabled')
                assert saved_player.getRaceId() == 'wandererRace'
                assert game.CGameObject.getTypeId(objectProperty(saved_player, 'race')) == 'wandererRace'
                assert numeric(objectProperty(objectProperty(saved_player, 'race'), 'baseStats'), 'intelligence') == 1
                assert saved_player.getItemAtSlot('2').getName() == helmet.getName()
                assert numeric(objectProperty(saved_player.getItemAtSlot('2'), 'bonus'), 'intelligence') == 4
                assert saved_donor is not None and saved_donor.getGame() is restored
                assert sorted(inventory(saved_donor)) == sorted(key for key, value in donor_before.items() if value is not book)
                assert not any(item.getStringProperty('plugin_citySourceItem') == 'BOOK08' for item in saved_donor.getItems())

                assert stats(objectProperty(saved_player, 'baseStats')) == base_before
                assert stats(saved_player.getStats()) == composed_before and resources(saved_player) == resources_before
                assert decode(saved_clock.getStringProperty('plugin_cityPoisonSourceState')) == state_before
                assert sorted(inventory(saved_player)) == sorted(inventory_before)
                restored_books = [item for item in saved_player.getItems() if item.getName() == unspent_name]
                assert len(restored_books) == 1
                saved_book = restored_books[0]
                assert saved_book is not book and saved_book.getGame() is restored
                assert type(saved_book).__name__ == expected_class and saved_book.getTypeId() == 'cityItemBook08'
                assert decode(saved_book.getStringProperty('plugin_cityCharges')) == [0, 0, 0]
                assert not saved_book.getBoolProperty('plugin_cityBook08Consumed')
                assert (saved_book.getStringProperty('plugin_citySourceItem'), numeric(saved_book, 'plugin_cityQuantity'),
                        numeric(saved_book, 'plugin_citySourceFlags'), saved_book.getBoolProperty('plugin_cityUnidentified'),
                        saved_book.getBoolProperty('plugin_cityAbilitiesPending')) == unspent_source_fields
                world, player, clock, book = saved_world, saved_player, saved_clock, saved_book
                helmet = player.getItemAtSlot('2')
                base = objectProperty(player, 'baseStats')
                cached = player.getStats()
                inventory_before = inventory(player)
                equipped_before = equipment(player)
                book.setBoolProperty('plugin_cityUnidentified', False)
                clock.setBoolProperty('plugin_cityBook08NativeConversionEnabled', False)
                use(player, book)
                assert stats(base) == base_before and stats(player.getStats()) == composed_before
                assert sameObjects(inventory(player), inventory_before) and sameObjects(equipment(player), equipped_before)
                assert resources(player) == resources_before
                assert not book.getBoolProperty('plugin_cityBook08Consumed')
                assert decode(book.getStringProperty('plugin_cityCharges')) == [0, 0, 0]
                assert decode(clock.getStringProperty('plugin_cityPoisonSourceState')) == state_before
                book.setBoolProperty('plugin_cityUnidentified', True)
                clock.setBoolProperty('plugin_cityBook08NativeConversionEnabled', True)
                use(player, book)
                assert stats(base) == base_before and sameObjects(inventory(player), inventory_before)
                assert decode(clock.getStringProperty('plugin_cityPoisonSourceState')) == state_before
                book.setBoolProperty('plugin_cityUnidentified', False)
                use(player, book)
                print('book08-native-effect ' + json.dumps({
                    'baseBefore': base_before['intelligence'], 'baseAfter': numeric(base, 'intelligence'),
                    'composedBefore': composed_before['intelligence'],
                    'composedAfter': numeric(player.getStats(), 'intelligence'),
                    'ownedAfter': any(item is book for item in player.getItems()),
                    'consumedAfter': book.getBoolProperty('plugin_cityBook08Consumed')}, sort_keys=True), flush=True)
                assert numeric(base, 'intelligence') == base_before['intelligence'] + 1, (
                    'BOOK08 native use must increment owned base Intelligence exactly once')
                expected_base = dict(base_before, intelligence=base_before['intelligence'] + 1)
                expected_composed = dict(composed_before, intelligence=composed_before['intelligence'] + 1)
                assert objectProperty(player, 'baseStats') is base and stats(base) == expected_base
                assert base.getStringProperty('mainStat') == base_main_stat
                assert stats(cached) == composed_before and stats(player.getStats()) == expected_composed
                assert player.getStats().getStringProperty('mainStat') == composed_main_stat
                assert resources(player) == resources_before
                assert sameObjects(inventory(player), {key: value for key, value in inventory_before.items() if value is not book})
                assert sameObjects(equipment(player), equipped_before)
                assert book.getBoolProperty('plugin_cityBook08Consumed')
                assert decode(book.getStringProperty('plugin_cityCharges')) == [0, 0, 0]
                assert book.getBoolProperty('plugin_cityAbilitiesPending')
                state_after = decode(clock.getStringProperty('plugin_cityPoisonSourceState'))
                receipt_key = 'book08Use:' + book_name
                receipt = state_after['receipts'][receipt_key]
                assert receipt == {
                    'status': 'complete', 'item': book_name, 'owner': player.getName(), 'chargeBefore': 1,
                    'storedChargesBefore': [0, 0, 0], 'chargePolicy': 'ordinaryBook08SingleUse',
                    'sourceEffect': 'BOOK08.ITM:effect0', 'conversion': 'ownedBaseIntelligencePlusOne',
                    'baseBefore': base_before['intelligence'], 'composedBefore': composed_before['intelligence'],
                    'steps': ['singleEffectiveChargeReserved', 'permanentOwnedBaseIntelligence', 'actualUsedInstanceRemoved']}
                expected_state = json.loads(json.dumps(state_before))
                expected_state['receipts'][receipt_key] = receipt
                assert state_after == expected_state, 'BOOK08 must not grant unrelated quest progress or rewards'
                player.equipItem('2', None)
                assert numeric(player.getStats(), 'intelligence') == composed_before['intelligence'] - 4 + 1
                player.equipItem('2', helmet)
                assert player.getItemAtSlot('2') is helmet and stats(player.getStats()) == expected_composed
                for unused in range(3):
                    loop.run()
                assert restored.getMap() is world and stats(player.getStats()) == expected_composed

                completed = True
                print('book08-native-unspent-save-reload-use passed', flush=True)

            finally:
                if restored is not None:
                    restored.getContext().shutdown()
                instance.getContext().shutdown()
                if completed:
                    owned_save = fixture_root / 'save'
                    assert owned_save.resolve(strict=True) == owned_save and owned_save.is_dir()
                    for suffix in ('.json', '.json.bak'):
                        owned_path = owned_save / (slot + suffix)
                        assert not owned_path.is_symlink() and owned_path.resolve().parent == owned_save
                        owned_path.unlink(missing_ok=True)
            """,
            return_stderr=True,
        )
        self.assertIn("book08-native-unspent-save-reload-use passed", output)
        self.assertNotIn("Traceback", errors)
        self.assertNotIn("PoisonBindingChanged", errors)
        self.assertNotIn("Python callback failed", errors)
        self.assertNotIn("IndexError", errors)
        for line in output.splitlines():
            if line.startswith("book08-native-"):
                self.assertLess(len(line), 8192)
                print(line, flush=True)


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

    def testCityQuestHintFallbackNeverReadsItsReflectedVirtualProperty(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1] / "res/maps/baldursGate/script.py").read_text(encoding="utf8")
        load = next(
            node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == "load"
        )
        quest = next(node for node in load.body if isinstance(node, ast.ClassDef) and node.name == "BaldursGateQuest")
        hint = next(node for node in quest.body if isinstance(node, ast.FunctionDef) and node.name == "getHint")
        state = {}
        namespace = {"clock": lambda _quest: SimpleNamespace(poisonQuestPresentation=lambda _key: state.get("source"))}
        exec(compile(ast.Module(body=[hint], type_ignores=[]), "<actual-city-quest-hint>", "exec"), namespace)

        class ReflectedQuest:
            def __init__(self, values):
                self.values, self.reads = values, []

            def getStringProperty(self, name):
                self.reads.append(name)
                if name == "hint":
                    raise AssertionError("CQuest.hint reflects virtual getHint and must not be its backing field")
                return self.values.get(name, "")

        for source_row, custom, expected in (
            (None, "", "Follow the named people, source items and city journal."),
            (None, "Authored contact.", "Authored contact."),
            ({"hint": "Heard clue."}, "Other text.", "Heard clue."),
            ({"hint": ""}, "Authored contact.", "Authored contact."),
        ):
            with self.subTest(source_row=source_row, custom=custom):
                state["source"] = source_row
                candidate = ReflectedQuest({"questKey": "quinnDagger", "hintText": custom})
                self.assertEqual(expected, namespace["getHint"](candidate))
                self.assertEqual(
                    ["questKey"] + ([] if source_row and source_row.get("hint") else ["hintText"]), candidate.reads
                )

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

    def testBook08RuntimeFixtureIsPrivateForLinuxAndWindowsResourceLayouts(self):
        import json
        import os
        from pathlib import Path
        import tempfile

        helper = globals().get("book08RuntimeFixture")
        self.assertTrue(callable(helper), "A self-contained native BOOK08 fixture helper is required")
        play_source = (Path(__file__).resolve().parents[1] / "play.py").read_text(encoding="utf8")
        for layout in ("linux", "windows-release", "windows-native-root"):
            with self.subTest(layout=layout), tempfile.TemporaryDirectory(
                prefix="nouraajd-book08-source-"
            ) as temporary:
                root = Path(temporary)
                build = root / "cmake-build-release"
                native = build / "Release" if layout != "linux" else build
                native.mkdir(parents=True)
                for directory in ("config", "maps/baldursGate", "plugins"):
                    (build / directory).mkdir(parents=True, exist_ok=True)
                # This source must be parsed, never imported or bootstrapped in a source test.
                (root / "play.py").write_text(
                    "raise AssertionError('play must not execute during fixture discovery')\n" + play_source,
                    encoding="utf8",
                )
                source_config = {
                    "cityClock": {
                        "class": "Clock",
                        "properties": {
                            "plugin_cityPoisonSourceEnabled": False,
                            "unrelated": {"sourceIds": ["CHANTH", "BOOK08"], "value": 17},
                        },
                    },
                    "other": {"class": "CItem", "properties": {"nested": [0, False, "preserve"]}},
                }
                if layout == "linux":
                    source_config["cityClock"]["properties"]["plugin_cityBook08NativeConversionEnabled"] = False
                config_path = build / "maps/baldursGate/config.json"
                config_path.write_text(json.dumps(source_config, indent=2), encoding="utf8")
                (build / "config/native-fixture.json").write_text('{"keep": 7}', encoding="utf8")
                (build / "maps/baldursGate/script.py").write_text(
                    "raise AssertionError('not executed')\n", encoding="utf8"
                )
                (build / "plugins/native_fixture.py").write_text(
                    "raise AssertionError('not executed')\n", encoding="utf8"
                )
                (build / "game.py").write_text("raise AssertionError('game must not be imported')\n", encoding="utf8")
                extension = "_game.cp312-win_amd64.pyd" if layout != "linux" else "_game.cpython-test.so"
                shared_core = "game_core.dll" if layout != "linux" else "libgame_core.so"
                shared_dependency = "SDL2.dll" if layout != "linux" else "libSDL2.so"
                (native / extension).write_bytes(b"synthetic extension; never load")
                (native / shared_core).write_bytes(b"synthetic core; never load")
                (build / shared_dependency).write_bytes(b"synthetic dependency; never load")
                before = {
                    path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()
                }
                before_paths = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
                configuration = "Release" if layout == "windows-release" else ""
                with patch.dict(os.environ, {"GAME_BUILD_CONFIG": configuration}, clear=False):
                    # Exercise the actual play fallback search on Linux, and its explicit override on Windows.
                    if layout == "linux":
                        os.environ.pop("GAME_BUILD_DIR", None)
                    else:
                        os.environ["GAME_BUILD_DIR"] = str(native if layout == "windows-native-root" else build)
                    previous = {key: os.environ.get(key) for key in ("GAME_BUILD_DIR", "GAME_BUILD_CONFIG")}
                    with helper(root) as private:
                        self.assertIsInstance(private, Path)
                        private = private.resolve()
                        self.assertNotEqual(build.resolve(), private)
                        self.assertTrue(private.is_relative_to(build.resolve()))
                        self.assertEqual(str(private), os.environ["GAME_BUILD_DIR"])
                        self.assertEqual("", os.environ["GAME_BUILD_CONFIG"])
                        self.assertEqual(b"synthetic extension; never load", (private / extension).read_bytes())
                        self.assertEqual(b"synthetic core; never load", (private / shared_core).read_bytes())
                        self.assertEqual(
                            b"synthetic dependency; never load", (private / shared_dependency).read_bytes()
                        )
                        self.assertTrue((private / "save").is_dir())
                        self.assertEqual([], list((private / "save").iterdir()))
                        self.assertEqual((build / "game.py").read_bytes(), (private / "game.py").read_bytes())
                        self.assertEqual(
                            (build / "config/native-fixture.json").read_bytes(),
                            (private / "config/native-fixture.json").read_bytes(),
                        )
                        self.assertEqual(
                            (build / "maps/baldursGate/script.py").read_bytes(),
                            (private / "maps/baldursGate/script.py").read_bytes(),
                        )
                        self.assertEqual(
                            (build / "plugins/native_fixture.py").read_bytes(),
                            (private / "plugins/native_fixture.py").read_bytes(),
                        )
                        changed = json.loads((private / "maps/baldursGate/config.json").read_text(encoding="utf8"))
                        self.assertIs(True, changed["cityClock"]["properties"]["plugin_cityPoisonSourceEnabled"])
                        self.assertIs(
                            True, changed["cityClock"]["properties"]["plugin_cityBook08NativeConversionEnabled"]
                        )
                        changed["cityClock"]["properties"]["plugin_cityPoisonSourceEnabled"] = False
                        if "plugin_cityBook08NativeConversionEnabled" in source_config["cityClock"]["properties"]:
                            changed["cityClock"]["properties"]["plugin_cityBook08NativeConversionEnabled"] = False
                        else:
                            del changed["cityClock"]["properties"]["plugin_cityBook08NativeConversionEnabled"]
                        self.assertEqual(source_config, changed, "Only the two declared initial flags may change")
                    self.assertFalse(private.exists(), "Only the owned temporary fixture must be cleaned")
                    self.assertEqual(previous, {key: os.environ.get(key) for key in previous})
                self.assertEqual(before_paths, sorted(path.relative_to(root).as_posix() for path in root.rglob("*")))
                self.assertEqual(
                    before,
                    {
                        path.relative_to(root).as_posix(): path.read_bytes()
                        for path in root.rglob("*")
                        if path.is_file()
                    },
                )

    def testBook08RuntimeFixtureSkipsOnlyUnavailableNativeBuild(self):
        import os
        from pathlib import Path
        import tempfile

        helper = globals().get("book08RuntimeFixture")
        self.assertTrue(callable(helper), "A self-contained native BOOK08 fixture helper is required")
        play_source = (Path(__file__).resolve().parents[1] / "play.py").read_text(encoding="utf8")
        with tempfile.TemporaryDirectory(prefix="nouraajd-book08-no-native-") as temporary:
            root = Path(temporary)
            (root / "play.py").write_text(play_source, encoding="utf8")
            missing = root / "absent-build"
            with patch.dict(os.environ, {"GAME_BUILD_DIR": str(missing)}, clear=False):
                with self.assertRaises(unittest.SkipTest):
                    with helper(root):
                        self.fail("A missing compiled extension must not create a runnable fixture")
            self.assertFalse(missing.exists())
            self.assertEqual(["play.py"], sorted(path.relative_to(root).as_posix() for path in root.rglob("*")))

    def testBook08ChildUsesOneSharedChildWithItsOriginalDeadline(self):
        from contextlib import contextmanager
        from pathlib import Path

        method = getattr(CityNativeLoadingRuntimeTest, "runBook08Child", None)
        self.assertTrue(callable(method), "Native BOOK08 methods must use the self-contained fixture wrapper")
        calls = []

        @contextmanager
        def fixture(root):
            calls.append(("enter", root))
            try:
                yield Path("private-unused-fixture")
            finally:
                calls.append(("exit", root))

        case = CityNativeLoadingRuntimeTest("testCityLoadsNativePlacedAndDeferredActorsWithBlockedLayerFallback")
        with patch.dict(globals(), {"book08RuntimeFixture": fixture}), patch.object(
            case, "runChild", return_value=("book08-output", "book08-errors")
        ) as child:
            self.assertEqual(
                ("book08-output", "book08-errors"), case.runBook08Child("native child body", return_stderr=True)
            )
        child.assert_called_once_with("native child body", return_stderr=True)
        expected_root = Path(__file__).resolve().parents[1]
        self.assertEqual([("enter", expected_root), ("exit", expected_root)], calls)

    def testBook08RuntimeFixtureRejectsAmbiguousNativeAndRespectsRequestedConfig(self):
        import json
        import os
        from pathlib import Path
        import tempfile

        helper = globals().get("book08RuntimeFixture")
        self.assertTrue(callable(helper), "A self-contained native BOOK08 fixture helper is required")
        play_source = (Path(__file__).resolve().parents[1] / "play.py").read_text(encoding="utf8")
        with tempfile.TemporaryDirectory(prefix="nouraajd-book08-config-") as temporary:
            root = Path(temporary)
            build = root / "cmake-build-release"
            for name in ("config", "maps/baldursGate", "plugins", "Debug", "Release"):
                (build / name).mkdir(parents=True, exist_ok=True)
            (root / "play.py").write_text(play_source, encoding="utf8")
            initial = {
                "cityClock": {
                    "properties": {
                        "plugin_cityPoisonSourceEnabled": False,
                        "plugin_cityBook08NativeConversionEnabled": False,
                    }
                }
            }
            config = build / "maps/baldursGate/config.json"
            config.write_text(json.dumps(initial), encoding="utf8")
            extension = "_game.cp312-win_amd64.pyd"
            (build / "Debug" / extension).write_bytes(b"foreign debug")
            with patch.dict(os.environ, {"GAME_BUILD_DIR": str(build), "GAME_BUILD_CONFIG": "Release"}):
                with self.assertRaises(unittest.SkipTest):
                    with helper(root):
                        pass
                self.assertFalse(any(path.name.startswith("book08-native-fixture-") for path in build.iterdir()))
                (build / extension).write_bytes(b"root fallback")
                (build / "Release" / extension).write_bytes(b"selected release")
                with helper(root) as private:
                    self.assertEqual(b"selected release", (private / extension).read_bytes())
                    self.assertEqual([extension], sorted(path.name for path in private.glob("_game*")))
                (build / "Release" / "_game.other.pyd").write_bytes(b"ambiguous active native")
                with self.assertRaises(AssertionError):
                    with helper(root):
                        pass
            self.assertEqual(initial, json.loads(config.read_text(encoding="utf8")))


if __name__ == "__main__":
    unittest.main()
