#include "gui/object/CStatsGraphicsObject.h"
#include "gui/object/CMapGraphicsObject.h"
#include "core/CLoader.h"
#include "core/CEventLoop.h"
#include "core/CJsonUtil.h"
#include "gui/CGui.h"
#include "core/CTypes.h"

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

std::shared_ptr<CMap> CMapLoader::loadNewMap(std::shared_ptr<CGame> game, std::string name) {
    std::shared_ptr<CMap> map = std::make_shared<CMap>(game);
    std::string path = vstd::join({"maps/", name}, "");
    map->getObjectHandler()->registerConfig(vstd::join({path, "/config.json"}, ""));
    CPluginLoader::load_plugin(map, vstd::join({path, "/script.py"}, ""));
    std::shared_ptr<Value> mapc = CConfigurationProvider::getConfig(vstd::join({path, "/map.json"}, ""));
    loadFromTmx(map, mapc);
    return map;
}

//std::shared_ptr<CMap> CMapLoader::loadSavedMap ( std::shared_ptr<CGame> game,std::string name ) {
//  std::shared_ptr<CMap> map=std::make_shared<CMap> ( game );
//  std::string path="save/"+name+".sav";
//  map->getObjectHandler()->registerConfig ( path+"/config.json" );
//  map->getGame()->getScriptHandler()->addModule ( name,path+"/script.py" );
//  map->getGame()->getScriptHandler()->call_function ( name+".load",map );
//  std::shared_ptr<Value> mapc=CConfigurationProvider::getConfig ( path+"/map.json" );
//  loadFromTmx ( map, mapc );
//  return map;
//}

std::shared_ptr<CMap> CMapLoader::loadNewMapWithPlayer(std::shared_ptr<CGame> game, std::string name,
                                                       std::string player) {
    std::shared_ptr<CMap> map = loadNewMap(game, name);
    map->setPlayer(map->createObject<CPlayer>(player));
    return map;
}

void CMapLoader::save(std::shared_ptr<CMap> map, std::string name) {
    CResourcesProvider::getInstance()->save(vstd::join({"save/", name, ".json"}, ""), JSONIFY(map));
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
            map->addTile(map->createObject<CTile>(tileType), x, y, level);
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
        auto mapObject = map->createObject<CMapObject>(objectType);
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
        CPluginLoader::load_plugin(game, script);
    }
}

//TODO:
void CGameLoader::loadGui(std::shared_ptr<CGame> game) {
    std::shared_ptr<CGui> gui = std::make_shared<CGui>(game);

    std::shared_ptr<CMapGraphicsObject> mapGraphicsObject = std::make_shared<CMapGraphicsObject>();

    std::shared_ptr<CStatsGraphicsObject> stats = std::make_shared<CStatsGraphicsObject>();

    gui->addObject(mapGraphicsObject);
    gui->addObject(stats);

    game->setGui(gui);


    CEventLoop::instance()->registerFrameCallback([gui](int time) {
        gui->render(time);
    });
    CEventLoop::instance()->registerEventCallback([gui](SDL_Event *event) {
        gui->event(event);
    });
}

void CPluginLoader::load_plugin(std::shared_ptr<CGame> game, std::string path) {
    std::string code = CResourcesProvider::getInstance()->load(path);
    std::string name = vstd::join({"CLASS", vstd::to_hex_hash(code)}, "");
    game->getScriptHandler()->add_class(name, code, {"game.CPlugin"});
    game->load_plugin(game->getScriptHandler()->get_object<std::function<std::shared_ptr<CPlugin>()>>(name));
    game->getScriptHandler()->execute_script(vstd::join({"del", name}, " "));
}

void CPluginLoader::load_plugin(std::shared_ptr<CMap> map, std::string path) {
    std::string code = CResourcesProvider::getInstance()->load(path);
    std::string name = vstd::join({"CLASS", vstd::to_hex_hash(code)}, "");
    map->getGame()->getScriptHandler()->add_class(name, code, {"game.CMapPlugin"});
    map->load_plugin(
            map->getGame()->getScriptHandler()->get_object<std::function<std::shared_ptr<CMapPlugin>()>>(name));
    map->getGame()->getScriptHandler()->execute_script(vstd::join({"del", name}, " "));
}