#include "dungeon.h"

#include <view/gamescene.h>

Dungeon::Dungeon(Coords enter, Coords exit):Building(enter.x,enter.y,enter.z),exit(exit)
{
    className="Dungeon";
    this->setAnimation("images/buildings/dungeon/");
}

Dungeon::Dungeon(const Dungeon &dungeon)
    :Dungeon(Coords(dungeon.getPosX(),dungeon.getPosY(),dungeon.getPosZ()),
             dungeon.getExit())
{
}

void Dungeon::onEnter()
{
    GameScene::getPlayer()->moveTo(exit.x,exit.y,exit.z,true);
    map->move(0,0);
}

void Dungeon::onMove()
{
}

bool Dungeon::canSave()
{
    return true;
}

Json::Value Dungeon::saveToJson()
{
    Json::Value config;
    config[(unsigned int)0]=getPosX();
    config[(unsigned int)1]=getPosY();
    config[(unsigned int)2]=getPosZ();
    config[(unsigned int)3]=exit.x;
    config[(unsigned int)4]=exit.y;
    config[(unsigned int)5]=exit.z;
    return config;
}
