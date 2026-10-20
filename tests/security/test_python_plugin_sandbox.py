#!/usr/bin/env python3
# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class PythonPluginSandboxTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader_source = (REPO_ROOT / "src" / "core" / "CLoader.cpp").read_text()
        cls.native_runtime_source = (REPO_ROOT / "src" / "plugin" / "CNativePluginRuntime.cpp").read_text()
        cls.save_format_source = (REPO_ROOT / "src" / "core" / "CSaveFormat.cpp").read_text()
        cls.provider_source = (REPO_ROOT / "src" / "core" / "CProvider.cpp").read_text()
        cls.game_source = (REPO_ROOT / "res" / "game.py").read_text()

    def test_python_plugins_do_not_receive_full_builtins(self):
        self.assertIn("build_restricted_plugin_builtins", self.loader_source)
        self.assertIn("PyEval_GetBuiltins", self.loader_source)
        self.assertIn('plugin_namespace["__builtins__"] = build_restricted_plugin_builtins();', self.loader_source)
        self.assertNotIn('plugin_namespace["__builtins__"] = pybind11::module::import("builtins")', self.loader_source)
        self.assertNotIn('pybind11::module_::import("builtins")', self.loader_source)
        self.assertNotIn('safeBuiltins[pybind11::str("open")]', self.loader_source)
        self.assertNotIn('safeBuiltins[pybind11::str("eval")]', self.loader_source)
        self.assertNotIn('safeBuiltins[pybind11::str("exec")]', self.loader_source)

    def test_python_plugins_can_only_import_allowlisted_modules(self):
        self.assertIn("restricted_plugin_import", self.loader_source)
        self.assertIn('safeBuiltins["__import__"] = pybind11::reinterpret_steal<pybind11::object>', self.loader_source)
        self.assertIn("PyCFunction_New(&importMethod, nullptr)", self.loader_source)
        self.assertIn('std::string(name) == "game" || std::string(name) == "json"', self.loader_source)
        self.assertIn("Python resource plugins may only import the game and json modules", self.loader_source)

    def test_allowlisted_imports_return_safe_proxy_modules(self):
        self.assertIn("build_safe_proxy_module", self.loader_source)
        self.assertIn("build_safe_json_proxy_module", self.loader_source)
        self.assertIn("is_unsafe_proxy_value", self.loader_source)
        self.assertIn("PyModule_Check(value.ptr())", self.loader_source)
        self.assertIn("clone_python_function", self.loader_source)
        self.assertIn("PyFunction_NewWithQualName", self.loader_source)
        self.assertNotIn("PyFunction_GET_QUALNAME", self.loader_source)
        self.assertIn("wrap_helper_function", self.loader_source)
        self.assertIn("clear_proxy_exception_frames", self.loader_source)
        self.assertRegex(
            self.loader_source,
            r'PyErr_NewException\(\s*"json.JSONDecodeError",\s*PyExc_ValueError,\s*nullptr\)',
        )
        self.assertIn('proxy.attr("__builtins__") = build_restricted_plugin_builtins();', self.loader_source)
        self.assertIn("import json", self.game_source)
        self.assertRegex(
            self.loader_source,
            r'proxy\.attr\("loads"\)\s*=\s*pybind11::reinterpret_steal<pybind11::object>',
        )
        self.assertNotIn('proxy.attr("JSONDecoder")', self.loader_source)
        self.assertNotIn('proxy.attr("JSONDecodeError") = pybind11::module_', self.loader_source)
        self.assertNotIn("PyImport_ImportModuleLevelObject", self.loader_source)

    def test_plugin_and_map_paths_are_validated_before_loading(self):
        self.assertIn("is_allowed_python_plugin_path", self.loader_source)
        self.assertIn("Rejected Python plugin outside trusted resource plugin paths", self.loader_source)
        self.assertIn("isValidMapName", self.save_format_source)
        self.assertIn("CSaveFormat::isValidMapName", self.loader_source)
        self.assertIn("Rejected invalid map name while loading plugins", self.loader_source)
        self.assertIn("Rejected invalid map name while resolving map", self.loader_source)

    def test_dynamic_plugins_are_limited_to_packaged_native_resources(self):
        self.assertIn("is_allowed_dynamic_library_path", self.native_runtime_source)
        self.assertIn('"plugins/native/"', self.native_runtime_source)
        self.assertIn("Rejected dynamic C++ plugin outside packaged native plugin paths", self.native_runtime_source)
        self.assertIn("getPathFromBaseSearchPath(candidate)", self.native_runtime_source)
        self.assertNotIn("resourcesProvider->getPath(candidate)", self.native_runtime_source)
        self.assertIn("Trusted resources such as native plugin libraries", self.provider_source)
        self.assertNotIn("std::filesystem::exists(candidate)", self.native_runtime_source)

    def test_resource_provider_rejects_absolute_and_parent_traversal_paths(self):
        self.assertIn("isSafeRelativeResourcePath", self.provider_source)
        self.assertIn("resourcePath.is_absolute()", self.provider_source)
        self.assertIn('normalized.starts_with("../")', self.provider_source)
        self.assertIn('normalized.contains("/../")', self.provider_source)
        self.assertIn("Rejected unsafe resource path", self.provider_source)

    def test_trust_boundary_model_is_documented(self):
        doc = REPO_ROOT / "docs" / "design" / "plugin_trust_boundary.md"
        self.assertTrue(doc.exists(), "trust boundary design doc must exist")
        text = doc.read_text()
        self.assertIn("authored repository content", text.lower())
        self.assertIn("isWithinResourceRoot", text)
        self.assertIn("is_allowed_python_plugin_path", text)

    def test_crafting_plugin_uses_resource_provider_instead_of_filesystem_paths(self):
        crafting_source = (REPO_ROOT / "res" / "plugins" / "crafting.py").read_text()
        self.assertNotIn("from pathlib import Path", crafting_source)
        self.assertNotIn("path.read_text", crafting_source)
        self.assertIn('game.CResourcesProvider.getInstance().load("config/" + filename)', crafting_source)


class PythonPluginSandboxRuntimeTest(unittest.TestCase):
    def testRestrictedPostedCampaignFlowsPreserveTheImportBoundary(self):
        from tests.test_python_callback_lifecycle import PythonCallbackLifecycleTest

        child = PythonCallbackLifecycleTest(methodName="runTest")
        output = child.runChild(
            r"""
            from pathlib import Path
            import tempfile

            plugin_source = "\n".join([
                "import game",
                "def rejectPrivateImports():",
                "    for name in ('ui', 'os'):",
                "        try:",
                "            __import__(name)",
                "        except Exception as error:",
                "            assert 'may only import' in str(error)",
                "        else:",
                "            raise RuntimeError('restricted import unexpectedly succeeded: ' + name)",
                "def load(_unused, owner):",
                "    rejectPrivateImports()",
                "    for name in ('prepareCompletion', 'complete_scenarioFlow', 'retryPendingFlow'):",
                "        helper = getattr(game.campaign, name)",
                "        assert callable(helper)",
                "        assert not hasattr(helper, '__globals__')",
                "        assert not hasattr(helper, '__wrapped__')",
                "        try:",
                "            helper(None)",
                "        except TypeError:",
                "            pass",
                "        else:",
                "            raise RuntimeError('campaign helper accepted a non-native game')",
                "    assert game.campaign.prepareCompletion(owner, 'sandbox') is None",
                "    def callback():",
                "        rejectPrivateImports()",
                "        flows = (game.campaign.complete_scenarioFlow(owner, 'sandbox'),",
                "                 game.campaign.retryPendingFlow(owner))",
                "        for flow in flows:",
                "            for attribute in ('gi_frame', 'gi_code', '__globals__', '__wrapped__'):",
                "                assert not hasattr(flow, attribute)",
                "            for name in ('send', 'throw', 'close'):",
                "                method = getattr(flow, name)",
                "                assert callable(method)",
                "                namespace = getattr(method, '__globals__', {})",
                "                assert 'open' not in namespace.get('__builtins__', {})",
                "            yield from flow",
                "        rejectPrivateImports()",
                "        owner.getMap().getPlayer().addGold(7)",
                "        owner.setBoolProperty('restrictedPostedFlowRan', True)",
                "    owner.post(callback)",
                "    owner.setBoolProperty('restrictedPostedFlowQueued', True)",
            ])
            owners = []
            try:
                for cancel_before_pump in (False, True):
                    owner = game.CGameLoader.loadGame()
                    owners.append(owner)
                    game.CGameLoader.startGameWithPlayer(owner, 'empty', 'Warrior')
                    player = owner.getMap().getPlayer()
                    gold_before = player.getGold()
                    resources = owner.getResourcesProvider()
                    resource_root = Path(resources.getPath('config/items.json')).parent.parent
                    with tempfile.TemporaryDirectory(prefix='sandbox-flow-', dir=resource_root / 'maps') as temporary:
                        plugin = Path(temporary) / 'script.py'
                        plugin.write_text(plugin_source, encoding='utf-8')
                        assert game.CPluginLoader.loadPlugin(owner, plugin.relative_to(resource_root).as_posix()), (
                            'the restricted map callback must create its native-owned flow')
                        assert owner.getBoolProperty('restrictedPostedFlowQueued')
                        assert not owner.getBoolProperty('restrictedPostedFlowRan')
                        if cancel_before_pump:
                            owner.getContext().shutdown()
                        for _ in range(8):
                            loop.run()
                        assert owner.getBoolProperty('restrictedPostedFlowRan') is (not cancel_before_pump)
                        assert player.getGold() == gold_before + (0 if cancel_before_pump else 7)
                        owner.getContext().shutdown()
                print('restricted posted flows execute or cancel without exposing trusted imports', flush=True)
            finally:
                for owner in reversed(owners):
                    owner.getContext().shutdown()
            """,
            timeout_seconds=20,
        )
        self.assertIn("restricted posted flows execute or cancel without exposing trusted imports", output)


if __name__ == "__main__":
    unittest.main()
