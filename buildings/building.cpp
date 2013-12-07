#include "building.h"
#include <QDebug>

Building::Building(Map *map,int x, int y):MapObject(map,x,y,1)
{
    className="Building";
}

void Building::onEnter()
{
    qDebug() << "Entered:" << className.c_str();
}
