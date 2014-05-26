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
    Q_PROPERTY(int chance READ getChance WRITE setChance)
    Q_PROPERTY(QString monster READ getMonster WRITE setMonster)
public:
    Cave();
    Cave(const Cave& cave);
    virtual void onEnter();
    virtual void onMove();
    QString getMonster() const;
    void setMonster(const QString &value);
    int getChance() const;
    void setChance(int value);

private:
    QString monster = "Pritz";
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
};
Q_DECLARE_METATYPE(Teleporter)
#endif // BUILDING_H
