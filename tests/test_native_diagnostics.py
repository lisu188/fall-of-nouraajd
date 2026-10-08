# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


class NativeDiagnosticsRuntimeTest(unittest.TestCase):
    def testFailedNativeTraceOutputRemainsMemoryOnlyInFinalManifest(self):
        from tests.test_python_callback_lifecycle import PythonCallbackLifecycleTest

        child = PythonCallbackLifecycleTest(methodName="runTest")
        output = child.runChild("""
            import game_diagnostics
            import json
            import os
            from pathlib import Path
            import tempfile
            game.configure_playtest_trace(False)
            for key in list(os.environ):
                if key.startswith('GAME_PLAYTEST_TRACE'):
                    os.environ.pop(key)
            with tempfile.TemporaryDirectory(prefix='nouraajd-output-health-') as temporary:
                root = Path(temporary).resolve()
                for fail_at_startup in (True, False):
                    target = root / ('blocked-directory' if fail_at_startup else 'missing-parent/events.jsonl')
                    if fail_at_startup:
                        target.mkdir()
                    os.environ.update(
                        GAME_PLAYTEST_TRACE='1', GAME_PLAYTEST_TRACE_FILE=str(target),
                        GAME_PLAYTEST_TRACE_RETAIN_RECENT='1')
                    session = game_diagnostics.startSession(
                        repo_root=root, build_dir=root, entrypoint='output-health-test', debug=True,
                        debug_dir=root / 'logs')
                    try:
                        assert session.configureTrace(game)
                        initial_status = session.manifest['channels']['gameplay']['status']
                        assert initial_status == ('memory_only' if fail_at_startup else 'active'), initial_status
                        game.record_playtest_trace_json('retained_after_output_failure', '{}')
                        assert game.playtest_trace_enabled()
                        assert not game.playtest_trace_output_available()
                        retained = game.get_playtest_trace_records()
                        assert len(retained) == 1, retained
                        assert json.loads(retained[0])['seq'] == 1, retained
                        session.finish()
                        manifest = json.loads(session.paths['manifest'].read_text(encoding='utf-8'))
                        assert manifest['channels']['gameplay']['status'] == 'memory_only', manifest
                        assert manifest['channels']['gameplay']['path'] == str(target), manifest
                        assert manifest['outcome'] == 'completed', manifest
                        assert game.get_playtest_trace_records() == retained
                    finally:
                        session.close()
                game.configure_playtest_trace(False)
                print('native output failures preserve memory-only manifest and history', flush=True)
            """)
        self.assertIn("native output failures preserve memory-only manifest and history", output)

    def testPreloadedNativeTraceMovesToEachDebugSession(self):
        from tests.test_python_callback_lifecycle import PythonCallbackLifecycleTest

        child = PythonCallbackLifecycleTest(methodName="runTest")
        output = child.runChild("""
            import game_diagnostics
            import json
            import os
            from pathlib import Path
            import tempfile
            game.configure_playtest_trace(False)
            for key in list(os.environ):
                if key.startswith('GAME_PLAYTEST_TRACE'):
                    os.environ.pop(key)
            with tempfile.TemporaryDirectory(prefix='nouraajd-preloaded-trace-') as temporary:
                root = Path(temporary)
                previous_path = None
                for index in range(2):
                    session = game_diagnostics.startSession(
                        repo_root=root, build_dir=root, entrypoint='preloaded-test', debug=True, debug_dir=root / 'logs')
                    try:
                        assert session.configureTrace(game)
                        game.record_playtest_trace_json('preloaded_session', json.dumps({'index': index}))
                        assert session.applyNative(game)
                        assert session.configureTrace(game)
                        game.record_playtest_trace_json('after_sink_restore', '{}')
                        records = [json.loads(line) for line in game.get_playtest_trace_records()]
                        assert [record['seq'] for record in records] == [1, 2], records
                        assert records[0]['index'] == index, records
                        current_path = session.paths['gameplay']
                        disk = [json.loads(line) for line in current_path.read_text(encoding='utf-8').splitlines()]
                        assert disk == records, (disk, records)
                        if previous_path is not None:
                            assert previous_path != current_path
                            earlier = previous_path.read_text(encoding='utf-8')
                            assert json.loads(earlier.splitlines()[0])['index'] == 0, earlier
                        previous_path = current_path
                    finally:
                        session.close()
                game.configure_playtest_trace(False)
                game.set_logger_sink('disabled')
                print('preloaded trace sessions preserve separate ordered evidence', flush=True)
            """)
        self.assertIn("preloaded trace sessions preserve separate ordered evidence", output)

    def testQuestCallbackTracebackPreservesFallback(self):
        from tests.test_python_callback_lifecycle import PythonCallbackLifecycleTest

        child = PythonCallbackLifecycleTest(methodName="runTest")
        output = child.runChild("""
            from pathlib import Path
            import tempfile
            with tempfile.TemporaryDirectory(prefix='nouraajd-callback-log-') as temporary:
                path = Path(temporary) / 'native.log'
                game.set_logger_sink('file', str(path))
                class BrokenQuest(game.CQuest):
                    def getObjective(self):
                        raise RuntimeError('original quest diagnostic failure')
                    def isCompleted(self):
                        raise ValueError('original completion diagnostic failure')
                quest = BrokenQuest()
                quest.objective = 'authored fallback'
                assert game.CQuest.getObjective(quest) == 'authored fallback'
                assert game.CQuest.isCompleted(quest) is False
                game.set_logger_sink('disabled')
                text = path.read_text(encoding='utf-8')
                assert 'RuntimeError' in text and 'original quest diagnostic failure' in text, text
                assert 'ValueError' in text and 'original completion diagnostic failure' in text, text
                assert 'getObjective' in text and 'isCompleted' in text, text
                assert '<string>' in text, text
                print('callback traceback and fallbacks preserved', flush=True)
            """)
        self.assertIn("callback traceback and fallbacks preserved", output)

    def testDialogTracebacksPreserveFailClosedResults(self):
        from tests.test_python_callback_lifecycle import PythonCallbackLifecycleTest

        child = PythonCallbackLifecycleTest(methodName="runTest")
        output = child.runChild("""
            import game as scripting_game
            from pathlib import Path
            import tempfile
            with tempfile.TemporaryDirectory(prefix='nouraajd-dialog-log-') as temporary:
                path = Path(temporary) / 'native.log'
                game.set_logger_sink('file', str(path))
                class BrokenDialog(scripting_game.CDialog):
                    def brokenAction(self):
                        raise RuntimeError('original dialog action failure')
                    def brokenCondition(self):
                        raise ValueError('original dialog condition failure')
                dialog = BrokenDialog()
                assert dialog.invokeAction('brokenAction') is False
                assert dialog.invokeCondition('brokenCondition') is False
                game.set_logger_sink('disabled')
                text = path.read_text(encoding='utf-8')
                assert 'Traceback' in text and 'brokenAction' in text, text
                assert 'original dialog action failure' in text, text
                assert 'brokenCondition' in text and 'original dialog condition failure' in text, text
                print('dialog traceback and fail-closed results preserved', flush=True)
            """)
        self.assertIn("dialog traceback and fail-closed results preserved", output)

    def testResourceDialogTracebacksSurviveRestrictedProxy(self):
        from tests.test_python_callback_lifecycle import PythonCallbackLifecycleTest

        child = PythonCallbackLifecycleTest(methodName="runTest")
        output = child.runChild("""
            from pathlib import Path
            import tempfile
            instance = game.CGameLoader.loadGame()
            resources = instance.getResourcesProvider()
            resource_root = Path(resources.getPath('config/items.json')).parent.parent
            with tempfile.TemporaryDirectory(prefix='diagnostic-proxy-', dir=resource_root / 'maps') as temporary:
                plugin = Path(temporary) / 'script.py'
                plugin.write_text('\\n'.join([
                    'import game',
                    'def load(_unused, context):',
                    '    class BrokenDialog(game.CDialog):',
                    '        def brokenAction(self):',
                    '            raise RuntimeError("resource dialog action traceback")',
                    '        def brokenCondition(self):',
                    '            raise ValueError("resource dialog condition traceback")',
                    '    dialog = BrokenDialog()',
                    '    assert dialog.invokeAction("brokenAction") is False',
                    '    assert dialog.invokeCondition("brokenCondition") is False',
                    '    context.setBoolProperty("diagnosticProxyPassed", True)',
                ]), encoding='utf-8')
                path = Path(temporary) / 'native.log'
                game.set_logger_sink('file', str(path))
                try:
                    assert game.CPluginLoader.loadPlugin(instance, plugin.relative_to(resource_root).as_posix())
                    assert instance.getBoolProperty('diagnosticProxyPassed')
                finally:
                    game.set_logger_sink('disabled')
                text = path.read_text(encoding='utf-8')
                for expected in (
                    'Traceback', '<string>', 'brokenAction', 'brokenCondition',
                    'resource dialog action traceback', 'resource dialog condition traceback',
                ):
                    assert expected in text, text
                assert 'NameError' not in text, text
                print('resource proxy traceback and fallback results preserved', flush=True)
            """)
        self.assertIn("resource proxy traceback and fallback results preserved", output)

    def testDebugMcpSessionRecordsRealPlayerRoute(self):
        import test as harness

        if not any(
            list(path.glob("_game*.pyd")) + list(path.glob("_game*.so"))
            for path in [harness.build_dir, *harness.extension_dirs]
        ):
            self.skipTest("The current _game extension is required for debug MCP validation")
        harness.TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(dir=harness.TEST_OUTPUT_DIR, prefix="debug-mcp-session-"))
        with self.subTest(diagnostics=str(root)):
            command = [
                sys.executable,
                "-B",
                str(harness.REPO_ROOT / "mcp.py"),
                "--stdio",
                "--repo-root",
                str(harness.REPO_ROOT),
                "--build-dir",
                str(harness.build_dir),
                "--debug",
                "--debug-dir",
                str(root),
            ]
            if harness.build_config:
                command.extend(["--build-config", harness.build_config])
            environment = os.environ.copy()
            for key in list(environment):
                if key.startswith("GAME_PLAYTEST_TRACE") or key in {"GAME_DEBUG", "GAME_DEBUG_DIR"}:
                    environment.pop(key)
            environment.update(
                SDL_VIDEODRIVER="dummy",
                SDL_AUDIODRIVER="dummy",
                SDL_RENDER_DRIVER="software",
                LIBGL_ALWAYS_SOFTWARE="1",
            )
            driver = harness.McpServerTest(methodName="runTest")
            process = driver._start_stdio_process(command, env=environment, map_name="multilevel")
            try:
                driver._initialize_stdio_mcp(process)
                session = {"proc": process, "next_request_id": 3}

                def engine(name, *args):
                    return driver._mcp_engine_call(session, name, list(args), timeout=60)

                def call(handle, method, *args):
                    return driver._mcp_handle_call(session, handle, method, list(args), timeout=60)

                instance = engine("CGameLoader.loadGame")
                engine("CGameLoader.startGameWithPlayer", instance, "multilevel", "Warrior")
                world = call(instance, "getMap")
                player = call(world, "getPlayer")
                self.assertIsNone(call(instance, "getGui"))
                loop = engine("event_loop.instance")
                call(loop, "run")
                start_turn = call(world, "getTurn")
                stairs = call(world, "getObjectByName", "stairsUp")
                controller = call(player, "getController")
                call(controller, "setTarget", player, call(stairs, "getCoords"))
                for _ in range(24):
                    call(world, "move")
                    call(loop, "run")
                    if call(world, "getBoolProperty", "used_stairs_up"):
                        break
                self.assertTrue(call(world, "getBoolProperty", "used_stairs_up"))
                self.assertGreater(call(world, "getTurn"), start_turn)
                engine("logger", "debug-session-native-marker")
            finally:
                driver._shutdown_process(process)
            runs = list(root.iterdir())
            self.assertEqual(1, len(runs))
            run = runs[0]
            manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("completed", manifest["outcome"])
            native = (run / "native.log").read_text(encoding="utf-8")
            self.assertIn("debug-session-native-marker", native)
            runtime = (run / "runtime.log").read_text(encoding="utf-8")
            self.assertIn("CGameLoader.startGameWithPlayer", runtime)
            self.assertIn("setTarget", runtime)
            events = [json.loads(line) for line in (run / "gameplay.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertTrue(any(record.get("map") == "multilevel" for record in events), events)
            self.assertTrue(any(record.get("event") == "movement" for record in events), events)
            self.assertEqual(sorted(record["seq"] for record in events), [record["seq"] for record in events])


if __name__ == "__main__":
    unittest.main()
