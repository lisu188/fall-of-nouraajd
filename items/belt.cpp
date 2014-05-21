#include "belt.h"
#include <configuration/configurationprovider.h>
Belt::Belt() {
}

Belt::Belt(const Belt &belt) {
	className = belt.className;
	Json::Value config =
<<<<<<< HEAD
	        (*ConfigurationProvider::getConfig("config/items.json"))[className];
=======
			(*ConfigurationProvider::getConfig("config/items.json"))[className];
>>>>>>> refs/remotes/origin/master
	loadFromJson(config);
}
