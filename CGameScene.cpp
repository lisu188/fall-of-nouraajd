#include "CGameScene.h"
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

class LoadGameTask  : public QRunnable {
public:
	LoadGameTask ( CMap *map ) :map ( map ) {}
	void run() {
		QMetaObject::invokeMethod ( map, "ensureSize",
		                            Qt::ConnectionType::BlockingQueuedConnection );
		QMetaObject::invokeMethod ( map->getScene()->getView(),"show" );
	}
private:
	CMap *map;
};

void CGameScene::startGame ( QString file ,QString player ) {
	srand ( time ( 0 ) );
	map = new CMap ( this,file );
	map->setPlayer ( player  );
	QThreadPool::globalInstance()->start ( new LoadGameTask ( map ) );
}

CGameScene::CGameScene ( QObject *parent ) :QGraphicsScene ( parent ) {

}

CGameScene::~CGameScene() {

}

CMap *CGameScene::getMap() const {
	return map;
}

CGameView *CGameScene::getView() {
	return dynamic_cast<CGameView*> ( this->views() [0] );
}

void CGameScene::removeObject ( CMapObject *object ) {
	this->removeItem ( object );
}

void CGameScene::keyPressEvent ( QKeyEvent *event ) {
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


