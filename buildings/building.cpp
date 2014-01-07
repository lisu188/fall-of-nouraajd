#include "building.h"
#include <QDebug>

Building::Building(int x, int y, int z):MapObject(x,y,z,1)
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
    config[(unsigned int)2]=getPosZ();
    return config;
}
