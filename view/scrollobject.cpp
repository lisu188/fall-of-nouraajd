#include "gamescene.h"
#include "scrollobject.h"

#include <view/playerlistview.h>

ScrollObject::ScrollObject(PlayerListView *stats, bool isRight)
{
    this->isRight=isRight;
    this->setZValue(1);
    this->stats=stats;
    if(!isRight)
    {
        this->setAnimation("images/arrows/left/",50);
    }
    else
    {
        this->setAnimation("images/arrows/right/",50);
    }
    setParentItem(stats);
}

void ScrollObject::setVisible(bool visible)
{
    if(visible&&this->scene()!=stats->scene()) {
        stats->scene()->addItem(this);
    }
    QGraphicsItem::setVisible(visible);
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
