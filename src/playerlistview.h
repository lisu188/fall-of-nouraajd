#ifndef PLAYERINVENTORYVIEW_H
#define PLAYERINVENTORYVIEW_H

#include "scrollobject.h"

#include <QGraphicsItem>
#include <src/player.h>

class PlayerListView : public QGraphicsObject {
	Q_OBJECT
	friend class ScrollObject;

public:
	PlayerListView ( std::set<MapObject *, Comparer> *MapObjects );
	Map *getMap();
	void setDraggable();
	virtual QRectF boundingRect() const;
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *option,
	                     QWidget *widget );
	void updatePosition ( int i );
	void setXY ( int x, int y );
	std::set<MapObject *, Comparer> *getItems() const;
	void setItems ( std::set<MapObject *, Comparer> *value );

private:
	int curPosition;
	int x, y;
	ScrollObject *right, *left;
	std::set<MapObject *, Comparer> *items;
	QPixmap pixmap;

protected:
	virtual void dropEvent ( QGraphicsSceneDragDropEvent *event );
	Q_SLOT void update();
};

#endif // PLAYERINVENTORYVIEW_H
