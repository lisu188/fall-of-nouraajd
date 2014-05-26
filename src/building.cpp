#include "building.h"
#include <QDebug>
#include <src/gamescene.h>
#include <src/playerstatsview.h>
#include <src/monster.h>
#include <src/configurationprovider.h>

Building *Building::getBuilding(std::string name)
{
    Building * building = NULL;
    Json::Value config = (*ConfigurationProvider::getConfig("config/buildings.json"))[name];
    if (config.isNull()) {
        return NULL;
    }
    std::string className = config.get("class", "").asString();
    int typeId = QMetaType::type(className.c_str());
    if (typeId == 0)return NULL;
    building = (Building*)QMetaType::create(typeId);
    building->loadFromJson(name);
    return building;
}

Building::Building()
{

}

Building::Building(const Building &)
{
}

void Building::onEnter()
{
    qDebug() << "Entered" << typeName.c_str() << "\n";
}

void Building::onMove()
{
}

void Building::loadFromJson(std::string name)
{
    this->typeName = name;
    Json::Value config = (*ConfigurationProvider::getConfig("config/buildings.json"))[name];
    this->setAnimation(config.get("path", "").asString());
}

Cave::Cave()
{
}

Cave::Cave(const Cave &cave)
{

}

void Cave::onEnter()
{
    Building::onEnter();
    if (enabled) {
        enabled = false;
        for (int i = -1; i < 2; i++)
            for (int j = -1; j < 2; j++) {
                if (j == 0 && i == 0) {
                    continue;
                }
                Monster *monster = (Monster*)Creature::getCreature(this->monster);
                map->addObject(monster);
                monster->moveTo(getPosX() + 1 * i, getPosY() + 1 * j, getPosZ(), true);
            }
        this->removeFromGame();
    }
}

void Cave::onMove()
{
    if (enabled && ((rand() % 100) < chance)) {
        Monster *monster = (Monster*)Creature::getCreature(this->monster);
        map->addObject(monster);
        monster->moveTo(getPosX(), getPosY(), getPosZ(), true);
    }
}

void Cave::loadFromProps(Tmx::PropertySet set)
{
    if (set.HasProperty("monster")) {
        monster = set.GetLiteralProperty("monster");
    }
    if (set.HasProperty("chance")) {
        chance = set.GetNumericProperty("chance");
    }
}

Teleporter::Teleporter()
{
}

Teleporter::Teleporter(const Teleporter &teleporter): Teleporter()
{
}

void Teleporter::onEnter()
{
    if (!enabled)return;
    std::set<MapObject*> *objects = this->getMap()->getObjects();
    std::set<MapObject*>::iterator it;
    std::vector<Teleporter*> teleporters;
    for (it = objects->begin(); it != objects->end(); it++) {
        if ((*it)->inherits("Teleporter")) {
            teleporters.push_back((Teleporter*)(*it));
        }
    }
    if (teleporters.size() > 1) {
        Teleporter *teleporter;
        do {
            teleporter = teleporters[rand() % teleporters.size()];
        } while (teleporter == this);
        GameScene::getPlayer()->moveTo(teleporter->getPosX(), teleporter->getPosY(), teleporter->getPosZ(), true);
        map->move(0, 0);
    }
}

void Teleporter::onMove()
{
}

void Teleporter::loadFromProps(Tmx::PropertySet set)
{
    if (set.HasProperty("enabled")) {
        enabled = (set.GetLiteralProperty("enabled").compare("true") == 0);
    }
}
