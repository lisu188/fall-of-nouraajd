/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
#pragma once

#include "core/CGame.h"
#include "core/CGlobal.h"
#include "core/CMap.h"
#include <rdg.h>
#include <vector>

class CMapLoader {

  public:
    static std::shared_ptr<CMap> loadNewMapWithPlayer(const std::shared_ptr<CGame> &game, const std::string &name,
                                                      std::string player);

    static std::shared_ptr<CMap> loadNewMapWithPlayer(const std::shared_ptr<CGame> &game, const std::string &name,
                                                      std::string player, const std::string &raceId);

    static std::shared_ptr<CMap> loadRandomMapWithPlayer(const std::shared_ptr<CGame> &game, std::string player);

    static std::shared_ptr<CMap> loadRandomMapWithPlayer(const std::shared_ptr<CGame> &game, std::string player,
                                                         const std::string &raceId);

    static std::shared_ptr<CMap> loadNewMap(const std::shared_ptr<CGame> &game, const std::string &name);

    static std::shared_ptr<CMap> loadSavedMap(const std::shared_ptr<CGame> &game, const std::string &name);

    static void save(const std::shared_ptr<CMap> &map, const std::string &name);

    static void loadFromTmx(const std::shared_ptr<CMap> &map, const std::shared_ptr<json> &mapc);

  private:
    static void handleTileLayer(const std::shared_ptr<CMap> &map, const std::vector<std::string> &tileTypes,
                                const json &layer);

    static void handleObjectLayer(const std::shared_ptr<CMap> &map, const json &layer);

    static std::shared_ptr<CPlayer> createPlayer(const std::shared_ptr<CGame> &game, std::string &player,
                                                 const std::string &raceId);
};

class CGameLoader {
  public:
    static std::shared_ptr<CGame> loadGame();

    static void startGameWithPlayer(const std::shared_ptr<CGame> &game, const std::string &file, std::string player);

    static void startGameWithPlayer(const std::shared_ptr<CGame> &game, const std::string &file, std::string player,
                                    const std::string &raceId);

    static void startRandomGameWithPlayer(const std::shared_ptr<CGame> &game, std::string player);

    static void startRandomGameWithPlayer(const std::shared_ptr<CGame> &game, std::string player,
                                          const std::string &raceId);

    static void startGame(const std::shared_ptr<CGame> &game, const std::string &file);

    static void changeMap(const std::shared_ptr<CGame> &game, const std::string &file);

    static void loadGui(const std::shared_ptr<CGame> &game);

    static void loadSavedGame(const std::shared_ptr<CGame> &game, const std::string &save);

  private:
    static void initObjectHandler(const std::shared_ptr<CObjectHandler> &handler);

    static void initConfigurations(const std::shared_ptr<CGame> &game);

    static void initScriptHandler(const std::shared_ptr<CScriptHandler> &handler, const std::shared_ptr<CGame> &game);
};

class CPluginLoader {
  public:
    // Returns whether a Python plugin path is inside the trusted resource plugin roots (under
    // plugins/ or a map's script.py). This is the trust-boundary decision loadPlugin makes before
    // executing any plugin code; it is exposed so the boundary can be tested without a full pybind
    // runtime (the game_core unit-test binary has no _game bindings to execute plugins with).
    static bool isTrustedPluginPath(const std::string &path);

    // Lua counterpart of isTrustedPluginPath: plugins/**.lua only (no map script.lua yet).
    static bool isTrustedLuaPluginPath(const std::string &path);

    static bool loadPlugin(const std::shared_ptr<CGame> &game, const std::string &path);

    static bool loadLuaPlugin(const std::shared_ptr<CGame> &game, const std::string &path);

    static bool loadCppPlugin(const std::shared_ptr<CGame> &game, const std::string &type);

    static bool loadDynamicPlugin(const std::shared_ptr<CGame> &game, const std::string &library,
                                  const std::string &entry = "game_plugin_load_v2");

    static bool loadGlobalPlugins(const std::shared_ptr<CGame> &game);

    static bool loadMapPlugins(const std::shared_ptr<CGame> &game, const std::string &mapName);
};

class CRandomMapGenerator {
  public:
    static std::shared_ptr<CMap> loadRandomMap(const std::shared_ptr<CGame> &game);

  private:
    static void generateTiles(std::shared_ptr<CMap> &map, const rdg::Dungeon &dungeon);

    static void generateEncounters(const std::shared_ptr<CGame> &game, std::shared_ptr<CMap> &map,
                                   const std::vector<rdg::Room> &rooms);
};
