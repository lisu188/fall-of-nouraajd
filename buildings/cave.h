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

private:
    bool enabled;

};

#endif // CAVE_H
