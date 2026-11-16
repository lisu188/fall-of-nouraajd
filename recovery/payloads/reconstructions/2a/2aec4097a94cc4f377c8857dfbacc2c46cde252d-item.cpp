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
        Json::Value config;
        item->typeName=name;
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
    config=(*ConfigurationProvider::getConfig("config/items.json"))[typeName];
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

// ---- formerly armor.cpp ----
Armor::Armor()
{
}

Armor::Armor(const Armor &armor)
{
    typeName=armor.typeName;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[typeName];
    loadFromJson(config);
}

Armor::Armor(std::string name)
{
    typeName=name;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[name];
    loadFromJson(config);
}

Interaction *Armor::getInteraction() {
    return interaction;
}

// ---- formerly belt.cpp ----
Belt::Belt()
{
}

Belt::Belt(const Belt &belt)
{
    typeName=belt.typeName;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[typeName];
    loadFromJson(config);
}

// ---- formerly boots.cpp ----
Boots::Boots()
{
}

Boots::Boots(const Boots &boots)
{
    typeName=boots.typeName;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[typeName];
    loadFromJson(config);
}

// ---- formerly gloves.cpp ----
Gloves::Gloves()
{
}

Gloves::Gloves(const Gloves &gloves)
{
    typeName=gloves.typeName;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[typeName];
    loadFromJson(config);
}

// ---- formerly helmet.cpp ----
Helmet::Helmet()
{
}

Helmet::Helmet(const Helmet &helmet)
{
    typeName=helmet.typeName;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[typeName];
    loadFromJson(config);
}

// ---- formerly smallweapon.cpp ----
SmallWeapon::SmallWeapon()
{
}

SmallWeapon::SmallWeapon(const SmallWeapon &weapon)
{
    typeName=weapon.typeName;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[typeName];
    loadFromJson(config);
}

// ---- formerly weapon.cpp ----
Weapon::Weapon()
{
}

Weapon::Weapon(const Weapon &weapon)
{
    typeName=weapon.typeName;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[typeName];
    loadFromJson(config);
}

Interaction *Weapon::getInteraction() {
    return interaction;
}

Stats *Weapon::getStats() {
    return &bonus;
}

// ---- members this commit's item.h adds ----
void Item::onMove()
{
}

void Item::loadFromProps(Tmx::PropertySet props)
{
    std::string name = props.GetLiteralProperty("type");
    typeName = name;
    Json::Value config = (*ConfigurationProvider::getConfig("config/items.json"))[name];
    loadFromJson(config);
}
