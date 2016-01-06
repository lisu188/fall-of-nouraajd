#include "CGame.h"
#include "loader/CLoader.h"

CGame::CGame ( std::shared_ptr<CGameView> view ) : view ( view ) {

}

CGame::~CGame() {

}

void CGame::changeMap ( std::string file ) {
    CGameLoader::changeMap ( this->ptr(), file );
}

std::shared_ptr<CMap> CGame::getMap() const {
    return map;
}

void CGame::setMap ( std::shared_ptr<CMap> map ) {
    this->map = map;
}

std::shared_ptr<CGameView> CGame::getView() {
    return view.lock();
}

//std::shared_ptr<CGuiHandler> CGame::getGuiHandler() {
//    return guiHandler.get ( this->ptr() );
//}

std::shared_ptr<CScriptHandler> CGame::getScriptHandler() {
    return scriptHandler.get();
}

std::shared_ptr<CObjectHandler> CGame::getObjectHandler() {
    return objectHandler.get();
}

std::shared_ptr<CGame> CGame::ptr() {
    return shared_from_this();
}

void CGame::keyPressEvent ( void  * event ) { //TODO: implement
//    if ( map->isMoving() ) {
//        return;
//    }
//    switch ( event->key() ) {
//    case Qt::Key_Up:
//        if ( !getGuiHandler()->isAnyPanelVisible() ) {
//            map->getPlayer()->setNextMove ( Coords ( 0, -1, 0 ) );
//            map->move();
//        }
//        break;
//    case Qt::Key_Down:
//        if ( !getGuiHandler()->isAnyPanelVisible() ) {
//            map->getPlayer()->setNextMove ( Coords ( 0, 1, 0 ) );
//            map->move();
//        }
//        break;
//    case Qt::Key_Left:
//        if ( !getGuiHandler()->isAnyPanelVisible() ) {
//            map->getPlayer()->setNextMove ( Coords ( -1, 0, 0 ) );
//            map->move();
//        }
//        break;
//    case Qt::Key_Right:
//        if ( !getGuiHandler()->isAnyPanelVisible() ) {
//            map->getPlayer()->setNextMove ( Coords ( 1, 0, 0 ) );
//            map->move();
//        }
//        break;
//    case Qt::Key_Space:
//        if ( !getGuiHandler()->isAnyPanelVisible() ) {
//            map->getPlayer()->setNextMove ( Coords ( 0, 0, 0 ) );
//            map->move();
//        }
//        break;
//    case Qt::Key_I:
//        getGuiHandler()->flipPanel ( "CCharPanel" );
//        break;
//    case Qt::Key_S:
//        scriptWindow.get ( this->ptr() )->setVisible ( true );
//        break;
//    }
}

