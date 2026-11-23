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

        RE

SOURCES += creatures/player.cpp \
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
    destroyer/destroyer.cpp

HEADERS  += \
    animation/animatedobject.h \
    animation/animation.h \
    animation/animationprovider.h \
    buildings/building.h \
    buildings/cave.h \
    buildings/dungeon.h \
    buildings/towers/tower.h \
    buildings/towns/town.h \
    compression/compression.h \
    compression/minizip.h \
    configuration/configurationprovider.h \
    creatures/creature.h \
    creatures/monster.h \
    creatures/player.h \
    destroyer/destroyer.h \
    interactions/interaction.h \
    items/armor.h \
    items/item.h \
    items/potion.h \
    items/weapon.h \
    json/autolink.h \
    json/config.h \
    json/features.h \
    json/forwards.h \
    json/json.h \
    json/json_batchallocator.h \
    json/reader.h \
    json/value.h \
    json/writer.h \
    map/coords.h \
    map/events/event.h \
    map/map.h \
    map/playeranimation.h \
    map/tile.h \
    stats/damage.h \
    stats/stats.h \
    view/charview.h \
    view/fightview.h \
    view/gamescene.h \
    view/gameview.h \
    view/listitem.h \
    view/mapscene.h \
    view/mapview.h \
    view/playerlistview.h \
    view/playerstatsview.h \
    view/scrollobject.h

RESOURCES += \
    config.qrc \
    images.qrc
