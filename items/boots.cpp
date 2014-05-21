#include "boots.h"

#include <configuration/configurationprovider.h>

Boots::Boots() {
}

Boots::Boots(const Boots &boots) {
	className = boots.className;
	Json::Value config =
			(*ConfigurationProvider::getConfig("config/items.json"))[className];
	loadFromJson(config);
}
