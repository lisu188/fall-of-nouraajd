#include "monster.h"

#include <view/gamescene.h>

#include <items/lootprovider.h>

#include <pathfinder/dumbpathfinder.h>

Monster::Monster(std::string name, Json::Value config):Creature(name,config)
{
}

Monster::Monster(std::string name):Creature(name)
{
}

Monster::Monster()
{
}

Monster::Monster(const Monster &monster):Monster(monster.className)
{
}

void Monster::onMove()
{
    if(!isAlive()) {
        return;
    }
    DumbPathFinder finder;
    Coords path=finder.findPath(this->getCoords(),GameScene::getPlayer()->getCoords());
    move(path.x,path.y);
    if(rand()%20==0) {
        onMove();
    }
    this->addExp(rand()%25);
}

void Monster::onEnter()
{
    if(!isAlive()) {
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
