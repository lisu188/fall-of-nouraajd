# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Source guard for the HTTP modal lifetime fix; native execution remains separate."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def guiWaitSource(source):
    start = source.index("template <typename T> T runGuiTask(")
    opening = source.index("{", start)
    depth = 1
    for index in range(opening + 1, len(source)):
        depth += (source[index] == "{") - (source[index] == "}")
        if not depth:
            return source[start : index + 1]
    raise AssertionError("Synchronous GUI wait function is incomplete")


class McpNativeUiOwnershipSourceTest(unittest.TestCase):
    def testSynchronousGuiWaitDropsItsTemporaryGameBeforeBlocking(self):
        source = guiWaitSource((ROOT / "src/handler/CGuiHandler.cpp").read_text(encoding="utf-8"))
        self.assertRegex(source, r"runGuiTask\(std::shared_ptr<CGame> game,")
        mode = re.search(r"const auto (\w+) = game->getGui\(\) \?", source)
        self.assertIsNotNone(mode, "Capture the frame mode while the game is still alive")
        spawn = source.index("game->getContext()->spawnTask(")
        release = source.index("game.reset();")
        wait = source.index("game_async::wait(handle, " + mode.group(1) + ")")
        self.assertLess(mode.start(), spawn)
        self.assertLess(spawn, release)
        self.assertLess(release, wait)
        self.assertNotIn("game->", source[release:])

    def testSynchronousCancellationKeepsTheExistingNeutralResultContract(self):
        source = guiWaitSource((ROOT / "src/handler/CGuiHandler.cpp").read_text(encoding="utf-8"))
        self.assertIn("catch (const vstd::task_cancelled &)", source)
        self.assertIn("if constexpr (!std::is_void_v<T>)", source)
        self.assertIn("return T{};", source)


if __name__ == "__main__":
    unittest.main()
