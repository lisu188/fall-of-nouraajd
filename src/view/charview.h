#ifndef CHARVIEW_H
#define CHARVIEW_H

#include <QGraphicsItem>

class CharView : public QGraphicsObject
{
public:
    CharView();
    virtual QRectF boundingRect() const;
    virtual void paint(QPainter *painter, const QStyleOptionGraphicsItem *, QWidget *);
};

#endif // CHARVIEW_H
