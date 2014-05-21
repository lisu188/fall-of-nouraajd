#include "gloves.h"
#include <configuration/configurationprovider.h>
Gloves::Gloves()
{
}

Gloves::Gloves(const Gloves &gloves)
{
    className=gloves.className;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[className];
    loadFromJson(config);
}
