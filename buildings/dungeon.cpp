#include "dungeon.h"

#include <view/gamescene.h>

Dungeon::Dungeon(Coords enter, Coords exit):exit(exit),Building(enter.x,enter.y,enter.z)
{
    className="Dungeon";
    this->setAnimation("images/buildings/dungeon/");
}

void Dungeon::onEnter()
{
    GameScene::getPlayer()->moveTo(exit.x,exit.y,exit.z,true);
}

void Dungeon::onMove()
{
}

bool Dungeon::canSave()
{
    return true;
}
