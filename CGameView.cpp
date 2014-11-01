#include "CGameView.h"
#include "Util.h"
#include <QDebug>
#include "CPlayerView.h"
#include <QBitmap>
#include <QDateTime>
#include <QtOpenGL/QGLWidget>
#include <QThreadPool>
#include <QApplication>
#include <QDesktopWidget>
#include "object/CObject.h"
#include "handler/CHandler.h"

void CGameView::start() {
	getScene()->startGame ( mapName ,playerType );
	CPlayer *player = getScene()->getPlayer();
	playerStatsView.show();
	playerStatsView.setPlayer ( player );
	connect ( player,&CCreature::inventoryChanged,getScene()->getMap()->getGuiHandler(),&CGuiHandler::refresh );
	connect ( player,&CCreature::equippedChanged,getScene()->getMap()->getGuiHandler(),&CGuiHandler::refresh );
	connect ( player,&CCreature::skillsChanged,getScene()->getMap()->getGuiHandler(),&CGuiHandler::refresh );
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
	setScene ( new CGameScene ( this ) );
	timer.setSingleShot ( true );
	timer.setInterval ( 250 );
	connect ( &timer,&QTimer::timeout, this, &CGameView::start );
	playerStatsView.setParent ( this );
	timer.start();
}

CGameView::~CGameView() {

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

		CPlayer *player =getScene()->getPlayer();
		centerOn ( player );
	}
}

void CGameView::wheelEvent ( QWheelEvent * ) {

}

void CGameView::dragMoveEvent ( QDragMoveEvent *e ) {
	QGraphicsView::dragMoveEvent ( e );
	repaint();
}

CGameScene *CGameView::getScene() const {
	return dynamic_cast<CGameScene *> ( scene() );
}

void CGameView::centerOn ( CPlayer *player ) {
	this->QGraphicsView::centerOn ( player );
}

