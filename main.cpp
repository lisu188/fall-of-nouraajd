#include "view/gameview.h"

#include <QApplication>
#include <QDebug>
#include <map/tile.h>
#include <items/armor.h>
#include <items/weapon.h>
#include <items/potion.h>
#include <items/smallweapon.h>
#include <items/helmet.h>
#include <items/boots.h>
#include <items/belt.h>
#include <items/gloves.h>
#include <configuration/configurationprovider.h>
#include <buildings/cave.h>
#include <buildings/dungeon.h>
#include <buildings/teleporter.h>
#include <creatures/monster.h>
#include <pathfinder/dumbpathfinder.h>
#include <pathfinder/randompathfinder.h>
#include <pathfinder/smartpathfinder.h>

std::set<int> qMetaTypesRegister;

void registerMetaTypes()
{
    qMetaTypesRegister.insert(qRegisterMetaType<Weapon>());
    qMetaTypesRegister.insert(qRegisterMetaType<Armor>());
    qMetaTypesRegister.insert(qRegisterMetaType<Potion>());
    qMetaTypesRegister.insert(qRegisterMetaType<Cave>());
    qMetaTypesRegister.insert(qRegisterMetaType<Dungeon>());
    qMetaTypesRegister.insert(qRegisterMetaType<Building>());
    qMetaTypesRegister.insert(qRegisterMetaType<Item>());
    qMetaTypesRegister.insert(qRegisterMetaType<Creature>());
    qMetaTypesRegister.insert(qRegisterMetaType<Player>());
    qMetaTypesRegister.insert(qRegisterMetaType<Monster>());
    qMetaTypesRegister.insert(qRegisterMetaType<Tile>());
    qMetaTypesRegister.insert(qRegisterMetaType<Teleporter>());
    qMetaTypesRegister.insert(qRegisterMetaType<Interaction>());
    qMetaTypesRegister.insert(qRegisterMetaType<SmallWeapon>());
    qMetaTypesRegister.insert(qRegisterMetaType<Helmet>());
    qMetaTypesRegister.insert(qRegisterMetaType<Boots>());
    qMetaTypesRegister.insert(qRegisterMetaType<Belt>());
    qMetaTypesRegister.insert(qRegisterMetaType<Gloves>());
    qMetaTypesRegister.insert(qRegisterMetaType<DumbPathFinder>());
    qMetaTypesRegister.insert(qRegisterMetaType<SmartPathFinder>());
    qMetaTypesRegister.insert(qRegisterMetaType<RandomPathFinder>());
}

int main(int argc, char *argv[])
{
    QApplication a(argc, argv);
    QGraphicsView *view;
    registerMetaTypes();
    view = new GameView();
    int ret=a.exec();
    delete view;
    return ret;
}
