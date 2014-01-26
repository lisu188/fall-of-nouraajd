#include "gamescene.h"
#include "listitem.h"

#include <map/tile.h>

#include <QGraphicsSceneMouseEvent>
#include <QDrag>

std::string toLower(const std::string& s)
{
    std::string result;
    std::locale loc;
    for (unsigned int i = 0; i < s.length(); ++i)
    {
        result += std::tolower(s.at(i), loc);
    }
    return result;
}

ListItem::ListItem(int x,int y,int z,int v):MapObject(x,y,z,v)
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

bool ListItem::compare(ListItem *item)
{
    return toLower(className).compare(toLower(item->className))<0;
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

QRectF ListItem::boundingRect() const
{
    return QRectF(0,0,Map::getTileSize(),Map::getTileSize());
}

void ListItem::paint(QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget)
{
    AnimatedObject::paint(painter,option,widget);
}

