#include "weapon.h"

#include <view/gamescene.h>
#include <creatures/player.h>
#include <view/gameview.h>
#include <configuration/configurationprovider.h>


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
