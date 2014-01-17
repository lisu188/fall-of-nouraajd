#ifndef PLAYERINVENTORYVIEW_H
#define PLAYERINVENTORYVIEW_H

#include "scrollobject.h"

#include <QGraphicsItem>
#include <creatures/player.h>


class PlayerListView : public QGraphicsObject
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
    void setDraggable() {
        draggable=true;
    }

private:
    int curPosition;
    int x,y;
    ScrollObject *right,*left;
    std::list<ListItem *> *items;
    bool draggable=false;
    QPixmap *pixmap;

    // QGraphicsItem interface
public:
    virtual QRectF boundingRect() const;
    virtual void paint(QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget);
    void updatePosition(int i);

    // QGraphicsItem interface
protected:
    virtual void dropEvent(QGraphicsSceneDragDropEvent *event);

    // QGraphicsItem interface
protected:
    virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);
};

#endif // PLAYERINVENTORYVIEW_H
