#pragma once
#include <QGraphicsItem>
#include "CReflection.h"

class CCreature;
class CGameView;
class CPlayerListView;
class CPlayerEquippedView;

class AGamePanel : public QGraphicsObject {
	Q_OBJECT
public:
	AGamePanel();
	AGamePanel ( const AGamePanel& );
	virtual void showPanel ( CGameView * );
	virtual void setUpPanel ( CGameView *  );
	virtual QRectF boundingRect() const;
	virtual void paint ( QPainter *, const QStyleOptionGraphicsItem *, QWidget * );
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
	CPlayerListView *playerInventoryView;
	CPlayerEquippedView *playerEquippedView;
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
	CPlayerListView *playerSkillsView;

};

