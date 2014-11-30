#pragma once
#include "CGamePanel.h"

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
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget );
};
