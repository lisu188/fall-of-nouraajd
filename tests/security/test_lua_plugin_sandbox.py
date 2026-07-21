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
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class LuaPluginSandboxTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader_source = (REPO_ROOT / "src" / "core" / "CLoader.cpp").read_text()
        cls.lua_handler_source = (REPO_ROOT / "src" / "handler" / "CLuaHandler.cpp").read_text()

    def test_lua_plugins_run_in_an_allowlisted_environment(self):
        self.assertIn("build_lua_sandbox_env", self.lua_handler_source)
        self.assertNotIn("luaL_openlibs", self.lua_handler_source)
        for closed_library in ("luaopen_io", "luaopen_os", "luaopen_package", "luaopen_debug", "luaopen_coroutine"):
            self.assertNotIn(closed_library, self.lua_handler_source)
        self.assertIn('copy_allowlisted_library(L, envIndex, "math", {"randomseed"});', self.lua_handler_source)
        self.assertIn('copy_allowlisted_library(L, envIndex, "string", {"dump"});', self.lua_handler_source)

    def test_lua_plugins_cannot_load_precompiled_bytecode(self):
        self.assertIn("luaL_loadbufferx", self.lua_handler_source)
        self.assertIn('"t"', self.lua_handler_source)
        self.assertNotIn('"bt"', self.lua_handler_source)

    def test_lua_string_dump_is_removed_from_the_method_metatable(self):
        self.assertIn('lua_setfield(luaState, -2, "dump");', self.lua_handler_source)

    def test_lua_plugin_paths_are_validated_before_loading(self):
        self.assertIn("is_allowed_lua_plugin_path", self.loader_source)
        self.assertIn("Rejected Lua plugin outside trusted resource plugin paths", self.loader_source)
        self.assertIn("isTrustedLuaPluginPath", self.loader_source)

    def test_trust_boundary_model_documents_lua(self):
        doc = REPO_ROOT / "docs" / "design" / "plugin_trust_boundary.md"
        self.assertTrue(doc.exists(), "trust boundary design doc must exist")
        text = doc.read_text()
        self.assertIn("is_allowed_lua_plugin_path", text)
        self.assertIn("build_lua_sandbox_env", text)


if __name__ == "__main__":
    unittest.main()
