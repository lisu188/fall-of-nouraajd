#include "dungeon.h"

#include <view/gamescene.h>

Dungeon::Dungeon(Map *map, int x, int y):Building(map,x,y)
{
    className="Dungeon";
    this->setAnimation("images/buildings/dungeon/");
}

void Dungeon::onEnter()
{
    GameScene::getGame()->changeMap();
}

void Dungeon::onMove()
{
}

bool Dungeon::canSave()
{
    return true;
}
