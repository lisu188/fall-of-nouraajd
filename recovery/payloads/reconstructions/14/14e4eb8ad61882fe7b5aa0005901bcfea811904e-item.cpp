#include "item.h"
#include <src/view/gamescene.h>
#include <src/view/itemslot.h>
#include <src/stats/stats.h>
#include <QDebug>
#include <QDrag>
#include <lib/json/json.h>
#include <fstream>
#include <src/interactions/interaction.h>
#include <src/items/potion.h>
#include <src/configuration/configurationprovider.h>
#include <src/creatures/player.h>
#include <src/view/gameview.h>

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

void Item::onUse(Creature *creature)
{
    ItemSlot *parent=(ItemSlot *)this->parentItem();
    if(!parent)
    {
        qDebug()<<"Parentless item dropped";
        return;
    }
    int slot=parent->getNumber();
    creature->setItem(slot,this);
}

void Item::mousePressEvent(QGraphicsSceneMouseEvent *event)
{
    if(singleUse&&GameScene::getPlayer())
    {
        GameScene::getPlayer()->loseItem(this);
        onUse(GameScene::getPlayer());
        delete this;
        return;
    }
    ListItem::mousePressEvent(event);
    if(event->isAccepted()) {
        return;
    }
    if(GameScene::getPlayer()&&!GameScene::getPlayer()->hasItem(this))
    {
        return;
    }
        QGraphicsObject *parent=this->parentObject();
        if(parent) {
            parent->setAcceptDrops(false);
        }
        AnimatedObject::mousePressEvent(event);
        if(parent) {
            parent->setAcceptDrops(true);
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

Armor::Armor()
{
}

Armor::Armor(const Armor &armor)
{
    className=armor.className;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[className];
    loadFromJson(config);
}

Armor::Armor(std::string name)
{
    className=name;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[name];
    loadFromJson(config);
}

Interaction *Armor::getInteraction() {
    return interaction;
}

Belt::Belt()
{
}

Belt::Belt(const Belt &belt)
{
    className=belt.className;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[className];
    loadFromJson(config);
}

Helmet::Helmet()
{
}

Helmet::Helmet(const Helmet &helmet)
{
    className=helmet.className;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[className];
    loadFromJson(config);
}

Boots::Boots()
{
}

Boots::Boots(const Boots &boots)
{
    className=boots.className;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[className];
    loadFromJson(config);
}

Gloves::Gloves()
{
}

Gloves::Gloves(const Gloves &gloves)
{
    className=gloves.className;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[className];
    loadFromJson(config);
}

Weapon::Weapon()
{
}

Weapon::Weapon(const Weapon &weapon)
{
    className=weapon.className;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[className];
    loadFromJson(config);
}

Interaction *Weapon::getInteraction() {
    return interaction;
}

Stats *Weapon::getStats() {
    return &bonus;
}

SmallWeapon::SmallWeapon()
{
}

SmallWeapon::SmallWeapon(const SmallWeapon &weapon)
{
    className=weapon.className;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[className];
    loadFromJson(config);
}

void Item::onMove()
{
}

void Item::loadFromProps(Tmx::PropertySet)
{
}
