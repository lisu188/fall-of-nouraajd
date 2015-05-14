#pragma once

#include "CGamePanel.h"
#include "handler/CMouseHandler.h"
#include <QWidget>

class CCharPanel : public AGamePanel,public CClickAction {
	Q_OBJECT
public:
	CCharPanel();
	virtual QRectF boundingRect() const override;
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *,
	                     QWidget * ) override;
	virtual void showPanel (  ) override;
	virtual void hidePanel() override;
	virtual void setUpPanel ( CGameView *view ) override;
	virtual void update() override;
	virtual QString getPanelName() override;
	virtual void onClickAction ( CGameObject *object ) override;
private:
	CListView *playerInventoryView;
	CPlayerEquippedView *playerEquippedView;

	// AGamePanel interface
public:
	virtual void handleDrop ( CPlayerView *view, CGameObject *object );
};
