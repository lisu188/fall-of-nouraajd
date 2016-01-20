#pragma once

#include "core/CGlobal.h"
#include "core/CMap.h"

class CMapLoader {

public:

    static std::shared_ptr<CMap> loadNewMapWithPlayer(std::shared_ptr<CGame> game, std::string name,
                                                      std::string player);

    static std::shared_ptr<CMap> loadNewMap(std::shared_ptr<CGame> game, std::string name);

    //static std::shared_ptr<CMap> loadSavedMap ( std::shared_ptr<CGame> game, std::string name );//TODO: implement
    static void saveMap(std::shared_ptr<CMap> map, std::string file);

    static void loadFromTmx(std::shared_ptr<CMap> map, std::shared_ptr<Value> mapc);

    void save(std::shared_ptr<Value> data, std::string file);

private:

    static void handleTileLayer(std::shared_ptr<CMap> map, const Value &tileset, const Value &layer);

    static void handleObjectLayer(std::shared_ptr<CMap> map, const Value &layer);
};

#include "core/CGlobal.h"
#include "core/CGame.h"

class CGameLoader {
public:
    static std::shared_ptr<CGame> loadGame();

    static void startGame(std::shared_ptr<CGame> game, std::string file, std::string player);

    static void changeMap(std::shared_ptr<CGame> game, std::string file);

private:
    static void initObjectHandler(std::shared_ptr<CObjectHandler> handler);

    static void initConfigurations(std::shared_ptr<CObjectHandler> handler);

    static void initScriptHandler(std::shared_ptr<CScriptHandler> handler, std::shared_ptr<CGame> game);

};

class CPluginLoader {
public:

    static void load_plugin(std::shared_ptr<CMap> game, std::string path);

    static void load_plugin(std::shared_ptr<CGame> game, std::string path);
};