#ifndef DUNGEON_H
#define DUNGEON_H
#include "building.h"

class Dungeon : public Building
{
public:
    Dungeon(Coords enter,Coords exit);
    virtual void onEnter();
    virtual void onMove();
    bool canSave();
    Json::Value saveToJson();
private:
    Coords exit;
};
#endif // DUNGEON_H
