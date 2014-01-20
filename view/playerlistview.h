#ifndef PLAYERINVENTORYVIEW_H
#define PLAYERINVENTORYVIEW_H

#include "scrollobject.h"

#include <QGraphicsItem>
#include <creatures/player.h>


class PlayerListView : public QGraphicsObject
{
    friend class ScrollObject;
public:
    PlayerListView(std::set<ListItem *> *listItems);
    void update();
    Map *getMap();
    void setDraggable();
    virtual QRectF boundingRect() const;
    virtual void paint(QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget);
    void updatePosition(int i);

private:
    int curPosition;
    int x,y;
    ScrollObject *right,*left;
    std::set<ListItem *> *items;
    bool draggable=false;
    QPixmap pixmap;
protected:
    virtual void dropEvent(QGraphicsSceneDragDropEvent *event);
    virtual void mousePressEvent(QGraphicsSceneMouseEvent *event);
};

#endif // PLAYERINVENTORYVIEW_H
