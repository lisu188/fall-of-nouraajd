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


class LayoutScriptEvaluationTest(unittest.TestCase):
    def test_layout_dimensions_do_not_compile_resource_strings_as_python(self):
        layout_cpp = (REPO_ROOT / "src/gui/CLayout.cpp").read_text()

        self.assertNotIn("handler/CScriptHandler.h", layout_cpp)
        self.assertNotIn("call_created_function", layout_cpp)
        self.assertNotRegex(layout_cpp, re.compile(r"getScriptHandler\s*\("))

    def test_invalid_layout_dimensions_fall_back_to_zero(self):
        layout_cpp = (REPO_ROOT / "src/gui/CLayout.cpp").read_text()
        parse_value = re.search(
            r"std::pair<CLayout::TYPE, int> CLayout::parseValue\(std::string value\) \{(?P<body>.*?)\n\}",
            layout_cpp,
            re.DOTALL,
        )

        self.assertIsNotNone(parse_value)
        body = parse_value.group("body")
        self.assertIn('vstd::logger::error("Invalid layout value:", value);', body)
        self.assertIn("return std::make_pair(SIMPLE, 0);", body)
        self.assertNotIn("object->getGame()", body)


if __name__ == "__main__":
    unittest.main()
