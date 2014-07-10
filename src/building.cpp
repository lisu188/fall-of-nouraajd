#include "building.h"
#include <QDebug>
#include <src/gamescene.h>
#include <src/playerstatsview.h>
#include <src/monster.h>
#include <src/configurationprovider.h>
#include <src/scriptmanager.h>

Building *Building::createBuilding(QString name) {
  return dynamic_cast<Building *>(MapObject::createMapObject(name));
}

Building::Building() : MapObject(0, 0, 0, 2) {}

Building::Building(const Building &) {}

void Building::onEnter() {
    map->getEngine()->executeCommand({this->typeName+".onEnter",this->name});

}

void Building::onMove() {
    map->getEngine()->executeCommand({this->typeName+".onMove",this->name});
}

void Building::onCreate()
{
    map->getEngine()->executeScript(QString("import ").append(this->typeName.c_str()));
    map->getEngine()->executeCommand({this->typeName+".onCreate",this->name});
}

void Building::onDestroy()
{
    map->getEngine()->executeCommand({this->typeName+".onDestroy",this->name});
}

void Building::loadFromJson(std::string name) {
  this->typeName = name;
  Json::Value config =
      (*ConfigurationProvider::getConfig("config/object.json"))[name];
  this->setAnimation(config.get("animation", "").asString());
}

bool Building::isEnabled() { return enabled; }

void Building::setEnabled(bool enabled) { this->enabled = enabled; }

