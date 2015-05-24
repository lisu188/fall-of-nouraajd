#pragma once
#include "CGamePanel.h"

class CPlayerInventoryView;
class CTradeItemsView;

class CTradePanel : public AGamePanel {
    Q_OBJECT
public:
    CTradePanel();

    virtual void showPanel();
    virtual void hidePanel();
    virtual void update();
    virtual void setUpPanel ( CGameView * view );
    virtual QString getPanelName();
    virtual QRectF boundingRect() const;
    virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *, QWidget * );
    virtual void handleDrop ( CPlayerView *,std::shared_ptr<CGameObject> object ) override;
    virtual void onClickAction ( std::shared_ptr<CGameObject> object ) override;
private:
    CPlayerInventoryView *playerInventoryView=0;
    CTradeItemsView *tradeItemsView=0;
};
