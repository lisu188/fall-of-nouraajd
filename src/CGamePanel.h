#pragma once
#include <QGraphicsItem>
#include "CReflection.h"

class CCreature;
class CGameView;
class PlayerListView;
class PlayerEquippedView;

class AGamePanel : public QGraphicsObject {
	Q_OBJECT
public:
	virtual void showPanel ( CGameView *view ) =0;
	virtual void setUpPanel ( CGameView * view ) =0;
	virtual QRectF boundingRect() const=0;
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget ) =0;
};


class CCharPanel : public AGamePanel {
	Q_OBJECT
public:
	CCharPanel();
	CCharPanel ( const CCharPanel& );
	virtual QRectF boundingRect() const;
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *,
	                     QWidget * );
	virtual void showPanel ( CGameView *view );
	virtual void setUpPanel ( CGameView * view );
private:
	PlayerListView *playerInventoryView;
	PlayerEquippedView *playerEquippedView;
};

class CFightPanel : public AGamePanel {
	Q_OBJECT
public:
	CFightPanel();
	CFightPanel ( const CFightPanel& );
	static CCreature *selected;
	void update();
	virtual QRectF boundingRect() const;
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *,
	                     QWidget * );
	virtual void showPanel ( CGameView *view );
	void setUpPanel ( CGameView *view );
private:
	PlayerListView *playerSkillsView;

};

