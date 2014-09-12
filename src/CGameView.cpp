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

bool CGameView::init = false;

void CGameView::start() {
	scene->startGame ( mapName ,playerType );
	scene->removeItem ( &loading );
	CPlayer *player = scene->getPlayer();
	playerStatsView.show();
	playerStatsView.setPlayer ( player );
	for ( auto it=panels.begin(); it!=panels.end(); it++ ) {
		( *it ).second->setUpPanel ( this );
	}
	init = true;
}

void CGameView::show() {
	showNormal();
}

void CGameView::initPanels() {
	auto viewList=CReflection::getInstance()->getInherited<AGamePanel*>();
	for ( auto it=viewList.begin(); it!=viewList.end(); it++ ) {
		panels[ ( *it )->metaObject()->className()]=*it;
		scene->addItem ( *it );
	}
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
	QPixmap pixmap ( "images/loading.png" );
	loading.setPixmap ( pixmap.scaled ( this->width(), this->height(),
	                                    Qt::IgnoreAspectRatio,
	                                    Qt::SmoothTransformation ) );
	scene->addItem ( &loading );
	timer.setSingleShot ( true );
	timer.setInterval ( 250 );
	connect ( &timer, SIGNAL ( timeout() ), this, SLOT ( start() ) );
	playerStatsView.setParent ( this );
	initPanels();
	timer.start();
}

CGameView::~CGameView() {
	delete scene;
}

void CGameView::showPanel ( QString panel ) {
	panels[panel]->showPanel ( this );
}

AGamePanel *CGameView::getPanel ( QString panel ) {
	return panels[panel];
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
	if ( event ) {
		QWidget::resizeEvent ( event );
		playerStatsView.move ( 0, 0 );
		AGamePanel *panel=getPanel ( "CCharPanel" );
		panel->showPanel ( this );
		panel->setVisible ( false );
	}
    if (    init ) {
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

