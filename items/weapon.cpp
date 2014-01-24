#include "weapon.h"

#include <view/gamescene.h>
#include <creatures/player.h>
#include <view/gameview.h>
#include <configuration/configurationprovider.h>


Weapon::Weapon()
{
}

Weapon::Weapon(std::string name)
{
    className=name;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[name];
    loadFromJson(config);
}

Weapon::Weapon(const Weapon &weapon):Weapon(weapon.className)
{
}

Interaction *Weapon::getInteraction() {
    return interaction;
}

Stats *Weapon::getStats() {
    return &bonus;
}

void Weapon::onUse(Creature *creature)
{
    creature->setWeapon(this);
}


