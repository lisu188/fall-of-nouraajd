#ifndef CAVE_H
#define CAVE_H
#include "building.h"

class Cave : public Building
{
public:
    Cave(int x, int y);
    virtual void onEnter();
    virtual void onMove();
    bool canSave();

private:
    bool enabled;
};

#endif // CAVE_H
