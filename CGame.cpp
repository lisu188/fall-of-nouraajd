#include "CGame.h"
#include "CUtil.h"
#include "CMap.h"
#include "CThreadUtil.h"
#include "object/CObject.h"
#include "panel/CPanel.h"
#include "handler/CHandler.h"

void CGame::startGame ( QString file ,QString player ) {
    srand ( time ( 0 ) );
    map = new CMap ( this,file );
    map->setPlayer ( map->createObject<CPlayer*> ( player )  );
    CThreadUtil::call_later ( [this]() {
        map->ensureSize();
        map->getGame()->getView()->show();
    } );
}

void CGame::changeMap ( QString file ) {
    CThreadUtil::call_later ( [this,file]() {
        CPlayer *player=map->getPlayer();
        player->setMap ( 0 );
        delete map;
        map=new CMap ( this,file );
        map->setPlayer ( player );
        map->ensureSize();
    } );
}

CGame::CGame ()  {
    initObjectHandler ( objectHandler.get() );
    initScriptHandler ( scriptHandler.get() );
}

CGame::~CGame() {

}

CMap *CGame::getMap() const {
    return map;
}

CGameView *CGame::getView() {
    return dynamic_cast<CGameView*> ( this->views() [0] );
}

void CGame::removeObject ( CGameObject *object ) {
    this->removeItem ( object );
}

void CGame::addObject ( CGameObject *object ) {
    this->addItem ( object );
}

CGuiHandler *CGame::getGuiHandler()   {
    return guiHandler.get ( this );
}

CScriptHandler *CGame::getScriptHandler() {
    return scriptHandler.get();
}

CObjectHandler *CGame::getObjectHandler() {
    return objectHandler.get();
}

void CGame::keyPressEvent ( QKeyEvent *event ) {
    if ( map->isMoving() ) {
        return;
    }
    switch ( event->key() ) {
    case Qt::Key_Up:
        if ( !getGuiHandler()->isAnyPanelVisible() ) {
            map->getPlayer()->setNextMove ( Coords ( 0,-1 ,0 ) );
            map->move();
        }
        break;
    case Qt::Key_Down:
        if ( !getGuiHandler()->isAnyPanelVisible() ) {
            map->getPlayer()->setNextMove ( Coords ( 0,1,0 ) );
            map->move();
        }
        break;
    case Qt::Key_Left:
        if ( !getGuiHandler()->isAnyPanelVisible() ) {
            map->getPlayer()->setNextMove ( Coords ( -1,0,0 ) );
            map->move();
        }
        break;
    case Qt::Key_Right:
        if ( !getGuiHandler()->isAnyPanelVisible() ) {
            map->getPlayer()->setNextMove ( Coords ( 1,0,0 ) );
            map->move();
        }
        break;
    case Qt::Key_Space:
        if ( !getGuiHandler()->isAnyPanelVisible() ) {
            map->getPlayer()->setNextMove ( Coords ( 0,0,0 ) );
            map->move();
        }
        break;
    case Qt::Key_I:
        getGuiHandler()->flipPanel ( "CCharPanel" );
        break;
    case Qt::Key_S:
        scriptWindow.get ( this )->setVisible ( true );
        break;
    }
}

void CGame::initObjectHandler ( CObjectHandler *handler ) {
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
    for ( QString path : CResourcesProvider::getInstance()->getFiles ( CONFIG ) ) {
        handler->registerConfig ( path );
    }
}

void CGame::initScriptHandler ( CScriptHandler *handler ) {
    for ( QString script:CResourcesProvider::getInstance()->getFiles ( CResType::SCRIPT ) ) {
        QString modName=QFileInfo ( script ).baseName();
        handler->import ( modName );
        handler->callFunction ( modName+".load",this );
    }
}





