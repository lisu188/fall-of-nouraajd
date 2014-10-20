#pragma once
#include <QGraphicsObject>
#include <QWidget>
#include <set>
#include "CAnimatedObject.h"

class CMapObject;
class CMap;
class QPaintEvent;
class CPlayer;
class CItem;
class CItemSlot;
class CGameView;
class CPlayerEquippedView : public QGraphicsObject {
	Q_OBJECT
public:
	CPlayerEquippedView ( CGameView *view );
	QRectF boundingRect() const;
	void paint ( QPainter *, const QStyleOptionGraphicsItem *, QWidget * );
	void update();
private:
	std::list<CItemSlot *> itemSlots;
};

class PlayerStatsView : public QWidget {
	Q_OBJECT
public:
	explicit PlayerStatsView();
	void setPlayer ( CPlayer *value );
	void update();
protected:
	void paintEvent ( QPaintEvent * );

private:
	CPlayer *player = 0;
};

class CScrollObject;
class CPlayerListView : public QGraphicsObject {
	Q_OBJECT
	friend class CScrollObject;
public:
	CPlayerListView ( CGameView *view );
	void setDraggable();
	virtual QRectF boundingRect() const;
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *, QWidget * );
	void updatePosition ( int i );
	void setXY ( int x, int y );
	void update();
protected:
	virtual void dropEvent ( QGraphicsSceneDragDropEvent *event );
	virtual std::set<QGraphicsItem *> getItems() const=0;
	CGameView *view=0;
private:
	void setNumber ( QGraphicsItem *item,int i, int x );
	unsigned int curPosition;
	unsigned int x, y;
	CScrollObject *right, *left;
	QPixmap pixmap;
};

class CPlayerInventoryrView:public CPlayerListView {
	Q_OBJECT
public:
	CPlayerInventoryrView ( CGameView *view );
protected:
	virtual std::set<QGraphicsItem *> getItems() const;
};

class CPlayerIteractionView:public CPlayerListView {
	Q_OBJECT
public:
	CPlayerIteractionView ( CGameView *view );
protected:
	virtual std::set<QGraphicsItem *> getItems() const;
};

class CScrollObject : public CAnimatedObject {
public:
	CScrollObject ( CPlayerListView *stats, bool isRight );
	void setVisible ( bool visible );

private:
	bool isRight;
	CPlayerListView *stats;

protected:
	virtual void mousePressEvent ( QGraphicsSceneMouseEvent * );
};

class CItemSlot : public QGraphicsObject {
	Q_OBJECT
public:
	CItemSlot ( int number, CGameView *view );
	QRectF boundingRect() const;
	void paint ( QPainter *painter, const QStyleOptionGraphicsItem *, QWidget * );
	static bool checkType ( int slot, CItem *item );
	void update();
	int getNumber();

protected:
	void dragMoveEvent ( QGraphicsSceneDragDropEvent *event );
	void dropEvent ( QGraphicsSceneDragDropEvent *event );

private:
	int number=-1;
	QPixmap pixmap;
	CGameView *view;
};

