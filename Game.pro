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

SOURCES += main.cpp \
    map/map.cpp \
    map/events/event.cpp \
    map/coords.cpp \
    creatures/creature.cpp \
    items/item.cpp \
    buildings/building.cpp \
    buildings/towers/tower.cpp \
    buildings/towns/town.cpp \
    items/weapon.cpp \
    interactions/interaction.cpp \
    buildings/cave.cpp \
    animation/animationprovider.cpp \
    animation/animation.cpp \
    map/playeranimation.cpp \
    animation/animatedobject.cpp \
    view/playerstatsview.cpp \
    view/gameview.cpp \
    view/gamescene.cpp \
    view/scrollobject.cpp \
    items/armor.cpp \
    view/playerlistview.cpp \
    view/listitem.cpp \
    destroyer/destroyer.cpp \
    stats/stats.cpp \
    stats/damage.cpp \
    view/fightview.cpp \
    json/json_writer.cpp \
    json/json_value.cpp \
    json/json_reader.cpp \
    creatures/player.cpp \
    creatures/monster.cpp \
    items/potion.cpp \
    configuration/configurationprovider.cpp \
    compression/compression.cpp \
    map/tile.cpp \
    buildings/dungeon.cpp \
    view/mapview.cpp \
    view/mapscene.cpp

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
    include/zconf.h \
    include/zlib.h \
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

# Inferred build compatibility: expose the surviving CharView declaration to GameView.
QMAKE_CXXFLAGS += -include $$PWD/view/charview.h

# The next surviving GameView constructs the same-tree CharView.
SOURCES += view/charview.cpp
