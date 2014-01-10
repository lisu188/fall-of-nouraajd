#ifndef LISTITEM_H
#define LISTITEM_H

#include <map/map.h>

class ListItem : public MapObject
{
public:
    ListItem();
    void setParentItem(QGraphicsItem *parent);
    void setNumber(int i, int x);
    void setVisible(bool visible);
    void setPos(QPointF point);
private:
    QGraphicsSimpleTextItem statsView;
protected:
    std::string tooltip;
    void mousePressEvent(QGraphicsSceneMouseEvent *event);
    void mouseReleaseEvent(QGraphicsSceneMouseEvent *event);
};

#endif // LISTITEM_H
