#include "gamescene.h"
#include "gameview.h"
#include "CPathFinder.h"
#include "util.h"
#include <QGraphicsView>
#include <QPointF>
#include <QApplication>
#include <QDesktopWidget>
#include <src/playerlistview.h>
#include "CAnimationProvider.h"
#include "CConfigurationProvider.h"
#include <fstream>
#include <lib/json/json.h>
#include <QDateTime>
#include <QDebug>
#include <vector>
#include "CGamePanel.h"
#include <QThreadPool>

class LoadGameTask  : public QRunnable {
public:
	LoadGameTask ( CMap *map ) :map ( map ) {}
	void run() {
		QMetaObject::invokeMethod ( map, "ensureSize",
		                            Qt::ConnectionType::BlockingQueuedConnection );
		QMetaObject::invokeMethod ( map->getScene()->getView(),"show" );
//		double all= ( map->getCurrentXBound() + 20 ) * ( map->getCurrentYBound() + 20 );
//		double loaded=0;
//		for ( int i = -10; i < map->getCurrentXBound() + 10; i++ )
//			for ( int j = -10; j < map->getCurrentYBound() + 10; j++ ) {
//				QMetaObject::invokeMethod ( map, "ensureTile",
//				                            Qt::ConnectionType::BlockingQueuedConnection,
//				                            Q_ARG ( int, i ),Q_ARG ( int, j ) );
//				loaded++;
//				if ( ( ( int ) loaded ) %100==0 ) {
//					//qDebug()<<loaded/all*100<<"%";
//				}
//			}
	}
private:
	CMap *map;
};

void CGameScene::startGame ( std::string file ,std::string player ) {
	srand ( time ( 0 ) );
	map = new CMap ( this,file );
	this->player = new Player ( map,player );
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

void CGameScene::playerMove ( int dirx, int diry ) {
	if ( !CompletionListener::getInstance()->isCompleted() ) {
		return;
	}
	if ( player->getFightList()->size() > 0 ||
	        getView()->getCharView()->isVisible() ) {
		return;
	}
	int sizex, sizey;
	if ( getView() ) {
		sizex = getView()->width() / map->getTileSize() + 1;
		sizey = getView()->height() / map->getTileSize() + 1;
	} else {
		sizex = QApplication::desktop()->width() / map->getTileSize() + 1;
		sizey = QApplication::desktop()->height() / map->getTileSize() + 1;
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

Player *CGameScene::getPlayer() const {
	return player;
}

void CGameScene::setPlayer ( Player *value ) {
	player = value;
}

