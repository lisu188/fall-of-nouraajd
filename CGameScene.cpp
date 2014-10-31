#include "CGameScene.h"
#include "CGameView.h"
#include "Util.h"
#include <QGraphicsView>
#include <QPointF>
#include <QApplication>
#include <QDesktopWidget>
#include <QKeyEvent>
#include "CPlayerView.h"
#include "CAnimationProvider.h"
#include "CConfigurationProvider.h"
#include <fstream>
#include <QJsonObject>
#include <QDateTime>
#include <QDebug>
#include <vector>
#include "CGamePanel.h"
#include <QThreadPool>
#include "handler/CHandler.h"
#include "CMap.h"
#include "CCreature.h"
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
	this->player = map->getObjectHandler()->createMapObject<CPlayer*> ( player );
	map->addObject ( this->player );
	this->player->moveTo ( map->getEntryX(), map->getEntryY(), map->getEntryZ() );
	this->player->updateViews();
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
	if ( map->getGuiHandler()->isAnyPanelVisible() ||map->isMoving() ) {
		return;
	}
	switch ( event->key() ) {
	case Qt::Key_Up:
		this->getPlayer()->setNextMove ( Coords ( 0,-1 ,0 ) );
		map->move();
		break;
	case Qt::Key_Down:
		this->getPlayer()->setNextMove ( Coords ( 0,1,0 ) );
		map->move();
		break;
	case Qt::Key_Left:
		this->getPlayer()->setNextMove ( Coords ( -1,0,0 ) );
		map->move();
		break;
	case Qt::Key_Right:
		this->getPlayer()->setNextMove ( Coords ( 1,0,0 ) );
		map->move();
		break;
	}
}

CPlayer *CGameScene::getPlayer() const {
	return player;
}

void CGameScene::setPlayer ( CPlayer *value ) {
	player = value;
}

