#include "potion.h"
#include <QDebug>
#include <src/configurationprovider.h>
#include <src/creature.h>
#include <src/gamescene.h>

Potion::Potion()
{
}

Potion::Potion(const Potion &potion)
{
    typeName = potion.typeName;
    Json::Value config = (*ConfigurationProvider::getConfig("config/items.json"))[typeName];
    loadFromJson(config);
}

void Potion::onUse(Creature *creature)
{
    qDebug() << creature->typeName.c_str() << "used" << typeName.c_str();
    effect(creature, power);
}

void Potion::loadFromJson(Json::Value config)
{
    Item::loadFromJson(config);
    if ((std::string(typeName).find("LifePotion") != std::string::npos)) {
        effect = &LifeEffect;
    } else if (std::string(typeName).find("ManaPotion") != std::string::npos) {
        effect = &ManaEffect;
    }
}

void LifeEffect(Creature *creature, int power)
{
    creature->healProc(power * 20);
}

void ManaEffect(Creature *creature, int power)
{
    creature->addManaProc(power * 20);
}
