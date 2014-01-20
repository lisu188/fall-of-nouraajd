#ifndef CHARVIEW_H
#define CHARVIEW_H

#include <QGraphicsItem>

class CharView : public QGraphicsItem
{
public:
    CharView();
    void update();
    virtual QRectF boundingRect() const;
    virtual void paint(QPainter *painter, const QStyleOptionGraphicsItem *, QWidget *);
};

#endif // CHARVIEW_H
