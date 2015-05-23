#include "CGame.h"
#include "CUtil.h"
#include "CMap.h"
#include "CThreadUtil.h"
#include "object/CObject.h"
#include "panel/CPanel.h"
#include "handler/CHandler.h"
#include "CGameLoader.h"

CGame::CGame ()  {

}

void CGame::changeMap ( QString file ) {
    CGameLoader::changeMap ( std::shared_ptr<CGame> ( this ),file );
}

std::shared_ptr<CMap> CGame::getMap() const {
    return map;
}

void CGame::setMap ( std::shared_ptr<CMap> map ) {
    this->map=map;
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
        scriptWindow.get ( std::shared_ptr<CGame> ( this ) )->setVisible ( true );
        break;
    }
}









