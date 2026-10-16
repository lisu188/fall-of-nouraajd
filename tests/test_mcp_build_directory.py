# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import unittest
from unittest.mock import patch

import mcp


class McpBuildDirectoryTest(unittest.TestCase):
    def testEnvironmentControlsDefault(self):
        with patch.dict(os.environ, {"GAME_BUILD_DIR": "build with spaces"}), patch.object(mcp.sys, "argv", ["mcp.py"]):
            self.assertEqual("build with spaces", mcp.parse_args().build_dir)

    def testCommandLineOverridesEnvironment(self):
        with (
            patch.dict(os.environ, {"GAME_BUILD_DIR": "environment-build"}),
            patch.object(mcp.sys, "argv", ["mcp.py", "--build-dir", "explicit-build"]),
        ):
            self.assertEqual("explicit-build", mcp.parse_args().build_dir)

    def testFreshPlatformDefault(self):
        for platform, expected in (("nt", "cmake-build-clangcl20-release"), ("posix", "cmake-build-gcc15-release")):
            with (
                self.subTest(platform=platform),
                patch.dict(os.environ, {"GAME_BUILD_DIR": ""}),
                patch.object(mcp.os, "name", platform),
                patch.object(mcp.sys, "argv", ["mcp.py"]),
            ):
                self.assertEqual(expected, mcp.parse_args().build_dir)


if __name__ == "__main__":
    unittest.main()
