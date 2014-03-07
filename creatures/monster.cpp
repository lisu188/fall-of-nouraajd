#include "monster.h"

#include <view/gamescene.h>

#include <items/lootprovider.h>

#include <pathfinder/dumbpathfinder.h>
#include <pathfinder/randompathfinder.h>
#include <pathfinder/smartpathfinder.h>

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
    std::packaged_task<Coords(Coords,Coords)> task([](Coords a,Coords b){
    PathFinder *finder;
    if((a.getDist(b))<25){
            finder=new SmartPathFinder();
    }else{
            finder=new RandomPathFinder();
    }
    Coords c=finder->findPath(a,b);
    delete finder;
    return c;
    });
    coords = task.get_future();
    std::thread(std::move(task),getCoords(),GameScene::getPlayer()->getCoords()).detach();
}

void Monster::onMoveEnd()
{
    coords.wait();
    Coords path=coords.get();
    move(path.x,path.y);
    /*
    if(rand()%20==0) {
        onMove();
    }
    */
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
