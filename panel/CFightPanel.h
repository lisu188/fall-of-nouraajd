#pragma once
#include <QGraphicsObject>
#include "CGamePanel.h"
class CCreature;
class CFightPanel;
class CListView;
class CCreatureFightView : public QGraphicsObject {
	Q_OBJECT
	friend class CFightPanel;
public:
	CCreatureFightView ( CFightPanel * panel );
	void setCreature ( CCreature * creature );
	virtual QRectF boundingRect() const;
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *, QWidget * );

private:
	CCreature *creature=0;

};

class CFightPanel : public AGamePanel,public CClickAction {
	Q_OBJECT
public:
	CFightPanel();

	virtual void update() override;
	virtual QRectF boundingRect() const override;
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *,
	                     QWidget * ) override;
	virtual void showPanel ( ) override;
	virtual void setUpPanel ( CGameView *view  ) override;
	virtual void hidePanel() override;
	virtual QString getPanelName() override;
	virtual void onClickAction ( CGameObject *object ) override;
protected:
	virtual void mousePressEvent ( QGraphicsSceneMouseEvent * );
private:
	CListView *playerSkillsView;
	CCreatureFightView *fightView;
};


