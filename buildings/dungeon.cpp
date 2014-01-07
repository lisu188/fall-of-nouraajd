#include "dungeon.h"

#include <view/gamescene.h>

Dungeon::Dungeon(int x, int y):Building(x,y)
{
    className="Dungeon";
    this->setAnimation("images/buildings/dungeon/");
}

void Dungeon::onEnter()
{
    GameScene::getPlayer()->moveTo(0,0,1,true);
}

void Dungeon::onMove()
{
}

bool Dungeon::canSave()
{
    return true;
}
