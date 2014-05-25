#include "monster.h"

#include <src/view/gamescene.h>

#include <src/items/lootprovider.h>

#include <src/pathfinder/dumbpathfinder.h>
#include <src/pathfinder/randompathfinder.h>
#include <src/pathfinder/smartpathfinder.h>
#include <QDebug>
#include <src/configuration/configurationprovider.h>

Monster::Monster(std::string name, Json::Value config): Creature(name, config)
{
}

Monster::Monster(std::string name): Creature(name)
{
}

Monster::Monster(): Creature()
{
}

Monster::Monster(const Monster &monster): Monster(monster.className)
{
}

void Monster::onMove()
{
    if (!isAlive()) {
        return;
    }
    PathFinder *finder;
    if ((this->getCoords().getDist(GameScene::getPlayer()->getCoords())) < 25) {
        finder = new SmartPathFinder();
    } else {
        finder = new RandomPathFinder();
    }
    Coords path = finder->findPath(this->getCoords(), GameScene::getPlayer()->getCoords());
    delete finder;
    move(path.x, path.y);
    /*
    if(rand()%20==0) {
        onMove();
    }
    */
    this->addExp(rand() % 25);
}

void Monster::onEnter()
{
    if (!isAlive()) {
        return;
    }
    GameScene::getPlayer()->addToFightList(this);
}

void Monster::levelUp()
{
    Creature::levelUp();
    heal(0);
    addMana(0);
}

std::set<Item *> *Monster::getLoot()
{
    return LootProvider::getLoot(getScale());
}


void Monster::loadFromProps(Tmx::PropertySet props)
{
    std::string name = props.GetLiteralProperty("type");
    alive = true;
    className = name;
    Json::Value config = *ConfigurationProvider::getConfig("config/creatures.json");
    loadFromJson(config[name]);
}
