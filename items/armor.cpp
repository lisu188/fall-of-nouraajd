#include "armor.h"

#include <view/gamescene.h>

#include <configuration/configurationprovider.h>

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
