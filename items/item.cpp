#include "item.h"

#include <view/gamescene.h>
#include <stats/stats.h>
#include <QDebug>
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
    AnimatedObject::setAnimation(path);
}

void Item::mousePressEvent(QGraphicsSceneMouseEvent *event)
{
    if(event->button()==Qt::MouseButton::RightButton)
    {
        ListItem::mousePressEvent(event);
    }
    else
    {
        onUse(GameScene::getPlayer());
        if(singleUse)
        {
            GameScene::getPlayer()->loseItem(this);
            delete this;
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
