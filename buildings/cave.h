#include "building.h"

#include <QPixmap>

#ifndef CAVE_H
#define CAVE_H

class Cave : public Building
{
public:
    Cave(Map *map, int x, int y);
    virtual void onEnter();
    virtual void onMove();
    static int count;
    bool canSave();

private:
    bool enabled;


    // MapObject interface
public:
    virtual void loadFromJson(Json::Value config);
    virtual Json::Value saveToJson();
};

#endif // CAVE_H
