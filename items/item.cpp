#include "item.h"

#include <map/tiles/tile.h>

#include <view/gamescene.h>
#include <stats/stats.h>
#include <QDebug>
#include <json/json.h>
#include <fstream>
#include <interactions/interaction.h>

Item::Item()
{
    className="Item";
    singleUse=false;
    this->setZValue(1);
    interaction=0;
}

bool Item::isSingleUse() {
    return singleUse;
}

void Item::setPos(QPointF point)
{
    ListItem::setPos(point);
}

void Item::onEquip(Creature *creature)
{
    creature->getStats()->addBonus(&bonus);
    qDebug() << creature->className.c_str()<<"equipped"<<className.c_str();
}

void Item::onUnequip(Creature *creature)
{
    creature->getStats()->removeBonus(&bonus);
    qDebug() << creature->className.c_str()<<"unequipped"<<className.c_str();
}

Item *Item::getItem(char *name)
{
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

void Item::initializeFromFile(char *path)
{
    std::fstream jsonFileStream;
    jsonFileStream.open (path);
    if(!jsonFileStream.is_open()) {
        jsonFileStream.open((std::string("assets:/")+path).c_str());
    }
    Json::Value config;
    Json::Reader reader;
    reader.parse( jsonFileStream, config );
    jsonFileStream.close();
    bonus.init(config["bonus"]);
    interaction=Interaction::getAction(config.get("interaction","").asString());
    setAnimation(config.get("path","").asCString());
    className=config.get("name","").asCString();
}
