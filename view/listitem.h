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

    // QGraphicsItem interface
public:
    QRectF boundingRect() const;
    virtual void paint(QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget);
};

class Comparer {
public:
    bool operator()(ListItem *first,ListItem *second)
    {
        if(!second) {
            return 0;
        }
        return first->compare(second);
    }
};

#endif // LISTITEM_H
