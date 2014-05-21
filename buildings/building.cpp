#include "building.h"
#include <QDebug>

Building::Building()
{
    this->setZValue(2);
}

Building::Building(const Building &)
{
}

void Building::onEnter()
{
    qDebug() << "Entered" << className.c_str()<<"\n";
}

bool Building::canSave() {
    return true;
}

void Building::onMove()
{
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
