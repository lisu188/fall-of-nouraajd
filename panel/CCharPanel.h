#pragma once

#include "CGamePanel.h"
#include <QWidget>

class BackPackObject : public QWidget {
	Q_OBJECT
public:
	BackPackObject ( CGameView* view , CCharPanel *panel ) ;

protected:
	void mousePressEvent ( QMouseEvent * ) override;
	void paintEvent ( QPaintEvent * ) override;

private:
	CCharPanel *panel=0;
	QPixmap pixmap;
	int time = 0;
};

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
	CPlayerListView *playerInventoryView;
	CPlayerEquippedView *playerEquippedView;
	BackPackObject *backpack;
};
