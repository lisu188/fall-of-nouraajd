#include "dungeon.h"

#include <view/gamescene.h>

Dungeon::Dungeon() {
	className = "Dungeon";
	this->setAnimation("images/buildings/dungeon/");
}

Dungeon::Dungeon(const Dungeon &dungeon)
		: Dungeon() {
	this->moveTo(dungeon.getPosX(), dungeon.getPosY(), dungeon.getPosZ());
	exit = Coords(getExit());
}

void Dungeon::onEnter() {
	GameScene::getPlayer()->moveTo(exit.x, exit.y, exit.z, true);
	map->move(0, 0);
}

void Dungeon::onMove() {
}

bool Dungeon::canSave() {
	return true;
}

Json::Value Dungeon::saveToJson() {
	Json::Value config;
	config[(unsigned int) 0] = getPosX();
	config[(unsigned int) 1] = getPosY();
	config[(unsigned int) 2] = getPosZ();
	config[(unsigned int) 3] = exit.x;
	config[(unsigned int) 4] = exit.y;
	config[(unsigned int) 5] = exit.z;
	return config;
}

void Dungeon::loadFromJson(Json::Value config) {
	int x = config[(unsigned int) 0].asInt();
	int y = config[(unsigned int) 1].asInt();
	int z = config[(unsigned int) 2].asInt();
	this->moveTo(x, y, z, true);
	x = config[(unsigned int) 3].asInt();
	y = config[(unsigned int) 4].asInt();
	z = config[(unsigned int) 5].asInt();
	exit = Coords(x, y, z);
}

Coords Dungeon::getExit() const {
	return exit;
}
