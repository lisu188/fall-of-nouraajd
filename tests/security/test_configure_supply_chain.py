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


class ConfigureSupplyChainTest(unittest.TestCase):
    def test_linux_configure_uses_os_pybind11_package(self):
        configure_script = (REPO_ROOT / "configure.sh").read_text()

        self.assertIn("pybind11-dev", configure_script)
        self.assertNotRegex(configure_script, re.compile(r"python3\s+-m\s+pip\s+install[^\n]*\bpybind11\b"))
        self.assertIn("dpkg-query -L pybind11-dev", configure_script)
        self.assertIn("pybind11Config.cmake was not found in the pybind11-dev package", configure_script)
        self.assertIn('-Dpybind11_DIR="${PYBIND11_DIR}"', configure_script)
        self.assertNotIn("python3 -m pybind11 --cmakedir", configure_script)

    def test_cmake_does_not_auto_load_pybind11_python_package(self):
        cmake_lists = (REPO_ROOT / "CMakeLists.txt").read_text()

        self.assertIn("find_package(pybind11 CONFIG REQUIRED)", cmake_lists)
        self.assertNotIn("COMMAND ${Python3_EXECUTABLE} -m pybind11 --cmakedir", cmake_lists)
        self.assertNotIn("list(APPEND CMAKE_PREFIX_PATH ${pybind11_cmake_dir})", cmake_lists)


if __name__ == "__main__":
    unittest.main()
