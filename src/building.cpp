#include "building.h"
#include <QDebug>
#include <src/gamescene.h>
#include <src/playerstatsview.h>
#include <src/monster.h>
#include <src/configurationprovider.h>
#include <src/scriptmanager.h>

Building::Building() : MapObject(0, 0, 0, 2) {}

Building::Building(const Building &) {}

void Building::onEnter() {

}

void Building::onMove() {

}

void Building::onCreate()
{

}

void Building::onDestroy()
{

}

void Building::loadFromJson(std::string name) {
  this->typeName = name;
  Json::Value config =
      (*ConfigurationProvider::getConfig("config/object.json"))[name];
  this->setAnimation(config.get("animation", "").asString());
}

bool Building::isEnabled() { return enabled; }

void Building::setEnabled(bool enabled) { this->enabled = enabled; }

