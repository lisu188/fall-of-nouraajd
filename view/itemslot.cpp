#include "itemslot.h"
#include <map/map.h>
#include <QGraphicsSceneDragDropEvent>
#include <qpainter.h>
#include <configuration/configurationprovider.h>
#include <creatures/creature.h>
#include <util/patch.h>

ItemSlot::ItemSlot(int number):number(number)
{
    pixmap.load(":/images/item.png");//change to slot items path in json
    pixmap=pixmap.scaled(Map::getTileSize(),Map::getTileSize(),
                         Qt::IgnoreAspectRatio,Qt::SmoothTransformation);
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
    bool inherits=false;
    if(widget)
    {
        Json::Value config=(*ConfigurationProvider::
                            getConfig("config/slots.json"))
                           [patch::to_string(slot).c_str()]["types"];
        for(int i=0; i<config.size(); i++)
        {
            inherits=inherits||widget->inherits(config[i].asCString());
            if(inherits) {
                break;
            }
        }
    }
    return inherits;
}

void ItemSlot::dragMoveEvent(QGraphicsSceneDragDropEvent *event)
{
    setAcceptDrops(checkType(number,event->source()));
}

void ItemSlot::dropEvent(QGraphicsSceneDragDropEvent *event)
{
}
