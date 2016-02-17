#include "core/CLoader.h"

#include "core/CJsonUtil.h"

void CMapLoader::loadFromTmx(std::shared_ptr<CMap> map, std::shared_ptr<Value> mapc) {
    const Value &mapProperties = (*mapc)["properties"];
    const Value &mapLayers = (*mapc)["layers"];
    map->entryx = vstd::to_int(mapProperties["x"].asString()).first;
    map->entryy = vstd::to_int(mapProperties["y"].asString()).first;
    map->entryz = vstd::to_int(mapProperties["z"].asString()).first;
    const Value &tileset = (*mapc)["tilesets"][0]["tileproperties"];
    for (int i=0;i<mapLayers.size();i++) {
        const Value &layer = mapLayers[i];
        if (vstd::string_equals(layer["type"].asString(), "tilelayer")) {
            handleTileLayer(map, tileset, layer);
        }
    }
    for (int i=0;i<mapLayers.size();i++) {
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

void CMapLoader::saveMap(std::shared_ptr<CMap> map, std::string file) {
    std::shared_ptr<Value> _data = std::make_shared<Value>();

    std::shared_ptr<Value> objects = std::make_shared<Value>();
    std::shared_ptr<Value> tiles = std::make_shared<Value>();
    std::shared_ptr<Value> triggers = std::make_shared<Value>();

    map->forObjects([objects](std::shared_ptr<CMapObject> object) {
        (*objects)[object->getName().c_str()] = *(CSerialization::serialize<std::shared_ptr<Value >>(object));
    });

    map->forTiles([tiles](std::shared_ptr<CTile> tile) {
        (*tiles)[tile->getName().c_str()] = *(CSerialization::serialize<std::shared_ptr<Value >>(tile));
    });

    (*_data)["objects"] = *objects;
    (*_data)["tiles"] = *tiles;
    (*_data)["triggers"] = *triggers;

    CResourcesProvider::getInstance()->save(vstd::join({"save/", file}, ""), _data);
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
    for (int i=0;i<objects.size();i++) {
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

#include "core/CTypes.h"

std::shared_ptr<CGame> CGameLoader::loadGame() {
    std::shared_ptr<CGame> game = std::make_shared<CGame>();
    initObjectHandler(game->getObjectHandler());
    initConfigurations(game->getObjectHandler());
    initScriptHandler(game->getScriptHandler(), game);
    return game;
}

void CGameLoader::startGame(std::shared_ptr<CGame> game, std::string file, std::string player) {
    game->setMap(CMapLoader::loadNewMapWithPlayer(game, file, player));
}

void CGameLoader::changeMap(std::shared_ptr<CGame> game, std::string name) {
    vstd::call_later([game, name]() {
        //TODO: implement stop processing events here
        vstd::call_when([game]() {
                            return !game->getMap()->isMoving();
                        },
                        [game, name]() {
                            std::shared_ptr<CPlayer> player = game->getMap()->getPlayer();
                            game->setMap(CMapLoader::loadNewMap(game, name));
                            game->getMap()->setPlayer(player);
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