#ifndef BUILDING_H
#define BUILDING_H
#include "src/building.h"

#include "configurationprovider.h"

#include <src/listitem.h>

class Building : public ListItem
{
    Q_OBJECT
    Q_PROPERTY(bool enabled READ isEnabled WRITE setEnabled)
public:
    static Building *getBuilding(std::string name);
    Building();
    Building(const Building&);
    virtual void onEnter();
    virtual void onMove();
    virtual void loadFromJson(std::string name);

    bool isEnabled();
    void setEnabled(bool enabled);

protected:
    bool enabled = true;
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
private:
    std::string monster = "Pritz";
    int chance = 15;
};
Q_DECLARE_METATYPE(Cave)

class Teleporter : public Building
{
    Q_OBJECT
public:
    Teleporter();
    Teleporter(const Teleporter& teleporter);
    virtual void onEnter();
    virtual void onMove();
    bool canSave();
};
Q_DECLARE_METATYPE(Teleporter)
#endif // BUILDING_H
