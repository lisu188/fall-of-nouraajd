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
    virtual bool compare(ListItem *item);
protected:
    std::string tooltip;
    virtual void hoverEnterEvent(QGraphicsSceneHoverEvent *event);
    virtual void hoverLeaveEvent(QGraphicsSceneHoverEvent *event);
private:
    QGraphicsSimpleTextItem statsView;
};

class Comparer {
public:
    bool operator()(ListItem *first,ListItem *second)
    {
        return first->compare(second);
    }
};

#endif // LISTITEM_H
