#pragma once

#include "core/CGlobal.h"
#include "CPlayerView.h"
#include "panel/CPanel.h"

class CPlayer;

class CGame;

class CGameView : public QGraphicsView, public std::enable_shared_from_this<CGameView> {
    Q_OBJECT
public:
    //replace argument with bean
    CGameView ( QString mapName, QString playerType );

    std::shared_ptr<CGame> getGame() const;

    void centerOn ( std::shared_ptr<CPlayer> player );

    Q_INVOKABLE void show();

    std::shared_ptr<CGameView> ptr();

protected:
    virtual void mouseDoubleClickEvent ( QMouseEvent *e );

    virtual void resizeEvent ( QResizeEvent *event );

    virtual void wheelEvent ( QWheelEvent * );

    virtual void dragMoveEvent ( QDragMoveEvent *e );

private:
    bool init = false;
    PlayerStatsView playerStatsView;
    std::shared_ptr<CGame> game;
};

