#ifndef CAVE_H
#define CAVE_H
#include "building.h"

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
};

#endif // CAVE_H
