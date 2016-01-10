#pragma once

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

