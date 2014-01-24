#ifndef DUNGEON_H
#define DUNGEON_H
#include "building.h"

class Dungeon : public Building
{
    Q_OBJECT
public:
    Dungeon();
    Dungeon(const Dungeon& dungeon);
    Dungeon(Coords enter,Coords exit);
    virtual void onEnter();
    virtual void onMove();
    bool canSave();
    Json::Value saveToJson();
    Coords getExit()const {
        return exit;
    }
private:
    Coords exit;
};
Q_DECLARE_METATYPE(Dungeon)
#endif // DUNGEON_H
