#ifndef BUILDING_H
#define BUILDING_H
#include "buildings/building.h"

#include <view/listitem.h>

class Building :public ListItem
{
    Q_OBJECT
public:
    Building();
    Building(const Building&);
    virtual void onEnter();
    virtual bool canSave();
    void onMove();
    virtual void loadFromJson(Json::Value config);
    virtual Json::Value saveToJson();
};
Q_DECLARE_METATYPE(Building)
#endif // BUILDING_H
