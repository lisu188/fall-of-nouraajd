#include "event.h"

#include <src/gameview.h>
#include <QApplication>
#include <QDebug>
#include <src/tile.h>
#include <src/potion.h>
#include <src/configurationprovider.h>
#include <src/monster.h>
#include <src/building.h>
#include <src/pathfinder.h>
#include <src/interaction.h>
#include <QThreadPool>

std::set<int> qMetaTypesRegister;

void registerMetaTypes()
{
    qMetaTypesRegister.insert(qRegisterMetaType<Weapon>());
    qMetaTypesRegister.insert(qRegisterMetaType<Armor>());
    qMetaTypesRegister.insert(qRegisterMetaType<Potion>());
    qMetaTypesRegister.insert(qRegisterMetaType<Cave>());
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
    qMetaTypesRegister.insert(qRegisterMetaType<Event>());
}

int main(int argc, char *argv[])
{
    QApplication a(argc, argv);
    QThreadPool::globalInstance()->setMaxThreadCount(16);
    QThreadPool::globalInstance()->setExpiryTimeout(0);
    registerMetaTypes();
    GameView view;
    int ret = a.exec();
    return ret;
}
