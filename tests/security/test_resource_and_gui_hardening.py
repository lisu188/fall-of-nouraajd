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


class ResourceAndGuiHardeningTest(unittest.TestCase):
    def read(self, relative_path):
        return (REPO_ROOT / relative_path).read_text()

    def test_loader_rejects_sparse_tiles_and_bad_tmx_objects(self):
        loader = self.read("src/core/CLoader.cpp")
        save_format = self.read("src/core/CSaveFormat.cpp")

        self.assertIn("MAX_TILESET_ID", loader)
        self.assertIn("MAX_TMX_LAYER_CELLS", loader)
        self.assertIn("parse_int_text", loader)
        self.assertIn("Skipping sparse tile id above limit", loader)
        self.assertIn("Skipping tile layer with invalid dimensions", loader)
        self.assertIn("Skipping malformed map object", loader)
        self.assertIn("save envelope contains invalid mapName", save_format)

    def test_dialogs_fail_closed(self):
        dialog_cpp = self.read("src/object/CDialog.cpp")
        game_py = self.read("res/game.py")
        panel_cpp = self.read("src/gui/panel/CGameDialogPanel.cpp")

        self.assertIn("PY_SAFE_RET_VAL(return override(condition).cast<bool>();, false)", dialog_cpp)
        self.assertIn("return false;", dialog_cpp)
        self.assertIn("_get_public_callback", game_py)
        self.assertIn("type(self).__dict__.get(name)", game_py)
        self.assertIn("return False", game_py)
        self.assertIn("Closing dialog with missing state", panel_cpp)

    def test_gui_and_text_bounds_are_present(self):
        text_manager = self.read("src/gui/CTextManager.cpp")
        texture_cache = self.read("src/gui/CTextureCache.cpp")
        proxy_target = self.read("src/gui/object/CProxyTargetGraphicsObject.cpp")
        console = self.read("src/gui/object/CConsoleGraphicsObject.cpp")

        self.assertIn("MAX_TEXT_TEXTURES", text_manager)
        self.assertIn("MAX_RENDER_TEXT_BYTES", text_manager)
        self.assertIn("MAX_ALPHA_MASK_PIXELS", texture_cache)
        self.assertIn("maxProxyCells", proxy_target)
        self.assertIn("GAME_ENABLE_PYTHON_CONSOLE", console)
        self.assertIn("MAX_CONSOLE_INPUT", console)
        self.assertIn("MAX_CONSOLE_HISTORY", console)

    def test_pathfinding_rng_and_minimap_are_bounded(self):
        pathfinder = self.read("src/core/CPathFinder.cpp")
        controller = self.read("src/core/CController.cpp")
        rng = self.read("src/handler/CRngHandler.cpp")
        minimap = self.read("src/gui/object/CMinimapGraphicsObject.cpp")

        self.assertIn("MAX_PATHFINDER_VISITED", pathfinder)
        self.assertIn("MAX_PATH_DUMP_PIXELS", pathfinder)
        self.assertIn("MAX_FLOW_FIELD_CELLS", controller)
        self.assertIn("MAX_RANDOM_VALUE", rng)
        self.assertIn("MAX_MINIMAP_DEFAULT_CELLS", minimap)

    def test_ownership_cycles_are_weak_and_overrides_release(self):
        game_object_h = self.read("src/object/CGameObject.h")
        animation_h = self.read("src/gui/CAnimation.h")
        overrides = self.read("src/core/CPythonOverrides.h")
        game_object_cpp = self.read("src/object/CGameObject.cpp")

        self.assertIn("std::weak_ptr<CGame> game;", game_object_h)
        self.assertIn("std::weak_ptr<CGameObject> object;", animation_h)
        self.assertIn("std::shared_ptr<CGameObject> ownedObject;", animation_h)
        self.assertIn("inline void release", overrides)
        self.assertIn("PyGILState_Check()", overrides)
        self.assertIn("CPythonOverrides::release(this)", game_object_cpp)

    def test_resource_plugin_exits_and_trade_totals_are_guarded(self):
        object_plugin = self.read("res/plugins/object.py")
        trade_panel = self.read("src/gui/panel/CGameTradePanel.cpp")
        market = self.read("src/object/CMarket.cpp")

        self.assertIn("target = self.getMap().getObjectByName(exit)", object_plugin)
        self.assertIn("return target if self.getMap().canStep(target) else None", object_plugin)
        self.assertIn("market->getBuyCost", trade_panel)
        self.assertIn("market->getSellCost", trade_panel)
        self.assertIn("if (!cre || !item", market)


if __name__ == "__main__":
    unittest.main()
