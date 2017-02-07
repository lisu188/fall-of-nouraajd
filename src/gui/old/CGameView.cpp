//#include "CGameView.h"
//#include "core/CGame.h"
//#include "loader/CLoader.h"
//
//
//void CGameView::show() {
//    showNormal();
//}
//
//std::shared_ptr<CGameView> CGameView::ptr() {
//    return shared_from_this();
//}
//
//CGameView::CGameView ( std::string mapName, std::string playerType ) {
//    setHorizontalScrollBarPolicy ( Qt::ScrollBarAlwaysOff );
//    setVerticalScrollBarPolicy ( Qt::ScrollBarAlwaysOff );
//    setViewportUpdateMode ( QGraphicsView::BoundingRectViewportUpdate );
//    setViewport ( new QGLWidget ( QGLFormat ( QGL::SampleBuffers ) ) );
//    setViewportUpdateMode ( QGraphicsView::FullViewportUpdate );
//    vstd::call_later ( [this, mapName, playerType]() {
//        game = CGameLoader::loadGame ( this->ptr() );
//        setScene ( game.get() );
//        CGameLoader::startGameWithPlayer ( game, mapName, playerType );
//        std::shared_ptr<CPlayer> player = getGame()->getMap()->getPlayer();
//        playerStatsView.setParent ( this );
//        playerStatsView.show();
//        playerStatsView.setPlayer ( player );
//        auto refresh = [this]() {
//            getGame()->getGuiHandler()->refresh();
//        };
//        connect ( player.get(), &CCreature::inventoryChanged, refresh );
//        connect ( player.get(), &CCreature::equippedChanged, refresh );
//        connect ( player.get(), &CCreature::skillsChanged, refresh );
//        init = true;
//    } );
//}
//
//void CGameView::mouseDoubleClickEvent ( QMouseEvent *e ) {
//    QWidget::mouseDoubleClickEvent ( e );
//    if ( e->button() == Qt::MouseButton::LeftButton || !init ) {
//        return;
//    }
//    if ( isFullScreen() ) {
//        this->setWindowState ( Qt::WindowNoState );
//    } else {
//        this->setWindowState ( Qt::WindowFullScreen );
//    }
//}
//
//void CGameView::resizeEvent ( QResizeEvent *event ) {
//    if ( init ) {
//        if ( event ) {
//            QWidget::resizeEvent ( event );
//            playerStatsView.move ( 0, 0 );
//            getGame()->getGuiHandler()->refresh();
//        }
//        centerOn ( getGame()->getMap()->getPlayer() );
//    }
//}
//
//void CGameView::wheelEvent ( QWheelEvent * ) {
//
//}
//
//void CGameView::dragMoveEvent ( QDragMoveEvent *e ) {
//    QGraphicsView::dragMoveEvent ( e );
//    repaint();
//}
//
//std::shared_ptr<CGame> CGameView::getGame() const {
//    return game;
//}
//
//void CGameView::centerOn ( std::shared_ptr<CPlayer> player ) {
//    this->QGraphicsView::centerOn ( player.get() );
//}
//
