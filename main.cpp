#include "view/gameview.h"

#include <QApplication>
#include <QDebug>
#include <map/tile.h>
#include <items/armor.h>
#include <items/weapon.h>
#include <items/potion.h>
#include <view/mapview.h>
#include <configuration/configurationprovider.h>
#include <buildings/cave.h>
#include <buildings/dungeon.h>
#include <buildings/teleporter.h>
#include <creatures/monster.h>

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
}

int main(int argc, char *argv[])
{
    QApplication a(argc, argv);
    QGraphicsView *view;
    registerMetaTypes();
    bool editor=(*ConfigurationProvider::getConfig("config/init.json")).get("editor",false).asBool();
    if(editor) {
        view=new MapView();
    }
    else {
        view = new GameView();
    }
    int ret=a.exec();
    delete view;
    return ret;
}
