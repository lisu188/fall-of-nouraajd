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


class McpHardeningTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mcp_source = (REPO_ROOT / "mcp.py").read_text()

    def test_engine_exports_are_allowlisted(self):
        self.assertIn("MCP_ALLOWED_EXPORTS", self.mcp_source)
        self.assertIn('"CGameLoader.loadGame"', self.mcp_source)
        self.assertIn('"event_loop.instance"', self.mcp_source)
        self.assertIn("if export_name not in MCP_ALLOWED_EXPORTS", self.mcp_source)
        self.assertIn("if name not in MCP_ALLOWED_EXPORTS", self.mcp_source)

        allowed_block = re.search(r"MCP_ALLOWED_EXPORTS = \{(?P<body>.*?)\n\}", self.mcp_source, re.DOTALL)
        self.assertIsNotNone(allowed_block)
        body = allowed_block.group("body")
        self.assertNotIn("CPluginLoader", body)
        self.assertNotIn("CResourcesProvider", body)
        self.assertNotIn("dumpPaths", body)

    def test_handle_methods_are_allowlisted(self):
        self.assertIn("MCP_ALLOWED_HANDLE_METHODS", self.mcp_source)
        self.assertIn("method not in self._allowed_handle_methods_for(target)", self.mcp_source)
        self.assertIn("allowed_methods = self._allowed_handle_methods_for(value)", self.mcp_source)

        denied_names = ("loadDynamicPlugin", "getPath", "load", "dumpPaths", "addChild", "removeChild", "applyEffects")
        allowed_methods_block = re.search(
            r"MCP_ALLOWED_HANDLE_METHODS = \{(?P<body>.*?)\n\}", self.mcp_source, re.DOTALL
        )
        self.assertIsNotNone(allowed_methods_block)
        body = allowed_methods_block.group("body")
        for name in denied_names:
            self.assertNotIn(name, body)

    def test_creature_archetype_inspection_is_read_only_and_allowlisted(self):
        allowed_methods_block = re.search(
            r"MCP_ALLOWED_HANDLE_METHODS = \{(?P<body>.*?)\n\}", self.mcp_source, re.DOTALL
        )
        self.assertIsNotNone(allowed_methods_block)
        creature_block = re.search(
            r'"CCreature": \{(?P<body>.*?)\n    \}', allowed_methods_block.group("body"), re.DOTALL
        )
        self.assertIsNotNone(creature_block)
        body = creature_block.group("body")

        read_only_inspectors = (
            "getArchetypeRaceId",
            "getArchetypeClassId",
            "getArchetypeRaceLabel",
            "getArchetypeClassLabel",
        )
        for name in read_only_inspectors:
            self.assertIn(f'"{name}"', body)

        mutation_surface = (
            "setArchetypeRaceId",
            "setArchetypeClassId",
            "setArchetypeRaceLabel",
            "setArchetypeClassLabel",
            "setRace",
            "setCreatureClass",
            "getRace",
            "getCreatureClass",
        )
        for name in mutation_surface:
            self.assertNotIn(name, body)

    def test_transport_limits_and_trace_redaction_are_present(self):
        self.assertIn("MAX_MCP_MESSAGE_BYTES = 1024 * 1024", self.mcp_source)
        self.assertIn("MAX_HTTP_SESSIONS", self.mcp_source)
        self.assertIn("MAX_HTTP_STREAMS_PER_SESSION", self.mcp_source)
        self.assertIn("MCP stdio message exceeds 1 MiB limit", self.mcp_source)
        self.assertIn("MCP HTTP message exceeds 1 MiB limit", self.mcp_source)
        self.assertIn("_redact_trace_value", self.mcp_source)
        self.assertIn('return "<redacted>"', self.mcp_source)

    def test_no_content_responses_do_not_force_content_length(self):
        self.assertIn("status not in {HTTPStatus.NO_CONTENT, HTTPStatus.NOT_MODIFIED}", self.mcp_source)


if __name__ == "__main__":
    unittest.main()
