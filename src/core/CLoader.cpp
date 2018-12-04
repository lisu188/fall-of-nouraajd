#include "gui/object/CStatsGraphicsObject.h"
#include "gui/object/CMapGraphicsObject.h"
#include "core/CLoader.h"
#include "core/CJsonUtil.h"
#include "gui/CGui.h"
#include "core/CTypes.h"
#include "gui/object/CConsoleGraphicsObject.h"

void CMapLoader::loadFromTmx(std::shared_ptr<CMap> map, std::shared_ptr<Value> mapc) {
    const Value &mapProperties = (*mapc)["properties"];
    const Value &mapLayers = (*mapc)["layers"];
    map->entryx = vstd::to_int(mapProperties["x"].asString()).first;
    map->entryy = vstd::to_int(mapProperties["y"].asString()).first;
    map->entryz = vstd::to_int(mapProperties["z"].asString()).first;
    const Value &tileset = (*mapc)["tilesets"][0]["tileproperties"];
    for (unsigned int i = 0; i < mapLayers.size(); i++) {
        const Value &layer = mapLayers[i];
        if (vstd::string_equals(layer["type"].asString(), "tilelayer")) {
            handleTileLayer(map, tileset, layer);
        }
    }
    for (unsigned int i = 0; i < mapLayers.size(); i++) {
        const Value &layer = mapLayers[i];
        if (vstd::string_equals(layer["type"].asString(), "objectgroup")) {
            handleObjectLayer(map, layer);
        }
    }
}

std::string getConfigPath(std::string mapName) {
    std::string path = vstd::join({"maps/", mapName}, "");
    return vstd::join({path, "/config.json"}, "");
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
    game->getObjectHandler()->registerConfig(getConfigPath(mapName));
    CPluginLoader::loadPlugin(game, getScriptPath(mapName));
    std::shared_ptr<Value> mapc = CConfigurationProvider::getConfig(getMapPath(mapName));
    loadFromTmx(map, mapc);
    map->setMapName(mapName);
    return map;
}

std::shared_ptr<CMap> CMapLoader::loadSavedMap(std::shared_ptr<CGame> game, std::string name) {
    std::string path = "save/" + name + ".json";
    std::shared_ptr<Value> save = CConfigurationProvider::getConfig(path);
    std::string mapName = (*save)["properties"]["mapName"].asString();

    game->getObjectHandler()->registerConfig(getConfigPath(mapName));
    CPluginLoader::loadPlugin(game, getScriptPath(mapName));
    game->getObjectHandler()->registerConfig(getConfigPath(mapName));

    game->getObjectHandler()->registerConfig(name, save);

    std::shared_ptr<CMap> map = game->getObjectHandler()->createObject<CMap>(game, name);
    return map;
}

std::shared_ptr<CMap> CMapLoader::loadNewMapWithPlayer(std::shared_ptr<CGame> game, std::string name,
                                                       std::string player) {
    std::shared_ptr<CMap> map = loadNewMap(game, name);
    map->setPlayer(game->createObject<CPlayer>(player));
    return map;
}

void CMapLoader::save(std::shared_ptr<CMap> map, std::string name) {
    CResourcesProvider::getInstance()->save(vstd::join({"save/", name, ".json"}, ""), JSONIFY_STYLED(map));
}

void CMapLoader::handleTileLayer(std::shared_ptr<CMap> map, const Value &tileset, const Value &layer) {
    const Value &layerProperties = layer["properties"];
    int level = vstd::to_int(layerProperties["level"].asString()).first;
    map->defaultTiles[level] = layerProperties["default"].asString();
    map->boundaries[level] =
            std::make_pair(vstd::to_int(layerProperties["xBound"].asString()).first,
                           vstd::to_int(layerProperties["yBound"].asString()).first);

    int yLayer = layer["width"].asInt();
    int xLayer = layer["height"].asInt();

    for (int y = 0; y < yLayer; ++y) {
        for (int x = 0; x < xLayer; ++x) {
            int id = layer["data"][x + y * xLayer].asInt();
            if (id == 0) {
                continue;
            }
            id--;
            std::string tileId = std::to_string(id);
            std::string tileType = tileset[tileId.c_str()]["type"].asString();
            map->addTile(map->getGame()->createObject<CTile>(tileType), x, y, level);
        }
    }
}

void CMapLoader::handleObjectLayer(std::shared_ptr<CMap> map, const Value &layer) {
    int level = vstd::to_int(layer["properties"]["level"].asString()).first;
    const Value &objects = layer["objects"];
    for (unsigned int i = 0; i < objects.size(); i++) {
        const Value &object = objects[i];
        std::string objectType = object["type"].asString();
        std::string objectName = object["name"].asString();

        int xPos = object["x"].asInt() / object["width"].asInt();
        int yPos = object["y"].asInt() / object["height"].asInt();
        auto mapObject = map->getGame()->createObject<CMapObject>(objectType);
        if (mapObject == nullptr) {
            vstd::logger::debug("Failed to load object:", objectType, objectName);
            continue;
        }
        if (!vstd::is_empty(objectName)) {
            mapObject->setName(objectName);
        }
        map->addObject(mapObject);
        const Value &objectProperties = object["properties"];
        for (auto it :objectProperties.getMemberNames()) {
            CSerialization::setProperty(mapObject, it, CJsonUtil::clone(&objectProperties[it]));
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
    for (std::string path : CResourcesProvider::getInstance()->getFiles(CONFIG)) {
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

//TODO: use CObjectHandler
void CGameLoader::loadGui(std::shared_ptr<CGame> game) {
    std::shared_ptr<CGui> gui = std::make_shared<CGui>(game);

    std::shared_ptr<CMapGraphicsObject> mapGraphicsObject = std::make_shared<CMapGraphicsObject>();

    std::shared_ptr<CStatsGraphicsObject> stats = std::make_shared<CStatsGraphicsObject>();
    std::shared_ptr<CConsoleGraphicsObject> console = std::make_shared<CConsoleGraphicsObject>();

    gui->addObject(mapGraphicsObject);
    gui->addObject(stats);
    gui->addObject(console);

    game->setGui(gui);


    vstd::event_loop<>::instance()->registerFrameCallback([gui](int time) {
        gui->render(time);
    });
    vstd::event_loop<>::instance()->registerEventCallback([gui](SDL_Event *event) {
        gui->event(event);
    });
}

void CPluginLoader::loadPlugin(std::shared_ptr<CGame> game, std::string path) {
    std::string code = CResourcesProvider::getInstance()->load(path);
    std::string name = vstd::join({"CLASS", vstd::to_hex_hash(code)}, "");
    //TODO: move name generation to script handler
    game->getScriptHandler()->add_class(name, code, {"game.CPlugin"});
    game->loadPlugin(game->getScriptHandler()->get_object<std::function<std::shared_ptr<CPlugin>()>>(name));
    game->getScriptHandler()->execute_script(vstd::join({"del", name}, " "));
}

