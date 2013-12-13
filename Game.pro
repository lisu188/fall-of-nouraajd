#-------------------------------------------------
#
# Project created by QtCreator 2013-10-30T13:16:43
#
#-------------------------------------------------

QT       += core gui

greaterThan(QT_MAJOR_VERSION, 4): QT += widgets

TARGET = Game
TEMPLATE = app
CONFIG += console
QMAKE_CXXFLAGS += -std=c++11

SOURCES += main.cpp \
    map/tiles/watertile.cpp \
    map/tiles/tile.cpp \
    map/tiles/grasstile.cpp \
    map/tiles/groundtile.cpp \
    map/tiles/roadtile.cpp \
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
    map/tiles/mountaintile.cpp \
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
    json/json_valueiterator.inl \
    json/json_value.cpp \
    json/json_reader.cpp \
    json/json_internalmap.inl \
    json/json_internalarray.inl \
    effects/effect.cpp \
    effects/stun.cpp \
    effects/abyssalshadowseffect.cpp \
    effects/endlesspaineffect.cpp \
    creatures/player.cpp \
    creatures/monster.cpp \
    items/potion.cpp \
    effects/armorofendlesswintereffect.cpp \
    configuration/configurationprovider.cpp

INCLUDEPATH += tmp/moc/release_shared

HEADERS  += \
    map/tiles/watertile.h \
    map/tiles/tile.h \
    map/tiles/grasstile.h \
    map/tiles/groundtile.h \
    map/tiles/roadtile.h \
    map/map.h \
    map/events/event.h \
    map/coords.h \
    creatures/creature.h \
    items/item.h \
    buildings/building.h \
    buildings/towers/tower.h \
    buildings/towns/town.h \
    interactions/interaction.h \
    map/tiles/mountaintile.h \
    buildings/cave.h \
    animation/animationprovider.h \
    animation/animation.h \
    map/playeranimation.h \
    animation/animatedobject.h \
    view/playerstatsview.h \
    view/gameview.h \
    view/gamescene.h \
    view/scrollobject.h \
    items/armor.h \
    view/playerlistview.h \
    view/listitem.h \
    destroyer/destroyer.h \
    stats/stats.h \
    stats/damage.h \
    view/fightview.h \
    json/writer.h \
    json/value.h \
    json/reader.h \
    json/json_batchallocator.h \
    json/json.h \
    json/forwards.h \
    json/features.h \
    json/config.h \
    json/autolink.h \
    effects/effect.h \
    effects/stun.h \
    effects/abyssalshadowseffect.h \
    effects/endlesspaineffect.h \
    creatures/player.h \
    creatures/monster.h \
    items/weapon.h \
    items/armor.h \
    items/potion.h \
    effects/armorofendlesswintereffect.h \
    configuration/configurationprovider.h
