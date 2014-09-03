#ifndef ITEMSLOT_H
#define ITEMSLOT_H

#include <QGraphicsObject>

#include "CItem.h"

class CItemSlot : public QGraphicsObject {
	Q_OBJECT
public:
	CItemSlot ( int number, std::map<int, CItem *> *equipped );
	QRectF boundingRect() const;
	void paint ( QPainter *painter, const QStyleOptionGraphicsItem *, QWidget * );
	static bool checkType ( int slot, QWidget *widget );
	void update();
	int getNumber() { return number; }

protected:
	void dragMoveEvent ( QGraphicsSceneDragDropEvent *event );
	void dropEvent ( QGraphicsSceneDragDropEvent *event );

private:
	int number;
	QPixmap pixmap;
	std::map<int, CItem *> *equipped;
};

#endif // ITEMSLOT_H
