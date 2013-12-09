#include <animation/animatedobject.h>

#ifndef LISTITEM_H
#define LISTITEM_H

class ListItem : public AnimatedObject
{
public:
    ListItem();
    void setParentItem(QGraphicsItem *parent);
    void setNumber(int i, int x);
    void setVisible(bool visible);
    void setPos(QPointF point);
};

#endif // LISTITEM_H
