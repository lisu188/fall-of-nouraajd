#include "CGameView.h"
#include "CUtil.h"
#include "CGame.h"
#include "object/CObject.h"
#include "handler/CHandler.h"
#include "gui/CGui.h"

void CGameView::start() {
    getGame()->startGame ( mapName ,playerType );
    CPlayer *player = getGame()->getMap()->getPlayer();
    playerStatsView.show();
    playerStatsView.setPlayer ( player );
    auto refresh=[this]() {
        getGame()->getGuiHandler()->refresh();
    };
    connect ( player,&CCreature::inventoryChanged,refresh );
    connect ( player,&CCreature::equippedChanged,refresh );
    connect ( player,&CCreature::skillsChanged,refresh );
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
            getGame()->getGuiHandler()->refresh();
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

