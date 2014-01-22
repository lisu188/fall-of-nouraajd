#include "item.h"

#include <view/gamescene.h>
#include <stats/stats.h>
#include <QDebug>
#include <QDrag>
#include <json/json.h>
#include <items/armor.h>
#include <fstream>
#include <items/weapon.h>
#include <interactions/interaction.h>
#include <items/potion.h>
#include <configuration/configurationprovider.h>

Item::Item()
{
    this->setZValue(1);
}

void Item::onEnter()
{
    this->getMap()->removeObject(this);
    GameScene::getPlayer()->addItem(this);
}

Json::Value Item::saveToJson()
{
    Json::Value config;
    config[(unsigned int)0]=getPosX();
    config[(unsigned int)1]=getPosY();
    config[(unsigned int)2]=getPosZ();
    return config;
}

bool Item::canSave()
{
    return true;
}

bool Item::isSingleUse() {
    return singleUse;
}

void Item::setPos(QPointF point)
{
    ListItem::setVisible(true);
    ListItem::setPos(point);
}

void Item::onEquip(Creature *creature)
{
    creature->getStats()->addBonus(bonus);
    qDebug() << creature->className.c_str()<<"equipped"<<className.c_str()<<"\n";
}

void Item::onUnequip(Creature *creature)
{
    creature->getStats()->removeBonus(bonus);
    qDebug() << creature->className.c_str()<<"unequipped"<<className.c_str()<<"\n";
}

Item *Item::getItem(const char *name)
{
    Item *item=0;
    if(std::string(name).compare("")==0) {
        return item;
    }
    std::string type=
        (*ConfigurationProvider::getConfig("config/items.json"))
        [name].get("type","").asString();;
    if(type.compare("weapon")==0)
    {
        item=new Weapon(name);
    } else if(type.compare("armor")==0) {
        item =new Armor(name);
    }
    else if(type.compare("potion")==0) {
        item =new Potion(name);
    } else
    {
        item=0;
    }
    return item;
}

void Item::setAnimation(std::string path)
{
    MapObject::setAnimation(path);
}

void Item::mousePressEvent(QGraphicsSceneMouseEvent *event)
{
    if(GameScene::getPlayer()&&
            GameScene::getPlayer()->getInventory()->find(this)
            ==GameScene::getPlayer()->getInventory()->end()&&
            GameScene::getPlayer()->getEquipped()->find(this)
            ==GameScene::getPlayer()->getEquipped()->end())
    {
        return;
    }
    if(singleUse&&GameScene::getPlayer())
    {
        GameScene::getPlayer()->loseItem(this);
        onUse(GameScene::getPlayer());
        delete this;
    }
    else
    {
        QGraphicsItem *parent=this->parentItem();
        if(parent) {
            parent->setAcceptDrops(false);
        }
        AnimatedObject::mousePressEvent(event);
        if(parent) {
            parent->setAcceptDrops(true);
        }
    }
}

void Item::loadFromJson(Json::Value config)
{
    bonus.loadFromJson(config["bonus"]);
    interaction=Interaction::getInteraction(config.get("interaction","").asString());
    setAnimation(config.get("path","").asCString());
    power=config.get("power",1).asInt();
    singleUse=config.get("singleUse",false).asBool();
    tooltip=config.get("tooltip","").asString();
    if(tooltip.compare("")==0) {
        tooltip=className;
    }
}
