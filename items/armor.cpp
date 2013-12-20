#include "armor.h"

#include <view/gamescene.h>

#include <configuration/configurationprovider.h>

Armor::Armor(std::string name)
{
    className=name;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[name];
    loadFromJson(config);
}

Interaction *Armor::getInteraction() {
    return interaction;
}

void Armor::onUse(Creature *creature)
{
    creature->setArmor(this);
}
