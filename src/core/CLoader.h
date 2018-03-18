#pragma once

#include "core/CGlobal.h"
#include "core/CMap.h"

class CMapLoader {

public:

    static std::shared_ptr<CMap> loadNewMapWithPlayer(std::shared_ptr<CGame> game, std::string name,
                                                      std::string player);

    static std::shared_ptr<CMap> loadNewMap(std::shared_ptr<CGame> game, std::string name);

    static std::shared_ptr<CMap> loadSavedMap(std::shared_ptr<CGame> game, std::string name);

    static void save(std::shared_ptr<CMap> map, std::string name);

    static void loadFromTmx(std::shared_ptr<CMap> map, std::shared_ptr<Value> mapc);

private:

    static void handleTileLayer(std::shared_ptr<CMap> map, const Value &tileset, const Value &layer);

    static void handleObjectLayer(std::shared_ptr<CMap> map, const Value &layer);

};

#include "core/CGlobal.h"
#include "core/CGame.h"

class CGameLoader {
public:
    static std::shared_ptr<CGame> loadGame();

    static void startGameWithPlayer(std::shared_ptr<CGame> game, std::string file, std::string player);

    static void startGame(std::shared_ptr<CGame> game, std::string file);

    static void changeMap(std::shared_ptr<CGame> game, std::string file);

    static void loadGui(std::shared_ptr<CGame> game);

    static void loadSavedGame(std::shared_ptr<CGame> game, std::string save);
private:
    static void initObjectHandler(std::shared_ptr<CObjectHandler> handler);

    static void initConfigurations(std::shared_ptr<CObjectHandler> handler);

    static void initScriptHandler(std::shared_ptr<CScriptHandler> handler, std::shared_ptr<CGame> game);

};

class CPluginLoader {
public:


    static void loadPlugin(std::shared_ptr<CGame> game, std::string path);
};