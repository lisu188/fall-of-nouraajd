#include "loader/CLoader.h"
#include "loader/CLoader.h"
#include "CThreadUtil.h"

std::shared_ptr<CGame> CGameLoader::loadGame ( std::shared_ptr<CGameView> view ) {
    std::shared_ptr<CGame> game=std::make_shared<CGame> ( view );
    initObjectHandler ( game->getObjectHandler() );
    initConfigurations ( game->getObjectHandler() );
    initScriptHandler ( game->getScriptHandler(),game );
    return game;
}

void CGameLoader::startGame ( std::shared_ptr<CGame> game, QString file, QString player ) {
    game->setMap ( CMapLoader::loadMap ( game,file,player ) );
    CThreadUtil::call_later ( [game]() {
        game->getMap()->ensureSize();
        game->getView()->show();
    } );
}

void CGameLoader::changeMap ( std::shared_ptr<CGame> game, QString name ) {
    CThreadUtil::call_later ( [game,name]() {
        //implement stop processing events here
        CThreadUtil::wait_until ( [game]() {
            return !game->getMap()->isMoving();
        } );
        std::shared_ptr<CPlayer> player=game->getMap()->getPlayer();
        game->setMap ( CMapLoader::loadMap ( game,name ) );
        game->getMap()->setPlayer ( player );
        game->getMap()->ensureSize();
    } );
}

void CGameLoader::initConfigurations ( std::shared_ptr<CObjectHandler> handler ) {
    for ( QString path : CResourcesProvider::getInstance()->getFiles ( CONFIG ) ) {
        handler->registerConfig ( path );
    }
}

void CGameLoader::initObjectHandler ( std::shared_ptr<CObjectHandler> handler ) {
    handler->registerType< CWeapon >();
    handler->registerType< CArmor >();
    handler->registerType< CPotion >();
    handler->registerType< CBuilding >();
    handler->registerType< CItem >();
    handler->registerType< CPlayer >();
    handler->registerType< CMonster >();
    handler->registerType< CTile >();
    handler->registerType< CInteraction >();
    handler->registerType< CSmallWeapon >();
    handler->registerType< CHelmet >();
    handler->registerType< CBoots >();
    handler->registerType< CBelt >();
    handler->registerType< CGloves >();
    handler->registerType< CEvent >();
    handler->registerType< CScroll >();
    handler->registerType< CEffect >();
    handler->registerType< CMarket >();
    handler->registerType< CTrigger >();
    handler->registerType< CQuest >();

}

void CGameLoader::initScriptHandler ( std::shared_ptr<CScriptHandler> handler, std::shared_ptr<CGame> game ) {
    for ( QString script:CResourcesProvider::getInstance()->getFiles ( CResType::SCRIPT ) ) {
        QString modName=QFileInfo ( script ).baseName();
        handler->import ( modName );
        handler->callFunction ( modName+".load",game );
    }
}
