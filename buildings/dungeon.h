#ifndef DUNGEON_H
#define DUNGEON_H
#include "building.h"

class Dungeon : public Building
{
public:
    Dungeon(Map *map, int x, int y);
    virtual void onEnter();
    virtual void onMove();
    bool canSave();
};
#endif // DUNGEON_H
