#pragma once
#include <QGraphicsItem>
#include "CReflection.h"
#include <QWidget>

class CCreature;
class CGameView;
class CPlayerListView;
class CPlayerEquippedView;
class CCharPanel;

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


class BackPackObject : public QWidget {
	Q_OBJECT
public:
	BackPackObject ( CGameView* view ) ;

protected:
	void mousePressEvent ( QMouseEvent * );
	void paintEvent ( QPaintEvent * );

private:
	QPixmap pixmap;
	int time = 0;
	CGameView *view;
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
	BackPackObject *backpack;
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
	virtual void setUpPanel ( CGameView *view );
private:
	CPlayerListView *playerSkillsView;

};

class CScrollPanel:public AGamePanel {
	Q_OBJECT
public:
	CScrollPanel();
	CScrollPanel ( const CScrollPanel& );
	virtual QRectF boundingRect() const;
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *, QWidget * );
	virtual void showPanel ( CGameView * );
	virtual void setUpPanel ( CGameView * );
	virtual void mousePressEvent ( QGraphicsSceneMouseEvent *event );
	QString getText() const;
	void setText ( const QString &value );

private:
	QString text;
};

