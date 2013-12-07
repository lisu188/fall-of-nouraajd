#include "listitem.h"

#include <map/tiles/tile.h>

ListItem::ListItem()
{

}


void ListItem::setParentItem(QGraphicsItem *parent)
{
    QGraphicsItem::setParentItem(parent);
}

void ListItem::setNumber(int i, int x)
{
    this->QGraphicsItem::setVisible(true);
    int px=i%x*Tile::size;
    int py=i/x*Tile::size;
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
