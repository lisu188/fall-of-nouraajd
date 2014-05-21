#include "teleporter.h"

#include <view/gamescene.h>

Teleporter::Teleporter() {
	className = "Teleporter";
	this->setAnimation("images/buildings/teleporter/");
}

Teleporter::Teleporter(const Teleporter &teleporter)
		: Teleporter() {
	this->moveTo(teleporter.getPosX(), teleporter.getPosY(),
<<<<<<< HEAD
	        teleporter.getPosZ());
}

void Teleporter::onEnter() {
	if (!enabled)
		return;
	std::set<MapObject*> *objects = this->getMap()->getObjects();
	std::set<MapObject*>::iterator it;
	std::vector<Teleporter*> teleporters;
	for (it = objects->begin(); it != objects->end(); it++) {
		if ((*it)->inherits("Teleporter")) {
			teleporters.push_back((Teleporter*) (*it));
		}
	}
	if (teleporters.size() > 1) {
		Teleporter *teleporter;
		do {
			teleporter = teleporters[rand() % teleporters.size()];
		}
		while (teleporter == this);
		GameScene::getPlayer()->moveTo(teleporter->getPosX(),
		        teleporter->getPosY(), teleporter->getPosZ(), true);
=======
			teleporter.getPosZ());
}

void Teleporter::onEnter() {
	if (!enabled)
		return;
	std::set<MapObject*> *objects = this->getMap()->getObjects();
	std::set<MapObject*>::iterator it;
	std::vector<Teleporter*> teleporters;
	for (it = objects->begin(); it != objects->end(); it++) {
		if ((*it)->inherits("Teleporter")) {
			teleporters.push_back((Teleporter*) (*it));
		}
	}
	if (teleporters.size() > 1) {
		Teleporter *teleporter;
		do {
			teleporter = teleporters[rand() % teleporters.size()];
		}
		while (teleporter == this);
		GameScene::getPlayer()->moveTo(teleporter->getPosX(),
				teleporter->getPosY(), teleporter->getPosZ(), true);
>>>>>>> refs/remotes/origin/master
		map->move(0, 0);
	}
}

void Teleporter::onMove() {
}

bool Teleporter::canSave() {
	return true;
}

Json::Value Teleporter::saveToJson() {
	Json::Value config;
	config[(unsigned int) 0] = getPosX();
	config[(unsigned int) 1] = getPosY();
	config[(unsigned int) 2] = getPosZ();
	config["enabled"] = enabled;
	return config;
}

void Teleporter::loadFromJson(Json::Value config) {
	int x = config[(unsigned int) 0].asInt();
	int y = config[(unsigned int) 1].asInt();
	int z = config[(unsigned int) 2].asInt();
	enabled = config["enabled"].asBool();
	this->moveTo(x, y, z, true);
}

void Teleporter::loadFromProps(Tmx::PropertySet set) {
	enabled = (set.GetLiteralProperty("enabled").compare("true") == 0);
}
