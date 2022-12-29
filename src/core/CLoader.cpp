/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2021  Andrzej Lis

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
#include "gui/object/CMapGraphicsObject.h"
#include "core/CLoader.h"
#include "core/CJsonUtil.h"
#include "gui/CGui.h"
#include "core/CTypes.h"
#include "handler/CRngHandler.h"
#include "core/CController.h"
#include "object/CCreature.h"
#include "object/CPlayer.h"
#include <rdg.h>

#include <utility>

void CMapLoader::loadFromTmx(const std::shared_ptr<CMap> &map, const std::shared_ptr<json> &mapc) {
    if (mapc) {
        const json &mapProperties = (*mapc)["properties"];
        const json &mapLayers = (*mapc)["layers"];
        map->entryx = vstd::to_int(mapProperties.count("x") ? mapProperties["x"].get<std::string>() : "0").first;
        map->entryy = vstd::to_int(mapProperties.count("y") ? mapProperties["y"].get<std::string>() : "0").first;
        map->entryz = vstd::to_int(mapProperties.count("z") ? mapProperties["z"].get<std::string>() : "0").first;
        const json &tileset = (*mapc)["tilesets"][0]["tileproperties"];
        for (const auto &layer: mapLayers) {
            if (vstd::string_equals(layer["type"].get<std::string>(), "tilelayer")) {
                handleTileLayer(map, tileset, layer);
            }
        }
        for (const auto &layer: mapLayers) {
            if (vstd::string_equals(layer["type"].get<std::string>(), "objectgroup")) {
                handleObjectLayer(map, layer);
            }
        }
    }
}

std::set<std::string> getConfigPaths(const std::string &mapName) {
    return CUtil::findFiles("maps/" + mapName, [](auto path) {
        return vstd::ends_with(path, ".json") && !vstd::ends_with(path, "map.json");
    });
}

std::string getScriptPath(std::string mapName) {
    std::string path = vstd::join({"maps/", std::move(mapName)}, "");
    return vstd::join({path, "/script.py"}, "");
}

std::string getMapPath(std::string mapName) {
    std::string path = vstd::join({"maps/", std::move(mapName)}, "");
    return vstd::join({path, "/map.json"}, "");
}

std::shared_ptr<CMap> CMapLoader::loadNewMap(const std::shared_ptr<CGame> &game, const std::string &mapName) {
    std::shared_ptr<CMap> map = game->getObjectHandler()->createObject<CMap>(game, "CMap");
    game->setMap(map);
    game->getObjectHandler()->registerConfig(getConfigPaths(mapName));
    CPluginLoader::loadPlugin(game, getScriptPath(mapName));
    std::shared_ptr<json> mapc = CConfigurationProvider::getConfig(getMapPath(mapName));
    loadFromTmx(map, mapc);
    map->setMapName(mapName);
    return map;
}

std::shared_ptr<CMap> CMapLoader::loadSavedMap(const std::shared_ptr<CGame> &game, const std::string &name) {
    std::string path = "save/" + name + ".json";
    std::shared_ptr<json> save = CConfigurationProvider::getConfig(path);
    auto mapName = (*save)["properties"]["mapName"].get<std::string>();

    game->getObjectHandler()->registerConfig(getConfigPaths(mapName));
    CPluginLoader::loadPlugin(game, getScriptPath(mapName));
    game->getObjectHandler()->registerConfig(getConfigPaths(mapName));//TODO: duplicate?

    game->getObjectHandler()->registerConfig(name, save);

    std::shared_ptr<CMap> map = game->getObjectHandler()->createObject<CMap>(game, name);

    return map;
}

std::shared_ptr<CMap> CMapLoader::loadNewMapWithPlayer(const std::shared_ptr<CGame> &game, const std::string &name,
                                                       std::string player) {
    std::shared_ptr<CMap> map = loadNewMap(game, name);
    std::shared_ptr<CPlayer> ptr = createPlayer(game, player);
    map->setPlayer(ptr);


    return map;
}

//TODO: move to map, set player as well as triggers
std::shared_ptr<CPlayer> CMapLoader::createPlayer(const std::shared_ptr<CGame> &game, std::string &player) {
    auto ptr = game->createObject<CPlayer>(std::move(player));
    return ptr;
}

std::shared_ptr<CMap> CMapLoader::loadRandomMapWithPlayer(const std::shared_ptr<CGame> &game, std::string player) {
    std::shared_ptr<CMap> map = CRandomMapGenerator::loadRandomMap(game);
    std::shared_ptr<CPlayer> ptr = createPlayer(game, player);
    map->setPlayer(ptr);
    return map;
}

void CMapLoader::save(const std::shared_ptr<CMap> &map, const std::string &name) {
    CResourcesProvider::getInstance()->save(vstd::join({"save/", name, ".json"}, ""), JSONIFY_STYLED(map));
}

void CMapLoader::handleTileLayer(const std::shared_ptr<CMap> &map, const json &tileset, const json &layer) {
    const json &layerProperties = layer["properties"];
    int level = vstd::to_int(layerProperties["level"].get<std::string>()).first;
    map->defaultTiles[level] = layerProperties["default"].get<std::string>();
    map->boundaries[level] =
            std::make_pair(vstd::to_int(layerProperties["xBound"].get<std::string>()).first,
                           vstd::to_int(layerProperties["yBound"].get<std::string>()).first);

    int yLayer = layer["width"].get<int>();
    int xLayer = layer["height"].get<int>();

    for (int y = 0; y < yLayer; ++y) {
        for (int x = 0; x < xLayer; ++x) {
            int id = layer["data"][x + y * xLayer].get<int>();
            if (id == 0) {
                continue;
            }
            id--;
            std::string tileId = std::to_string(id);
            auto tileType = tileset[tileId.c_str()]["type"].get<std::string>();
            map->addTile(map->getGame()->createObject<CTile>(tileType), x, y, level);
        }
    }
}

void CMapLoader::handleObjectLayer(const std::shared_ptr<CMap> &map, const json &layer) {
    int level = vstd::to_int(layer["properties"]["level"].get<std::string>()).first;
    const json &objects = layer["objects"];
    for (const auto &object: objects) {
        auto objectType = object["type"].get<std::string>();
        auto objectName = object["name"].get<std::string>();

        int xPos = object["x"].get<int>() / object["width"].get<int>();
        int yPos = object["y"].get<int>() / object["height"].get<int>();
        auto mapObject = map->getGame()->createObject<CMapObject>(objectType);
        if (mapObject == nullptr) {
            vstd::logger::debug("Failed to load object:", objectType, objectName);
            continue;
        }
        if (!vstd::is_empty(objectName)) {
            mapObject->setName(objectName);
        }
        map->addObject(mapObject);
        const json &objectProperties = object.count("properties") ? object["properties"] : json();
        for (auto [key, value]: objectProperties.items()) {
            CSerialization::setProperty(mapObject, key, CJsonUtil::clone(value));
        }
        mapObject->moveTo(xPos, yPos, level);
        vstd::logger::debug("Loaded object:", mapObject->to_string());
    }
}

std::shared_ptr<CMap> CRandomMapGenerator::loadRandomMap(const std::shared_ptr<CGame> &game) {
    auto map = CMapLoader::loadNewMap(game, "");
    auto options = rdg<>::Options();

    options.n_rows = 555;
    options.n_cols = 555;
    options.corridor_layout = rdg<>::BENT;

    auto dungeon = rdg<>::create_dungeon(options);
    auto container = dungeon.getStairs();
    auto stairs = vstd::any(container);

    map->entryx = stairs.row;
    map->entryy = stairs.col;
    map->entryz = 0;

    generateTiles(map, dungeon);

    std::map<int, rdg<>::Room> rooms = dungeon.getRooms();

    generateEncounters(game, map, rooms);

    vstd::random_element(rooms).first;
    vstd::random_element(rooms).first;


    return map;
}

void CRandomMapGenerator::generateEncounters(const std::shared_ptr<CGame> &game, std::shared_ptr<CMap> &map,
                                             std::map<int, rdg<>::Room> &rooms) {
    for (const auto room: rooms | boost::adaptors::map_values) {
        auto roomCoords = Coords(room.row + room.width / 2, room.col + room.height / 2, 0);
        if (roomCoords.getDist(map->getEntry()) > 5) {
            for (const auto &creature: game->getRngHandler()->getRandomEncounter(5)) {
                map->addObject(creature, roomCoords);
            }
        }
    }
}

void CRandomMapGenerator::generateTiles(std::shared_ptr<CMap> &map, rdg<void>::Dungeon &dungeon) {
    for (unsigned int i = 0; i < dungeon.getCells().size(); i++) {
        for (unsigned int j = 0; j < dungeon.getCells()[0].size(); j++) {
            if (dungeon.getCells()[i][j].isOpenspace()) {
                map->addTile(map->getGame()->createObject<CTile>("GroundTile"), i, j, 0);
            } else {
                map->addTile(map->getGame()->createObject<CTile>("MountainTile"), i, j, 0);
            }
        }
    }
}


std::shared_ptr<CGame> CGameLoader::loadGame() {
    std::shared_ptr<CGame> game = std::make_shared<CGame>();
    initObjectHandler(game->getObjectHandler());
    initConfigurations(game->getObjectHandler());
    initScriptHandler(game->getScriptHandler(), game);
    return game;
}

void CGameLoader::startGameWithPlayer(const std::shared_ptr<CGame> &game, const std::string &file, std::string player) {
    game->setMap(CMapLoader::loadNewMapWithPlayer(game, file, std::move(player)));
}

void CGameLoader::startRandomGameWithPlayer(const std::shared_ptr<CGame> &game, std::string player) {
    game->setMap(CMapLoader::loadRandomMapWithPlayer(game, std::move(player)));
}

void CGameLoader::loadSavedGame(const std::shared_ptr<CGame> &game, const std::string &save) {
    game->setMap(CMapLoader::loadSavedMap(game, save));
}

void CGameLoader::startGame(const std::shared_ptr<CGame> &game, const std::string &file) {
    game->setMap(CMapLoader::loadNewMap(game, file));
}

void CGameLoader::changeMap(const std::shared_ptr<CGame> &game, const std::string &name) {
    vstd::call_later([game, name]() {
        //TODO: implement stop processing events here
        vstd::call_when([game]() {
                            return !game->getMap()->isMoving();
                        },
                        [game, name]() {
                            std::shared_ptr<CMap> oldMap = game->getMap();
                            std::shared_ptr<CMap> map = CMapLoader::loadNewMap(game, name);
                            game->setMap(map);
                            std::shared_ptr<CPlayer> player = oldMap->getPlayer();
                            game->getMap()->setPlayer(player);
                            game->getMap()->setTurn(oldMap->getTurn());
                        });
    });
}

void CGameLoader::initConfigurations(const std::shared_ptr<CObjectHandler> &handler) {
    for (const std::string &path: CResourcesProvider::getInstance()->getFiles(CResType::CONFIG)) {
        handler->registerConfig(path);
    }
}

void CGameLoader::initObjectHandler(const std::shared_ptr<CObjectHandler> &handler) {
    for (const auto &it: *CTypes::builders()) {
        handler->registerType(it.first, it.second);
    }
}

void
CGameLoader::initScriptHandler(const std::shared_ptr<CScriptHandler> &handler, const std::shared_ptr<CGame> &game) {
    for (const std::string &script: CResourcesProvider::getInstance()->getFiles(CResType::PLUGIN)) {
        CPluginLoader::loadPlugin(game, script);
    }
}

void CGameLoader::loadGui(const std::shared_ptr<CGame> &game) {
    std::shared_ptr<CGui> gui = game->createObject<CGui>("gui");

    game->setGui(gui);

    vstd::event_loop<>::instance()->registerFrameCallback([game](int time) {
        game->getGui()->render(time);
    });
    vstd::event_loop<>::instance()->registerEventCallback([game](SDL_Event *event) {
        return game->getGui()->event(event);
    });
}

void CPluginLoader::loadPlugin(const std::shared_ptr<CGame> &game, const std::string &path) {
    PY_SAFE(
            std::string code = CResourcesProvider::getInstance()->load(path);
            auto name = game->getScriptHandler()->add_class(code, {"game.CPlugin"});
            game->loadPlugin(
                    game->getScriptHandler()->get_object<std::function<std::shared_ptr<CPlugin>()>>(name));
            game->getScriptHandler()->execute_script(vstd::join({"del", name}, " "));
    )
}

