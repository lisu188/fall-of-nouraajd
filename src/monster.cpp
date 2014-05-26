#include "monster.h"
#include <src/gamescene.h>
#include <src/lootprovider.h>
#include <src/pathfinder.h>
#include <QDebug>
#include <src/configurationprovider.h>

Monster::Monster(): Creature()
{
}

Monster::Monster(const Monster &monster)
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
