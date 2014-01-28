#include "helmet.h"

#include <configuration/configurationprovider.h>

Helmet::Helmet()
{
}

Helmet::Helmet(const Helmet &helmet)
{
    className=helmet.className;
    Json::Value config=(*ConfigurationProvider::getConfig("config/items.json"))[className];
    loadFromJson(config);
}
