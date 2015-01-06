#pragma once
#include "CGamePanel.h"
#include "handler/CMouseHandler.h"

class CPlayerInventoryView;
class CTradeItemsView;

class CTradePanel : public AGamePanel,public CClickAction {
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

	std::set<CItem*> *getItems();
	virtual void onClickAction ( CGameObject *object );
private:
	CPlayerInventoryView *playerInventoryView=0;
	CTradeItemsView *tradeItemsView=0;
	std::set<CItem*> items;
};
