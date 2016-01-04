#pragma once

#include "CGamePanel.h"

class CPlayerInventoryView;

class CTradeItemsView;

class CTradePanel : public AGamePanel {

public:
    CTradePanel();

    virtual void showPanel();

    virtual void hidePanel();

    virtual void update();

    virtual void setUpPanel ( std::shared_ptr<CGameView> view ) override;

    virtual std::string getPanelName();

    virtual QRectF boundingRect() const;

    virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *, QWidget * );

    virtual void handleDrop ( std::shared_ptr<CPlayerView> view, std::shared_ptr<CGameObject> object ) override;

    virtual void onClickAction ( std::shared_ptr<CGameObject> object ) override;

private:
    std::shared_ptr<CPlayerInventoryView> playerInventoryView;
    std::shared_ptr<CTradeItemsView> tradeItemsView;
};
