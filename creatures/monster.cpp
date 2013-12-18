#include "monster.h"

#include <view/gamescene.h>

Monster::Monster(std::string name, Json::Value config, Map *map):Creature(name,config,map)
{
}

Monster::Monster(std::string name, Map *map):Creature(name,map)
{
}

void Monster::onMove()
{
    if(!isAlive()) {
        return;
    }
    int px=GameScene::getPlayer()->getPosX();
    int py=GameScene::getPlayer()->getPosY();
    int dirx=px-this->getPosX();
    int diry=py-this->getPosY();
    int movx,movy;
    if(dirx>0) {
        movx=1;
    }
    else if(dirx==0) {
        movx=0;
    }
    else {
        movx=-1;
    }
    if(diry>0) {
        movy=1;
    }
    else if(diry==0) {
        movy=0;
    }
    else {
        movy=-1;
    }
    if(movx!=0&&movy!=0)
    {
        switch(rand()%2)
        {
        case 0:
            movx=0;
            break;
        case 1:
            movy=0;
            break;
        }
    }
    move(movx,movy);
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

std::list<Item *> *Monster::getLoot()
{
    std::list<Item *>* list=new std::list<Item *>();
    if(rand()%3==0) {
        list->push_back(Item::getItem("ManaPotion"));
    }
    else {
        list->push_back(Item::getItem("LifePotion"));
    }
    return list;
}
