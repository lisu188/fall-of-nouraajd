#include "gamescene.h"
#include "itemslot.h"
#include <map/map.h>
#include <QGraphicsSceneDragDropEvent>
#include <qpainter.h>
#include <configuration/configurationprovider.h>
#include <creatures/creature.h>
#include <util/patch.h>

ItemSlot::ItemSlot(int number, std::map<int, Item *> *equipped):number(number),equipped(equipped)
{
    pixmap.load(":/images/item.png");//change to slot items path in json
    pixmap=pixmap.scaled(Map::getTileSize(),Map::getTileSize(),
                         Qt::IgnoreAspectRatio,Qt::SmoothTransformation);
    this->setAcceptDrops(true);
}

QRectF ItemSlot::boundingRect() const
{
    return QRectF(0,0,Map::getTileSize(),Map::getTileSize());
}

void ItemSlot::paint(QPainter *painter, const QStyleOptionGraphicsItem *, QWidget *)
{
    painter->drawPixmap(0,0,pixmap);
}

bool ItemSlot::checkType(int slot,QWidget *widget)
{
    if(widget)
    {
        Json::Value config=(*ConfigurationProvider::
                            getConfig("config/slots.json"))
                           [patch::to_string(slot).c_str()]["types"];
        for(int i=0; i<config.size(); i++)
        {
            if(widget->inherits(config[i].asCString())) {
                return true;
            }
        }
    }
    return false;
}

void ItemSlot::update()
{
    Item *item=equipped->at(number);
    if(item)
    {
        item->setParentItem(this);
        item->setPos(0,0);
        item->setVisible(true);
        item->QGraphicsItem::update();
    }
    QGraphicsObject::update();
}

void ItemSlot::dragMoveEvent(QGraphicsSceneDragDropEvent *event)
{
    QGraphicsObject::dragMoveEvent(event);
    event->setAccepted(checkType(number,event->source()));
}

void ItemSlot::dropEvent(QGraphicsSceneDragDropEvent *event)
{
    QGraphicsObject::dropEvent(event);
    if(checkType(number,event->source()))
    {
        GameScene::getPlayer()->setItem(number,(Item*)event->source());
    }
    event->acceptProposedAction();
    event->accept();
}
