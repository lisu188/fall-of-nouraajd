#ifndef DUNGEON_H
#define DUNGEON_H
#include "building.h"

class Dungeon : public Building
{
    Q_OBJECT
public:
    Dungeon();
    Dungeon(const Dungeon& dungeon);
    virtual void onEnter();
    virtual void onMove();
    bool canSave();
    Json::Value saveToJson();
    void loadFromJson(Json::Value config);
    Coords getExit()const;
private:
    Coords exit;
};
Q_DECLARE_METATYPE(Dungeon)
#endif // DUNGEON_H
