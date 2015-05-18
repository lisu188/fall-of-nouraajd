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
    getGame()->startGame ( mapName ,playerType );
    CPlayer *player = getGame()->getMap()->getPlayer();
    playerStatsView.show();
    playerStatsView.setPlayer ( player );
    connect ( player,&CCreature::inventoryChanged,getGame()->getMap()->getGuiHandler(),&CGuiHandler::refresh );
    connect ( player,&CCreature::equippedChanged,getGame()->getMap()->getGuiHandler(),&CGuiHandler::refresh );
    connect ( player,&CCreature::skillsChanged,getGame()->getMap()->getGuiHandler(),&CGuiHandler::refresh );
    init = true;
}

void CGameView::show() {
    showNormal();
}

CGameView::CGameView ( QString mapName , QString playerType ) :mapName ( mapName ),playerType ( playerType ) {
    game=new CGame ( this );
    setHorizontalScrollBarPolicy ( Qt::ScrollBarAlwaysOff );
    setVerticalScrollBarPolicy ( Qt::ScrollBarAlwaysOff );
    setViewportUpdateMode ( QGraphicsView::BoundingRectViewportUpdate );
    setViewport ( new QGLWidget ( QGLFormat ( QGL::SampleBuffers ) ) );
    setViewportUpdateMode ( QGraphicsView::FullViewportUpdate );
    setScene ( game );
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
            getGame()->getMap()->getGuiHandler()->refresh();
        }

        CPlayer *player =getGame()->getMap()->getPlayer();
        centerOn ( player );
    }
}

void CGameView::wheelEvent ( QWheelEvent * ) {

}

void CGameView::dragMoveEvent ( QDragMoveEvent *e ) {
    QGraphicsView::dragMoveEvent ( e );
    repaint();
}

CGame *CGameView::getGame() const {
    return game;
}

void CGameView::centerOn ( CPlayer *player ) {
    this->QGraphicsView::centerOn ( player );
}

