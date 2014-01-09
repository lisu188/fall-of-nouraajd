#include "gamescene.h"
#include "scrollobject.h"

#include <view/playerlistview.h>

ScrollObject::ScrollObject(PlayerListView *stats, bool isRight)
{
    this->isRight=isRight;
    this->stats=stats;
    if(!isRight)
    {
        this->setAnimation("images/arrows/left/",50);
    }
    else
    {
        this->setAnimation("images/arrows/right/",50);
    }
}

void ScrollObject::setVisible(bool visible)
{
    this->QGraphicsPixmapItem::setVisible(visible);
    if(visible)
    {
        setParentItem(stats);
        if(!isRight) {
            this->setPos(0,GameScene::getGame()->getMap()->getTileSize()*(stats->y));
        }
        else {
            this->setPos(GameScene::getGame()->getMap()->getTileSize()*(stats->x-1),GameScene::getGame()->getMap()->getTileSize()*(stats->y));
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
