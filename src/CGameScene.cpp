#include "CGameScene.h"
#include "CGameView.h"
#include "CPathFinder.h"
#include "Util.h"
#include <QGraphicsView>
#include <QPointF>
#include <QApplication>
#include <QDesktopWidget>
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
#include "CObjectHandler.h"

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
	this->player->moveTo ( map->getEntryX(), map->getEntryY(), map->getEntryZ(), true );
	this->player->updateViews();
	QThreadPool::globalInstance()->start ( new LoadGameTask ( map ) );
}

void CGameScene::keyPressEvent ( QKeyEvent *keyEvent ) {
	if ( keyEvent ) {
		keyEvent->setAccepted ( false );
		switch ( keyEvent->key() ) {
		case Qt::Key_Up:
			playerMove ( 0, -1 );
			keyEvent->setAccepted ( true );
			break;
		case Qt::Key_Down:
			playerMove ( 0, 1 );
			keyEvent->setAccepted ( true );
			break;
		case Qt::Key_Left:
			playerMove ( -1, 0 );
			keyEvent->setAccepted ( true );
			break;
		case Qt::Key_Right:
			playerMove ( 1, 0 );
			keyEvent->setAccepted ( true );
			break;
		case Qt::Key_C:
			getView()->showCharView();
			keyEvent->setAccepted ( true );
			break;
		}
	}
}

CGameScene::~CGameScene() {
	delete map;
}

void CGameScene::playerMove ( int dirx, int diry ) {
	if ( !CompletionListener::getInstance()->isCompleted() ) {
		return;
	}
	if ( player->getFightList()->size() > 0 ||
	        getView()->getCharView()->isVisible() ) {
		return;
	}
	map->move ( dirx, diry );
}

void CGameScene::mousePressEvent ( QGraphicsSceneMouseEvent *event ) {
	QGraphicsScene::mousePressEvent ( event );
}

void CGameScene::mouseMoveEvent ( QGraphicsSceneMouseEvent *event ) {
	QGraphicsScene::mouseMoveEvent ( event );
}

void CGameScene::mouseReleaseEvent ( QGraphicsSceneMouseEvent *event ) {
	QGraphicsScene::mouseReleaseEvent ( event );
}
CMap *CGameScene::getMap() const {
	return map;
}

void CGameScene::setMap ( CMap *value ) {
	map = value;
}

CGameView *CGameScene::getView() {
//	if ( this->views().size() ==0 ) {
//		return NULL;
//	}
	return dynamic_cast<CGameView*> ( this->views() [0] );
}

CPlayer *CGameScene::getPlayer() const {
	return player;
}

void CGameScene::setPlayer ( CPlayer *value ) {
	player = value;
}

