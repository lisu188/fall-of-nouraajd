#ifndef PLAYERINVENTORYVIEW_H
#define PLAYERINVENTORYVIEW_H

#include "scrollobject.h"

#include <QGraphicsItem>
#include <creatures/player.h>


class PlayerListView : public QGraphicsItem
{
    friend class ScrollObject;
public:
    PlayerListView(std::list<ListItem *> *listItems);
    void update();
    Map *getMap()
    {
        if(items->size())
        {
            return items->front()->getMap();
        }
        return 0;
    }

private:
    int curPosition;
    int x,y;
    ScrollObject *right,*left;
    std::list<ListItem *> *items;

    // QGraphicsItem interface
public:
    virtual QRectF boundingRect() const;
    virtual void paint(QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget);
    void updatePosition(int i);

    // QGraphicsItem interface
protected:
    virtual void dropEvent(QGraphicsSceneDragDropEvent *event);
};

#endif // PLAYERINVENTORYVIEW_H
