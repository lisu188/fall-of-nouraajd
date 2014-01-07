#ifndef BUILDING_H
#define BUILDING_H
#include "buildings/building.h"

#include <map/map.h>

class Building :public MapObject
{
public:
    Building(int x, int y,int z);
    virtual void onEnter();
    virtual bool canSave();
    virtual void loadFromJson(Json::Value config);
    virtual Json::Value saveToJson();
};

#endif // BUILDING_H
