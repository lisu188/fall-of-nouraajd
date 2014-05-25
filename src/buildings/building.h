#ifndef BUILDING_H
#define BUILDING_H
#include "src/buildings/building.h"

#include <src/view/listitem.h>

class Building : public ListItem
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

class Cave : public Building
{
    Q_OBJECT
public:
    Cave();
    Cave(const Cave& cave);
    virtual void onEnter();
    virtual void onMove();
    bool canSave();
    void loadFromJson(Json::Value config);
private:
    bool enabled;
    std::string monster="Pritz";
    int chance=15;

    // MapObject interface
public:
    virtual void loadFromProps(Tmx::PropertySet set);

    // MapObject interface
public:
    virtual Json::Value saveToJson();
};
Q_DECLARE_METATYPE(Cave)

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

class Teleporter : public Building
{
    Q_OBJECT
public:
    Teleporter();
    Teleporter(const Teleporter& teleporter);
    virtual void onEnter();
    virtual void onMove();
    bool canSave();
    Json::Value saveToJson();
    void loadFromJson(Json::Value config);
    void loadFromProps(Tmx::PropertySet set);
private:
    bool enabled = true;
};
Q_DECLARE_METATYPE(Teleporter)
#endif // BUILDING_H
