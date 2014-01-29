 # ------------------------------------------------ -
 #
 # Project created by QtCreator 2013 - 10 - 30T13 : 16 : 43
 #
 # ------------------------------------------------ -

QT += core gui

greaterThan(QT_MAJOR_VERSION, 4) : QT += widgets

TARGET = Game
TEMPLATE = app

win32 {
CONFIG += console
}

QMAKE_CXXFLAGS += -std=c++11

        RESOURCES +=  \
        config.qrc \
    iteractions.qrc \
    creatures.qrc \
    buildings.qrc \
    tiles.qrc \
    images.qrc \
    weapons.qrc \
    armors.qrc \
    potions.qrc

SOURCES += \
    creatures/player.cpp \
    view/fightview.cpp \
    map/map.cpp \
    view/gameview.cpp \
    view/gamescene.cpp \
    items/item.cpp \
    creatures/creature.cpp \
    view/listitem.cpp \
    view/mapview.cpp \
    view/charview.cpp \
    view/playerlistview.cpp \
    creatures/monster.cpp \
    map/tile.cpp \
    interactions/interaction.cpp \
    configuration/configurationprovider.cpp \
    view/mapscene.cpp \
    animation/animationprovider.cpp \
    main.cpp \
    buildings/dungeon.cpp \
    compression/compression.cpp \
    view/scrollobject.cpp \
    view/playerstatsview.cpp \
    animation/animatedobject.cpp \
    buildings/cave.cpp \
    buildings/building.cpp \
    buildings/towns/town.cpp \
    buildings/towers/tower.cpp \
    map/coords.cpp \
    stats/damage.cpp \
    map/events/event.cpp \
    map/playeranimation.cpp \
    stats/stats.cpp \
    items/armor.cpp \
    json/json_reader.cpp \
    json/json_value.cpp \
    json/json_writer.cpp \
    items/potion.cpp \
    items/weapon.cpp \
    animation/animation.cpp \
    destroyer/destroyer.cpp \
    buildings/teleporter.cpp \
    items/smallweapon.cpp \
    items/helmet.cpp \
    view/playerequippedview.cpp \
    view/itemslot.cpp

HEADERS += \
    creatures/player.h \
    view/gameview.h \
    map/map.h \
    creatures/creature.h \
    view/charview.h \
    view/mapview.h \
    view/playerlistview.h \
    view/gamescene.h \
    creatures/monster.h \
    view/fightview.h \
    interactions/interaction.h \
    compression/minizip.h \
    view/listitem.h \
    view/scrollobject.h \
    map/tile.h \
    items/item.h \
    view/playerstatsview.h \
    animation/animatedobject.h \
    view/mapscene.h \
    animation/animationprovider.h \
    items/armor.h \
    items/potion.h \
    items/weapon.h \
    buildings/dungeon.h \
    buildings/cave.h \
    buildings/towns/town.h \
    buildings/towers/tower.h \
    buildings/building.h \
    map/coords.h \
    stats/damage.h \
    map/events/event.h \
    map/playeranimation.h \
    stats/stats.h \
    json/autolink.h \
    json/config.h \
    json/features.h \
    json/forwards.h \
    json/json.h \
    json/json_batchallocator.h \
    json/reader.h \
    json/value.h \
    json/writer.h \
    animation/animation.h \
    compression/compression.h \
    configuration/configurationprovider.h \
    destroyer/destroyer.h \
    buildings/teleporter.h \
    items/smallweapon.h \
    items/helmet.h \
    view/playerequippedview.h \
    view/itemslot.h \
    util/patch.h
