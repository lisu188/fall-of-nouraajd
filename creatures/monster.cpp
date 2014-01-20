#include "monster.h"

#include <view/gamescene.h>

Monster::Monster(std::string name, Json::Value config):Creature(name,config)
{
}

Monster::Monster(std::string name):Creature(name)
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

std::set<Item *> *Monster::getLoot()
{
    std::set<Item *>* list=new std::set<Item *>();
    if(rand()%3==0) {
        list->insert(Item::getItem("ManaPotion"));
    }
    else {
        list->insert(Item::getItem("LifePotion"));
    }
    return list;
}
