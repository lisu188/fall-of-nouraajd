#include "CGame.h"
#include "CGameView.h"
#include "Util.h"
#include <QGraphicsView>
#include <QPointF>
#include <QApplication>
#include <QDesktopWidget>
#include <QKeyEvent>
#include "CPlayerView.h"
#include <fstream>
#include <QJsonObject>
#include <QDateTime>
#include <QDebug>
#include <vector>
#include "panel/CPanel.h"
#include <QThreadPool>
#include "handler/CHandler.h"
#include "CMap.h"
#include "object/CObject.h"
#include "CPathFinder.h"


void CGame::startGame ( QString file ,QString player ) {
    srand ( time ( 0 ) );
    map = new CMap ( this,file );
    map->setPlayer ( map->getObjectHandler()->createObject<CPlayer*> ( player )  );
    AsyncTask::async ( [this]() {
        map->ensureSize();
        map->getGame()->getView()->show();
    } );
}

void CGame::changeMap ( QString file ) {
    AsyncTask::async ( [this,file]() {
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

void CGame::removeObject ( CMapObject *object ) {
    this->removeItem ( object );
}

void CGame::keyPressEvent ( QKeyEvent *event ) {
    if ( map->isMoving() ) {
        return;
    }
    switch ( event->key() ) {
    case Qt::Key_Up:
        if ( !map->getGuiHandler()->isAnyPanelVisible() ) {
            map->getPlayer()->setNextMove ( Coords ( 0,-1 ,0 ) );
            map->move();
        }
        break;
    case Qt::Key_Down:
        if ( !map->getGuiHandler()->isAnyPanelVisible() ) {
            map->getPlayer()->setNextMove ( Coords ( 0,1,0 ) );
            map->move();
        }
        break;
    case Qt::Key_Left:
        if ( !map->getGuiHandler()->isAnyPanelVisible() ) {
            map->getPlayer()->setNextMove ( Coords ( -1,0,0 ) );
            map->move();
        }
        break;
    case Qt::Key_Right:
        if ( !map->getGuiHandler()->isAnyPanelVisible() ) {
            map->getPlayer()->setNextMove ( Coords ( 1,0,0 ) );
            map->move();
        }
        break;
    case Qt::Key_Space:
        if ( !map->getGuiHandler()->isAnyPanelVisible() ) {
            map->getPlayer()->setNextMove ( Coords ( 0,0,0 ) );
            map->move();
        }
        break;
    case Qt::Key_I:
        this->getMap()->getGuiHandler()->flipPanel ( "CCharPanel" );
        break;
    }
}





