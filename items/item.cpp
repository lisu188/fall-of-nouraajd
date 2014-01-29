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

Item::Item(const Item &)
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

Item *Item::getItem(std::string name)
{
    Item *item=0;
    if(std::string(name).compare("")==0) {
        return item;
    }
    std::string Class=
        (*ConfigurationProvider::getConfig("config/items.json"))
        [name].get("class","").asString();
    int id=QMetaType::type(Class.c_str());
    item=(Item*)QMetaType::create(id);
    if(item) {
        Json::Value config;
        item->className=name;
        item->loadFromJson(config);
    }
    return item;
}

void Item::onUse(Creature *)
{
}

void Item::mousePressEvent(QGraphicsSceneMouseEvent *event)
{
    if(GameScene::getPlayer()&&!GameScene::getPlayer()->hasItem(this))
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
        AnimatedObject::mousePressEvent(event);
    }
}

void Item::loadFromJson(Json::Value config)
{
    this->moveTo(config.isNull()?0:config[(unsigned int)0].asInt(),
                 config.isNull()?0:config[(unsigned int)1].asInt(),
                 config.isNull()?0:config[(unsigned int)2].asInt()
                 ,true);
    config=(*ConfigurationProvider::getConfig("config/items.json"))[className];
    bonus.loadFromJson(config["bonus"]);
    interaction=Interaction::getInteraction(config.get("interaction","").asString());
    setAnimation(config.get("path","").asCString());
    power=config.get("power",1).asInt();
    singleUse=config.get("singleUse",false).asBool();
    tooltip=config.get("tooltip","").asString();
    slot=config.get("slot",0).asInt();
    if(tooltip.compare("")==0) {
        tooltip=className;
    }
}
