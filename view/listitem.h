#ifndef LISTITEM_H
#define LISTITEM_H

#include <map/map.h>

class ListItem : public MapObject
{
public:
    ListItem(int x=0,int y=0,int z=0,int v=0);
    void setParentItem(QGraphicsItem *parent);
    void setNumber(int i, int x);
    void setVisible(bool visible);
    void setPos(QPointF point);
    virtual bool compare(ListItem *item);
    QRectF boundingRect() const;
    virtual void paint(QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget);
protected:
    std::string tooltip;
    virtual void hoverEnterEvent(QGraphicsSceneHoverEvent *event);
    virtual void hoverLeaveEvent(QGraphicsSceneHoverEvent *event);
    QGraphicsSimpleTextItem statsView;
};

class Comparer {
public:
    bool operator()(ListItem *first,ListItem *second)
    {
        if(!second||!first) {
            return 0;
        }
        return first->compare(second);
    }
};

#endif // LISTITEM_H
