/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

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
#include "gui/object/CStatsGraphicsObject.h"
#include "gui/object/CMapGraphicsObject.h"
#include "gui/panel/CGamePanel.h"
#include "core/CLoader.h"
#include "core/CJsonUtil.h"
#include "gui/CGui.h"
#include "core/CTypes.h"

void CMapLoader::loadFromTmx(std::shared_ptr<CMap> map, std::shared_ptr<json> mapc) {
    const json &mapProperties = (*mapc)["properties"];
    const json &mapLayers = (*mapc)["layers"];
    map->entryx = vstd::to_int(mapProperties.count("x") ? mapProperties["x"].get<std::string>() : "0").first;
    map->entryy = vstd::to_int(mapProperties.count("y") ? mapProperties["y"].get<std::string>() : "0").first;
    map->entryz = vstd::to_int(mapProperties.count("z") ? mapProperties["z"].get<std::string>() : "0").first;
    const json &tileset = (*mapc)["tilesets"][0]["tileproperties"];
    for (unsigned int i = 0; i < mapLayers.size(); i++) {
        const json &layer = mapLayers[i];
        if (vstd::string_equals(layer["type"].get<std::string>(), "tilelayer")) {
            handleTileLayer(map, tileset, layer);
        }
    }
    for (unsigned int i = 0; i < mapLayers.size(); i++) {
        const json &layer = mapLayers[i];
        if (vstd::string_equals(layer["type"].get<std::string>(), "objectgroup")) {
            handleObjectLayer(map, layer);
        }
    }
}

std::set<std::string> getConfigPaths(std::string mapName) {
    return CUtil::findFiles("maps/" + mapName, [](auto path) {
        return vstd::ends_with(path, ".json") && !vstd::ends_with(path, "map.json");
    });
}

std::string getScriptPath(std::string mapName) {
    std::string path = vstd::join({"maps/", mapName}, "");
    return vstd::join({path, "/script.py"}, "");
}

std::string getMapPath(std::string mapName) {
    std::string path = vstd::join({"maps/", mapName}, "");
    return vstd::join({path, "/map.json"}, "");
}

std::shared_ptr<CMap> CMapLoader::loadNewMap(std::shared_ptr<CGame> game, std::string mapName) {
    std::shared_ptr<CMap> map = game->getObjectHandler()->createObject<CMap>(game, "CMap");
    game->setMap(map);
    game->getObjectHandler()->registerConfig(getConfigPaths(mapName));
    CPluginLoader::loadPlugin(game, getScriptPath(mapName));
    std::shared_ptr<json> mapc = CConfigurationProvider::getConfig(getMapPath(mapName));
    loadFromTmx(map, mapc);
    map->setMapName(mapName);
    return map;
}

std::shared_ptr<CMap> CMapLoader::loadSavedMap(std::shared_ptr<CGame> game, std::string name) {
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

std::shared_ptr<CMap> CMapLoader::loadNewMapWithPlayer(std::shared_ptr<CGame> game, std::string name,
                                                       std::string player) {
    std::shared_ptr<CMap> map = loadNewMap(game, name);
    auto ptr = game->createObject<CPlayer>(player);
    ptr->setName("player");
    map->setPlayer(ptr);
    return map;
}

void CMapLoader::save(std::shared_ptr<CMap> map, std::string name) {
    CResourcesProvider::getInstance()->save(vstd::join({"save/", name, ".json"}, ""), JSONIFY_STYLED(map));
}

void CMapLoader::handleTileLayer(std::shared_ptr<CMap> map, const json &tileset, const json &layer) {
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
            std::string tileType = tileset[tileId.c_str()]["type"].get<std::string>();
            map->addTile(map->getGame()->createObject<CTile>(tileType), x, y, level);
        }
    }
}

void CMapLoader::handleObjectLayer(std::shared_ptr<CMap> map, const json &layer) {
    int level = vstd::to_int(layer["properties"]["level"].get<std::string>()).first;
    const json &objects = layer["objects"];
    for (unsigned int i = 0; i < objects.size(); i++) {
        const json &object = objects[i];
        std::string objectType = object["type"].get<std::string>();
        std::string objectName = object["name"].get<std::string>();

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
        for (auto[key, value] :objectProperties.items()) {
            CSerialization::setProperty(mapObject, key, CJsonUtil::clone(value));
        }
        mapObject->moveTo(xPos, yPos, level);
        vstd::logger::debug("Loaded object:", mapObject->to_string());
    }
}


std::shared_ptr<CGame> CGameLoader::loadGame() {
    std::shared_ptr<CGame> game = std::make_shared<CGame>();
    initObjectHandler(game->getObjectHandler());
    initConfigurations(game->getObjectHandler());
    initScriptHandler(game->getScriptHandler(), game);
    return game;
}

void CGameLoader::startGameWithPlayer(std::shared_ptr<CGame> game, std::string file, std::string player) {
    game->setMap(CMapLoader::loadNewMapWithPlayer(game, file, player));
}

void CGameLoader::loadSavedGame(std::shared_ptr<CGame> game, std::string save) {
    game->setMap(CMapLoader::loadSavedMap(game, save));
}

void CGameLoader::startGame(std::shared_ptr<CGame> game, std::string file) {
    game->setMap(CMapLoader::loadNewMap(game, file));
}

void CGameLoader::changeMap(std::shared_ptr<CGame> game, std::string name) {
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

void CGameLoader::initConfigurations(std::shared_ptr<CObjectHandler> handler) {
    for (std::string path : CResourcesProvider::getInstance()->getFiles(CResType::CONFIG)) {
        handler->registerConfig(path);
    }
}

void CGameLoader::initObjectHandler(std::shared_ptr<CObjectHandler> handler) {
    for (std::pair<std::string, std::function<std::shared_ptr<CGameObject>() >> it:*CTypes::builders()) {
        handler->registerType(it.first, it.second);
    }
}

void CGameLoader::initScriptHandler(std::shared_ptr<CScriptHandler> handler, std::shared_ptr<CGame> game) {
    for (std::string script:CResourcesProvider::getInstance()->getFiles(CResType::PLUGIN)) {
        CPluginLoader::loadPlugin(game, script);
    }
}

void CGameLoader::loadGui(std::shared_ptr<CGame> game) {
    std::shared_ptr<CGui> gui = game->createObject<CGui>("gui");

    game->setGui(gui);

    vstd::event_loop<>::instance()->registerFrameCallback([game](int time) {
        game->getGui()->render(time);
    });
    vstd::event_loop<>::instance()->registerEventCallback([game](SDL_Event *event) {
        return game->getGui()->event(event);
    });
}

void CPluginLoader::loadPlugin(std::shared_ptr<CGame> game, std::string path) {
    std::string code = CResourcesProvider::getInstance()->load(path);
    auto name = game->getScriptHandler()->add_class(code, {"game.CPlugin"});
    game->loadPlugin(game->getScriptHandler()->get_object<std::function<std::shared_ptr<CPlugin>()>>(name));
    game->getScriptHandler()->execute_script(vstd::join({"del", name}, " "));
}

