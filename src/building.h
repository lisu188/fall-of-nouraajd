#ifndef BUILDING_H
#define BUILDING_H
#include "src/building.h"

#include "configurationprovider.h"

#include <src/listitem.h>

class Building : public ListItem
{
    Q_OBJECT
    Q_PROPERTY(bool enabled READ isEnabled WRITE setEnabled USER true)
public:
    static Building *createBuilding(QString name);
    Building();
    Building(const Building&);
    virtual void onEnter();
    virtual void onMove();
    virtual void loadFromJson(std::string name);
        //PROPERTIES
    bool isEnabled();
    void setEnabled(bool enabled);

protected:
    bool enabled = true;
};
Q_DECLARE_METATYPE(Building)

class Cave : public Building
{
    Q_OBJECT
    Q_PROPERTY(int chance READ getChance WRITE setChance USER true)
    Q_PROPERTY(QString monster READ getMonster WRITE setMonster USER true)
    Q_PROPERTY(int monsters READ getMonsters WRITE setMonsters USER true)
public:
    Cave();
    Cave(const Cave& cave);
    virtual void onEnter();
    virtual void onMove();
    //PROPERTIES
    QString getMonster() const;
    void setMonster(const QString &value);
    int getChance() const;
    void setChance(int value);
    int getMonsters() const;
    void setMonsters(int value);

private:
    QString monster = "Pritz";
    int chance = 15;
    int monsters=5;
};
Q_DECLARE_METATYPE(Cave)

class Teleporter : public Building
{
    Q_OBJECT
    Q_PROPERTY(QString exit READ getExit WRITE setExit USER true)
public:
    Teleporter();
    Teleporter(const Teleporter& teleporter);
    virtual void onEnter();
    virtual void onMove();
    //PROPERTIES
    QString getExit() const;
    void setExit(const QString &value);
private:
    QString exit;
};
Q_DECLARE_METATYPE(Teleporter)
#endif // BUILDING_H
