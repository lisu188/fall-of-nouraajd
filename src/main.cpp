#include "view/gameview.h"

#include <QApplication>
#include <QDebug>
#include <src/map/tile.h>
#include <src/items/armor.h>
#include <src/items/weapon.h>
#include <src/items/potion.h>
#include <src/items/smallweapon.h>
#include <src/items/helmet.h>
#include <src/items/boots.h>
#include <src/items/belt.h>
#include <src/items/gloves.h>
#include <src/configuration/configurationprovider.h>
#include <src/buildings/cave.h>
#include <src/buildings/dungeon.h>
#include <src/buildings/teleporter.h>
#include <src/creatures/monster.h>
#include <src/pathfinder/dumbpathfinder.h>
#include <src/pathfinder/randompathfinder.h>
#include <src/pathfinder/smartpathfinder.h>

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
    int ret = a.exec();
    delete view;
    return ret;
}
