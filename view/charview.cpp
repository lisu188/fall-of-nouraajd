#include "charview.h"

#include <qpainter.h>

CharView::CharView()
{
    setZValue(6);
    setVisible(false);
}

void CharView::update()
{
    QGraphicsItem::update();
}

QRectF CharView::boundingRect() const
{
    return QRectF(0,0,400,300);
}

void CharView::paint(QPainter *painter, const QStyleOptionGraphicsItem *, QWidget *)
{
    painter->fillRect(boundingRect(),QColor("BLACK"));
}
