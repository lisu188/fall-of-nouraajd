#include "monster.h"

#include <view/gamescene.h>

#include <items/lootprovider.h>

#include <pathfinder/dumbpathfinder.h>
#include <pathfinder/randompathfinder.h>
#include <pathfinder/smartpathfinder.h>
#include <QDebug>

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
    PathFinder *finder;
    if((this->getCoords().getDist(GameScene::getPlayer()->getCoords()))<25){
            finder=new SmartPathFinder();
    }else{
            finder=new RandomPathFinder();
    }
    Coords path=finder->findPath(this->getCoords(),GameScene::getPlayer()->getCoords());
    delete finder;
    move(path.x,path.y);
    /*
    if(rand()%20==0) {
        onMove();
    }
    */
    this->addExp(rand()%25);
    std::thread fillCache([](Coords a,Coords b)->void{
        SmartPathFinder finder;
        for(int i=-1;i<=1;i++)
            for(int j=-1;j<=1;j++)
                for(int k=-1;k<=1;k++)
                    for(int l=-1;l<=1;l++){
                      finder.findPath(Coords(a.x+i,a.y+j,a.z),Coords(b.x+i,b.y+j,b.z));
                    }
    },this->getCoords(),GameScene::getPlayer()->getCoords());
    fillCache.detach();
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
