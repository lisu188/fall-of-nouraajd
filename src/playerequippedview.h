#ifndef PLAYEREQUIPPEDVIEW_H
#define PLAYEREQUIPPEDVIEW_H

#include "CItemSlot.h"

#include <QGraphicsObject>

class Item;
class PlayerEquippedView : public QGraphicsObject {
	Q_OBJECT
public:
	PlayerEquippedView ( std::map<int, Item *> *equipped );
	QRectF boundingRect() const;
	void paint ( QPainter *painter, const QStyleOptionGraphicsItem *option,
	             QWidget *widget );

private:
	std::map<int, Item *> *equipped;
	std::list<CItemSlot *> itemSlots;
	Q_SLOT virtual void update();
};

#endif // PLAYEREQUIPPEDVIEW_H
