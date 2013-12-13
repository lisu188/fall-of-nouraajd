#include "item.h"

#include <map/tiles/tile.h>

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
    singleUse=false;
    this->setZValue(1);
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
    std::string path=name;
    path="config/items/"+path+".json";
    std::string type=ConfigurationProvider::getConfig(path)->get("type","").asString();
    if(type.compare("weapon")==0)
    {
        return new Weapon(path.c_str());
    } else if(type.compare("armor")==0) {
        return new Armor(path.c_str());
    }
    else if(type.compare("potion")==0) {
        return new Potion(path.c_str());
    } else
    {
        throw type;
    }
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

void Item::initializeFromFile(const char *path)
{
    Json::Value *config=ConfigurationProvider::getConfig(path);
    bonus.init((*config)["bonus"]);
    interaction=Interaction::getInteraction(config->get("interaction","").asString());
    setAnimation(config->get("path","").asCString());
    className=config->get("name","").asCString();
    power=config->get("power",1).asInt();
}
