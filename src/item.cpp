#include "item.h"

#include <src/gamescene.h>
#include <src/itemslot.h>
#include <src/stats.h>
#include <QDebug>
#include <QDrag>
#include <lib/json/json.h>
#include <src/item.h>
#include <fstream>
#include <src/interaction.h>
#include <src/potion.h>
#include <src/configurationprovider.h>

Item::Item(): ListItem(0, 0, 0, 2)
{

}

Item::Item(const Item &item): Item()
{
    this->loadFromJson(item.name);
}

void Item::onEnter()
{
    this->getMap()->removeObject(this);
    GameScene::getPlayer()->addItem(this);
}

void Item::onMove()
{

}

bool Item::isSingleUse()
{
    return singleUse;
}

void Item::setSingleUse(bool singleUse){
    this->singleUse=singleUse;
}

void Item::onEquip(Creature *creature)
{
    creature->getStats()->addBonus(bonus);
    qDebug() << creature->typeName.c_str() << "equipped" << typeName.c_str() << "\n";
}

void Item::onUnequip(Creature *creature)
{
    creature->getStats()->removeBonus(bonus);
    qDebug() << creature->typeName.c_str() << "unequipped" << typeName.c_str() << "\n";
}

Item *Item::createItem(std::string name)
{
    return dynamic_cast<Item*>(MapObject::createMapObject(name));
}

void Item::onUse(Creature *creature)
{
    ItemSlot *parent = (ItemSlot *)this->parentItem();
    if (!parent) {
        qDebug() << "Parentless item dropped";
        return;
    }
    int slot = parent->getNumber();
    creature->setItem(slot, this);
}

void Item::mousePressEvent(QGraphicsSceneMouseEvent *event)
{
    if (singleUse && GameScene::getPlayer()) {
        GameScene::getPlayer()->loseItem(this);
        onUse(GameScene::getPlayer());
        delete this;
        return;
    }
    ListItem::mousePressEvent(event);
    if (event->isAccepted()) {
        return;
    }
    if (GameScene::getPlayer() && !GameScene::getPlayer()->hasItem(this)) {
        return;
    }
    QGraphicsObject *parent = this->parentObject();
    if (parent) {
        parent->setAcceptDrops(false);
    }
    AnimatedObject::mousePressEvent(event);
    if (parent) {
        parent->setAcceptDrops(true);
    }
}

void Item::loadFromJson(std::string name)
{
    this->typeName = name;
    Json::Value config = (*ConfigurationProvider::getConfig("config/object.json"))[typeName];
    bonus.loadFromJson(config["bonus"]);
    interaction = Interaction::getInteraction(config.get("interaction", "").asString());
    setAnimation(config.get("path", "").asCString());
    power = config.get("power", 1).asInt();
    singleUse = config.get("singleUse", false).asBool();
    tooltip = config.get("tooltip", "").asString();
    slot = config.get("slot", 0).asInt();
    if (tooltip.compare("") == 0) {
        tooltip = typeName;
    }
}
int Item::getPower() const
{
    return power;
}

void Item::setPower(int value)
{
    power = value;
}


Armor::Armor()
{
}

Armor::Armor(const Armor &armor)
{

}

Interaction *Armor::getInteraction()
{
    return interaction;
}

Belt::Belt()
{
}

Belt::Belt(const Belt &belt)
{

}

Boots::Boots()
{
}

Boots::Boots(const Boots &boots)
{

}

Gloves::Gloves()
{

}

Gloves::Gloves(const Gloves &gloves)
{

}

Helmet::Helmet()
{
}

Helmet::Helmet(const Helmet &helmet)
{

}

SmallWeapon::SmallWeapon()
{

}

SmallWeapon::SmallWeapon(const SmallWeapon &weapon)
{

}

Weapon::Weapon(): Item()
{
}

Weapon::Weapon(const Weapon &weapon)
{

}

Interaction *Weapon::getInteraction()
{
    return interaction;
}

Stats *Weapon::getStats()
{
    return &bonus;
}
