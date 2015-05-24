#include "CGame.h"
#include "CUtil.h"
#include "CMap.h"
#include "CThreadUtil.h"
#include "object/CObject.h"
#include "panel/CPanel.h"
#include "handler/CHandler.h"
#include "loader/CLoader.h"

CGame::CGame ()  {

}

CGame::~CGame() {
    for ( QGraphicsItem* it:items() ) {
        removeItem ( it ); //to let shared pointers do their job
    }
}

void CGame::changeMap ( QString file ) {
    CGameLoader::changeMap ( this->ptr(),file );
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

void CGame::removeObject ( std::shared_ptr<CGameObject> object ) {
    this->removeItem ( object.get() );
}

void CGame::addObject ( std::shared_ptr<CGameObject> object ) {
    this->addItem ( object.get() );
}

std::shared_ptr<CGuiHandler> CGame::getGuiHandler()   {
    return guiHandler.get ( this->ptr() );
}

std::shared_ptr<CScriptHandler> CGame::getScriptHandler() {
    return scriptHandler.get();
}

std::shared_ptr<CObjectHandler> CGame::getObjectHandler() {
    return objectHandler.get();
}

std::shared_ptr<CGame> CGame::ptr() {
    return shared_from_this();
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
        scriptWindow.get ( this->ptr() )->setVisible ( true );
        break;
    }
}

