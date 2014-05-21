#include "belt.h"
#include <configuration/configurationprovider.h>
Belt::Belt()
{
}

Belt::Belt(const Belt &belt)
{
    className=belt.className;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[className];
    loadFromJson(config);
}
