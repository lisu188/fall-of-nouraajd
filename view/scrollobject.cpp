#include "gamescene.h"
#include "scrollobject.h"

#include <view/playerlistview.h>

ScrollObject::ScrollObject(PlayerListView *stats, bool isRight)
{
    this->isRight=isRight;
    this->stats=stats;
    if(stats->getMap())
    {
        tileSize=stats->getMap()->getTileSize();
    }
    else
    {
        tileSize=0;
    }
    if(!isRight)
    {
        this->setAnimation("images/arrows/left/",tileSize);
    }
    else
    {
        this->setAnimation("images/arrows/right/",tileSize);
    }
}

void ScrollObject::setVisible(bool visible)
{
    this->QGraphicsPixmapItem::setVisible(visible);
    if(visible)
    {
        setParentItem(stats);
        if(!isRight) {
            this->setPos(0,tileSize*(stats->y));
        }
        else {
            this->setPos(tileSize*(stats->x-1),tileSize*(stats->y));
        }
    }
    else {
        setParentItem(0);
    }
}

void ScrollObject::mousePressEvent(QGraphicsSceneMouseEvent *event)
{
    if(isRight) {
        stats->updatePosition(1);
    }
    if(!isRight) {
        stats->updatePosition(-1);
    }
}
