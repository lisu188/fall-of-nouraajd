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
    interactions/attacks/attack.cpp \
    interactions/spells/spell.cpp \
    interactions/skills/skill.cpp \
    map/tiles/mountaintile.cpp \
    buildings/cave.cpp \
    animation/animationprovider.cpp \
    animation/animation.cpp \
    map/playeranimation.cpp \
    animation/animatedobject.cpp \
    view/playerstatsview.cpp \
    view/gameview.cpp \
    view/gamescene.cpp \
    interactions/spells/magicmissile.cpp \
    interactions/skills/doubleattack.cpp \
    interactions/skills/sneakattack.cpp \
    view/scrollobject.cpp \
    interactions/spells/chaosblast.cpp \
    items/armor.cpp \
    view/playerlistview.cpp \
    view/listitem.cpp \
    destroyer/destroyer.cpp \
    interactions/skills/strike.cpp \
    interactions/spells/frostbolt.cpp \
    stats/stats.cpp \
    stats/damage.cpp \
    view/fightview.cpp \
    json/json_writer.cpp \
    json/json_value.cpp \
    json/json_reader.cpp \
    effects/effect.cpp \
    effects/stun.cpp \
    interactions/skills/stunner.cpp \
    interactions/attacks/elemstaff.cpp \
    interactions/spells/abyssalshadows.cpp \
    effects/abyssalshadowseffect.cpp \
    interactions/spells/endlesspain.cpp \
    effects/endlesspaineffect.cpp \
    interactions/spells/shadowbolt.cpp \
    interactions/spells/devour.cpp \
    creatures/player.cpp \
    creatures/monster.cpp \
    items/potion.cpp \
    interactions/spells/armorofendlesswinter.cpp \
    effects/armorofendlesswintereffect.cpp \
    configuration/configurationprovider.cpp

HEADERS  += \
    animation/animatedobject.h \
    animation/animation.h \
    animation/animationprovider.h \
    buildings/building.h \
    buildings/cave.h \
    buildings/towers/tower.h \
    buildings/towns/town.h \
    configuration/configurationprovider.h \
    creatures/creature.h \
    creatures/monster.h \
    creatures/player.h \
    destroyer/destroyer.h \
    effects/abyssalshadowseffect.h \
    effects/armorofendlesswintereffect.h \
    effects/effect.h \
    effects/endlesspaineffect.h \
    effects/stun.h \
    interactions/attacks/attack.h \
    interactions/attacks/elemstaff.h \
    interactions/interaction.h \
    interactions/skills/doubleattack.h \
    interactions/skills/skill.h \
    interactions/skills/sneakattack.h \
    interactions/skills/strike.h \
    interactions/skills/stunner.h \
    interactions/spells/abyssalshadows.h \
    interactions/spells/armorofendlesswinter.h \
    interactions/spells/chaosblast.h \
    interactions/spells/devour.h \
    interactions/spells/endlesspain.h \
    interactions/spells/frostbolt.h \
    interactions/spells/magicmissile.h \
    interactions/spells/shadowbolt.h \
    interactions/spells/spell.h \
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
    map/tiles/grasstile.h \
    map/tiles/groundtile.h \
    map/tiles/mountaintile.h \
    map/tiles/roadtile.h \
    map/tiles/tile.h \
    map/tiles/watertile.h \
    stats/damage.h \
    stats/stats.h \
    view/fightview.h \
    view/gamescene.h \
    view/gameview.h \
    view/listitem.h \
    view/playerlistview.h \
    view/playerstatsview.h \
    view/scrollobject.h
