#include "CGameView.h"
#include "CLootProvider.h"
#include "Util.h"
#include <QDebug>
#include "CPlayerView.h"
#include <QBitmap>
#include <QDateTime>
#include <QtOpenGL/QGLWidget>
#include <QThreadPool>
#include <QApplication>
#include <QDesktopWidget>
#include "CCreature.h"
#include "CGuiHandler.h"

bool CGameView::init = false;

void CGameView::start() {
	scene->startGame ( mapName ,playerType );
	scene->removeItem ( &loading );
	CPlayer *player = scene->getPlayer();
	playerStatsView.show();
	playerStatsView.setPlayer ( player );
	connect ( player,&CCreature::inventoryChanged,scene->getMap()->getGuiHandler(),&CGuiHandler::refresh );
	connect ( player,&CCreature::equippedChanged,scene->getMap()->getGuiHandler(),&CGuiHandler::refresh );
	init = true;
}

void CGameView::show() {
	showNormal();
}



CGameView::CGameView ( QString mapName , QString playerType ) {
	this->mapName=mapName;
	this->playerType=playerType;
	setHorizontalScrollBarPolicy ( Qt::ScrollBarAlwaysOff );
	setVerticalScrollBarPolicy ( Qt::ScrollBarAlwaysOff );
	setViewportUpdateMode ( QGraphicsView::BoundingRectViewportUpdate );
	setViewport ( new QGLWidget ( QGLFormat ( QGL::SampleBuffers ) ) );
	setViewportUpdateMode ( QGraphicsView::FullViewportUpdate );
	scene = new CGameScene();
	setScene ( scene );
	timer.setSingleShot ( true );
	timer.setInterval ( 250 );
	connect ( &timer, SIGNAL ( timeout() ), this, SLOT ( start() ) );
	playerStatsView.setParent ( this );
	timer.start();
}

CGameView::~CGameView() {
	delete scene;
}



void CGameView::mouseDoubleClickEvent ( QMouseEvent *e ) {
	QWidget::mouseDoubleClickEvent ( e );
	if ( e->button() == Qt::MouseButton::LeftButton || !init ) {
		return;
	}
	if ( isFullScreen() ) {
		this->setWindowState ( Qt::WindowNoState );
	} else {
		this->setWindowState ( Qt::WindowFullScreen );
	}
}

void CGameView::resizeEvent ( QResizeEvent *event ) {
	if (    init ) {
		if ( event ) {
			QWidget::resizeEvent ( event );
			playerStatsView.move ( 0, 0 );
			getScene()->getMap()->getGuiHandler()->refresh();
		}

		CPlayer *player =scene->getPlayer();
		centerOn ( player );
	}
}

void CGameView::wheelEvent ( QWheelEvent * ) {}

void CGameView::dragMoveEvent ( QDragMoveEvent *e ) {
	QGraphicsView::dragMoveEvent ( e );
	repaint();
}

CGameScene *CGameView::getScene() const {
	return scene;
}

void CGameView::setScene ( CGameScene *value ) {
	QGraphicsView::setScene ( value );
	scene = value;
}

