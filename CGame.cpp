#include "CGame.h"
#include "CUtil.h"
#include "CMap.h"
#include "CThreadUtil.h"
#include "gui/CGui.h"
#include "object/CObject.h"
#include "panel/CPanel.h"
#include "handler/CHandler.h"

void CGame::startGame ( QString file ,QString player ) {
    srand ( time ( 0 ) );
    map = new CMap ( this,file );
    map->setPlayer ( map->getObjectHandler()->createObject<CPlayer*> ( player )  );
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

CGame::CGame ( QObject *parent ) :QGraphicsScene ( parent ) {

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

CConfigHandler *CGame::getConfigHandler()
{
    return configHandler.get(convert<std::set<QString>>(CResourcesProvider::getInstance()->getFiles ( CONFIG )));
}

CGuiHandler *CGame::getGuiHandler()   {
    return guiHandler.get ( this );
}

CScriptHandler *CGame::getScriptHandler()
{
   return scriptHandler.get();
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
    }
}





