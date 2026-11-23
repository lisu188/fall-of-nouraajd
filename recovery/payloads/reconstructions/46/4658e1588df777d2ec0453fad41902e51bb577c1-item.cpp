#include "item.h"
#include <src/gamescene.h>
#include <src/itemslot.h>
#include <src/stats.h>
#include <QDebug>
#include <QDrag>
#include <lib/json/json.h>
#include <fstream>
#include <src/interaction.h>
#include <src/potion.h>
#include <src/configurationprovider.h>
#include <src/player.h>
#include <src/gameview.h>

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

bool Item::isSingleUse() {
    return singleUse;
}

void Item::onEquip(Creature *creature)
{
    creature->getStats()->addBonus(bonus);
    qDebug() << creature->typeName.c_str()<<"equipped"<<typeName.c_str()<<"\n";
}

void Item::onUnequip(Creature *creature)
{
    creature->getStats()->removeBonus(bonus);
    qDebug() << creature->typeName.c_str()<<"unequipped"<<typeName.c_str()<<"\n";
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
        item->loadFromJson(name);
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

void Item::loadFromJson(std::string name)
{
    this->typeName=name;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[name];
    bonus.loadFromJson(config["bonus"]);
    interaction=Interaction::getInteraction(config.get("interaction","").asString());
    setAnimation(config.get("path","").asCString());
    power=config.get("power",1).asInt();
    singleUse=config.get("singleUse",false).asBool();
    tooltip=config.get("tooltip","").asString();
    slot=config.get("slot",0).asInt();
    if(tooltip.compare("")==0) {
        tooltip=typeName;
    }
}

Armor::Armor()
{
}

Armor::Armor(const Armor &)
{
}

Armor::Armor(std::string name)
{
    loadFromJson(name);
}

Interaction *Armor::getInteraction() {
    return interaction;
}

Belt::Belt()
{
}

Belt::Belt(const Belt &)
{
}

Helmet::Helmet()
{
}

Helmet::Helmet(const Helmet &)
{
}

Boots::Boots()
{
}

Boots::Boots(const Boots &)
{
}

Gloves::Gloves()
{
}

Gloves::Gloves(const Gloves &)
{
}

Weapon::Weapon()
{
}

Weapon::Weapon(const Weapon &)
{
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

SmallWeapon::SmallWeapon(const SmallWeapon &)
{
}

void Item::onMove()
{
}

