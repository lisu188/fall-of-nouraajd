#pragma once
#include <QGraphicsItem>
#include "CCreature.h"
class ScrollObject;
class PlayerListView : public QGraphicsObject {
	Q_OBJECT
	friend class ScrollObject;

public:
	PlayerListView ( std::set<CMapObject *, Comparer> *MapObjects );
	CMap *getMap();
	void setDraggable();
	virtual QRectF boundingRect() const;
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *option,
	                     QWidget *widget );
	void updatePosition ( int i );
	void setXY ( int x, int y );
	std::set<CMapObject *, Comparer> *getItems() const;
	void setItems ( std::set<CMapObject *, Comparer> *value );

private:
	int curPosition;
	int x, y;
	ScrollObject *right, *left;
	std::set<CMapObject *, Comparer> *items;
	QPixmap pixmap;

protected:
	virtual void dropEvent ( QGraphicsSceneDragDropEvent *event );
	Q_SLOT void update();
};

class ScrollObject : public CAnimatedObject {
public:
	ScrollObject ( PlayerListView *stats, bool isRight );
	void setVisible ( bool visible );

private:
	bool isRight;
	PlayerListView *stats;

protected:
	virtual void mousePressEvent ( QGraphicsSceneMouseEvent *event );
};
