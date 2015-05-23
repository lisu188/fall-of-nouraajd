#include "CGameLoader.h"
#include "CMapLoader.h"
#include "CThreadUtil.h"

std::shared_ptr<CGame> CGameLoader::loadGame() {
    std::shared_ptr<CGame> game=std::make_shared<CGame>();
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
        CPlayer *player=game->getMap()->getPlayer();
        player->setMap ( 0 );
        std::shared_ptr<CMap> map=CMapLoader::loadMap ( game,name );
        map->setPlayer ( player );
        map->ensureSize();
        game->setMap ( map );
    } );
}

void CGameLoader::initConfigurations ( CObjectHandler *handler ) {
    for ( QString path : CResourcesProvider::getInstance()->getFiles ( CONFIG ) ) {
        handler->registerConfig ( path );
    }
}

void CGameLoader::initObjectHandler ( CObjectHandler *handler ) {
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

void CGameLoader::initScriptHandler ( CScriptHandler *handler,std::shared_ptr<CGame> game ) {
    for ( QString script:CResourcesProvider::getInstance()->getFiles ( CResType::SCRIPT ) ) {
        QString modName=QFileInfo ( script ).baseName();
        handler->import ( modName );
        handler->callFunction ( modName+".load",game );
    }
}
