#include "smallweapon.h"

#include <configuration/configurationprovider.h>

SmallWeapon::SmallWeapon()
{
}

SmallWeapon::SmallWeapon(const SmallWeapon &weapon)
{
    className=weapon.className;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[className];
    loadFromJson(config);
}
