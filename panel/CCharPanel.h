#pragma once

#include "CGamePanel.h"
#include <QWidget>

class CCharPanel : public AGamePanel {
	Q_OBJECT
public:
	CCharPanel();
	CCharPanel ( const CCharPanel& );
	virtual QRectF boundingRect() const override;
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *,
	                     QWidget * ) override;
	virtual void showPanel (  ) override;
	virtual void hidePanel() override;
	virtual void setUpPanel ( CGameView *view ) override;
	virtual void update() override;
	virtual QString getPanelName() override;
private:
	CListView *playerInventoryView;
	CPlayerEquippedView *playerEquippedView;
};
