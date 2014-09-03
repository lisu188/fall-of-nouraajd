#pragma once
#include <QGraphicsObject>
#include <QWidget>
#include <set>
#include "CAnimatedObject.h"
#include "Util.h"

class CMapObject;
class CMap;
class QPaintEvent;
class CPlayer;
class CItem;
class CItemSlot;
class CPlayerEquippedView : public QGraphicsObject {
	Q_OBJECT
public:
	CPlayerEquippedView ( std::map<int, CItem *> *equipped );
	QRectF boundingRect() const;
	void paint ( QPainter *painter, const QStyleOptionGraphicsItem *option,
	             QWidget *widget );

private:
	std::map<int, CItem *> *equipped;
	std::list<CItemSlot *> itemSlots;
	Q_SLOT virtual void update();
};

class PlayerStatsView : public QWidget {
	Q_OBJECT
public:
	explicit PlayerStatsView();
	void setPlayer ( CPlayer *value );

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
	CPlayerListView ( std::set<CMapObject *, Comparer<CMapObject>> *MapObjects );
	CMap *getMap();
	void setDraggable();
	virtual QRectF boundingRect() const;
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *option,
	                     QWidget *widget );
	void updatePosition ( int i );
	void setXY ( int x, int y );
	std::set<CMapObject *, Comparer<CMapObject>> *getItems() const;
	void setItems ( std::set<CMapObject *, Comparer<CMapObject>> *value );

private:
	int curPosition;
	int x, y;
	CScrollObject *right, *left;
	std::set<CMapObject *, Comparer<CMapObject>> *items;
	QPixmap pixmap;

protected:
	virtual void dropEvent ( QGraphicsSceneDragDropEvent *event );
	Q_SLOT void update();
};

class CScrollObject : public CAnimatedObject {
public:
	CScrollObject ( CPlayerListView *stats, bool isRight );
	void setVisible ( bool visible );

private:
	bool isRight;
	CPlayerListView *stats;

protected:
	virtual void mousePressEvent ( QGraphicsSceneMouseEvent *event );
};

