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
        self.assertIn("PyImport_GetModule", self.loader_source)
        self.assertIn('proxy.attr("__builtins__") = build_restricted_plugin_builtins();', self.loader_source)
        self.assertIn("import json", self.game_source)
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
        self.assertNotIn("std::filesystem::exists(candidate)", self.native_runtime_source)

    def test_resource_provider_rejects_absolute_and_parent_traversal_paths(self):
        self.assertIn("isSafeRelativeResourcePath", self.provider_source)
        self.assertIn("resourcePath.is_absolute()", self.provider_source)
        self.assertIn('normalized.rfind("../", 0) == 0', self.provider_source)
        self.assertIn('normalized.find("/../") != std::string::npos', self.provider_source)
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


if __name__ == "__main__":
    unittest.main()
