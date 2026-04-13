#include "item.h"

#include <map/tiles/tile.h>

#include <view/gamescene.h>
#include <stats/stats.h>
#include <QDebug>

Item::Item()
{
    className="Item";
    singleUse=false;
    this->setZValue(1);
}

Item::~Item()
{
    if(bonus)delete bonus;
}

void Item::setPos(QPointF point)
{
    ListItem::setPos(point);
}

void Item::onEquip(Creature *creature)
{
    if(!bonus)return;
    creature->getStats()->addBonus(bonus);
    qDebug() << creature->className.c_str()<<"equipped"<<className.c_str();
}

void Item::onUnequip(Creature *creature)
{
    if(!bonus)return;
    creature->getStats()->removeBonus(bonus);
    qDebug() << creature->className.c_str()<<"unequipped"<<className.c_str();
}

void Item::setAnimation(std::string path)
{
    AnimatedObject::setAnimation(path);
}

void Item::mousePressEvent(QGraphicsSceneMouseEvent *event)
{
    onUse(GameScene::getPlayer());
    if(singleUse)
    {
        GameScene::getPlayer()->loseItem(this);
        delete this;
    }
}
