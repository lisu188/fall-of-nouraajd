#include "building.h"
#include <QDebug>

Building::Building(Map *map,int x, int y):MapObject(map,x,y,1)
{
    className="Building";
}

void Building::onEnter()
{
    qDebug() << "Entered" << className.c_str()<<"\n";
}

bool Building::canSave() {
    return true;
}

void Building::loadFromJson(Json::Value config)
{
}

Json::Value Building::saveToJson()
{
    Json::Value config;
    config[(unsigned int)0]=getPosX();
    config[(unsigned int)1]=getPosY();
    return config;
}
