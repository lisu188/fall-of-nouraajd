#pragma once
#include "CGlobal.h"
#include "CGame.h"

class CGameLoader {
public:
    static std::shared_ptr<CGame> loadGame();
    static void startGame ( std::shared_ptr<CGame> game, QString file ,QString player );
    static void changeMap ( std::shared_ptr<CGame> game,QString file );
private:
    static void initObjectHandler ( std::shared_ptr<CObjectHandler> handler );
    static void initConfigurations ( std::shared_ptr<CObjectHandler> handler );
    static void initScriptHandler ( std::shared_ptr<CScriptHandler> handler,std::shared_ptr<CGame> game ) ;
};

