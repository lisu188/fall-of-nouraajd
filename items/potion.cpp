#include "potion.h"
#include <QDebug>
#include <configuration/configurationprovider.h>
#include <creatures/creature.h>
#include <view/gamescene.h>

Potion::Potion()
{
}

Potion::Potion(const Potion &potion)
{
    className=potion.className;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[className];
    loadFromJson(config);
}

void Potion::onUse(Creature *creature)
{
    qDebug() << creature->className.c_str() << "used" << className.c_str();
    effect(creature,power);
}

void Potion::loadFromJson(Json::Value config)
{
    Item::loadFromJson(config);
    if((std::string(className).find("LifePotion") != std::string::npos))
    {
        effect=&LifeEffect;
    } else if(std::string(className).find("ManaPotion") != std::string::npos) {
        effect=&ManaEffect;
    }
}

void LifeEffect(Creature *creature,int power)
{
    creature->healProc(power*20);
}

void ManaEffect(Creature *creature,int power)
{
    creature->addManaProc(power*20);
}
