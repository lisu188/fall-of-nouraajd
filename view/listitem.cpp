#include "gamescene.h"
#include "listitem.h"

#include <map/tile.h>

#include <QGraphicsSceneMouseEvent>
#include <QDrag>

ListItem::ListItem():MapObject(0,0,0,0)
{
    statsView.setParentItem(this);
    statsView.setVisible(true);
    statsView.setText(" ");
    statsView.setPos(-this->mapToParent(0,0).x(),
                     -statsView.boundingRect().height());
}


void ListItem::setParentItem(QGraphicsItem *parent)
{
    QGraphicsItem::setParentItem(parent);
}

void ListItem::setNumber(int i, int x)
{
    this->QGraphicsItem::setVisible(true);
    int px=i%x*getMap()->getTileSize();
    int py=i/x*getMap()->getTileSize();
    this->QGraphicsItem::setPos(px,py);
}

void ListItem::setVisible(bool visible)
{
    QGraphicsItem::setVisible(visible);
}

void ListItem::setPos(QPointF point)
{
    this->QGraphicsItem::setVisible(true);
    this->QGraphicsItem::setPos(point);
}

void ListItem::hoverEnterEvent(QGraphicsSceneHoverEvent *event)
{
    statsView.setVisible(true);
    statsView.setText(tooltip.c_str());
    statsView.setPos(0,0-statsView.boundingRect().height());
    event->setAccepted(true);
}

void ListItem::hoverLeaveEvent(QGraphicsSceneHoverEvent *event)
{
    statsView.setVisible(false);
    event->setAccepted(true);
}

