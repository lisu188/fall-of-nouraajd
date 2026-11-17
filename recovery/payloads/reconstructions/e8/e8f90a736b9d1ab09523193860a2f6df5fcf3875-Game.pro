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
    potions.qrc \
    items.qrc

SOURCES += \
    creatures/player.cpp \
    view/fightview.cpp \
    map/map.cpp \
    view/gameview.cpp \
    view/gamescene.cpp \
    items/item.cpp \
    creatures/creature.cpp \
    view/listitem.cpp \
    view/charview.cpp \
    view/playerlistview.cpp \
    creatures/monster.cpp \
    map/tile.cpp \
    interactions/interaction.cpp \
    configuration/configurationprovider.cpp \
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
    view/itemslot.cpp \
    items/boots.cpp \
    items/gloves.cpp \
    items/belt.cpp \
    items/lootprovider.cpp \
    pathfinder/pathfinder.cpp \
    pathfinder/dumbpathfinder.cpp \
    pathfinder/smartpathfinder.cpp \
    tmx/TmxEllipse.cpp \
    tmx/TmxImage.cpp \
    tmx/TmxImageLayer.cpp \
    tmx/TmxLayer.cpp \
    tmx/TmxMap.cpp \
    tmx/TmxObject.cpp \
    tmx/TmxObjectGroup.cpp \
    tmx/TmxPolygon.cpp \
    tmx/TmxPolyline.cpp \
    tmx/TmxPropertySet.cpp \
    tmx/TmxTile.cpp \
    tmx/TmxTileset.cpp \
    tmx/TmxUtil.cpp \
    tinyxml/tinystr.cpp \
    tinyxml/tinyxml.cpp \
    tinyxml/tinyxmlerror.cpp \
    tinyxml/tinyxmlparser.cpp \
    base64/base64.cpp \
    zlib/adler32.c \
    zlib/compress.c \
    zlib/crc32.c \
    zlib/deflate.c \
    zlib/gzclose.c \
    zlib/gzlib.c \
    zlib/gzread.c \
    zlib/gzwrite.c \
    zlib/infback.c \
    zlib/inffast.c \
    zlib/inflate.c \
    zlib/inftrees.c \
    zlib/trees.c \
    zlib/uncompr.c \
    zlib/zutil.c

HEADERS += \
    creatures/player.h \
    view/gameview.h \
    map/map.h \
    creatures/creature.h \
    view/charview.h \
    view/playerlistview.h \
    view/gamescene.h \
    creatures/monster.h \
    view/fightview.h \
    interactions/interaction.h \
    view/listitem.h \
    view/scrollobject.h \
    map/tile.h \
    items/item.h \
    view/playerstatsview.h \
    animation/animatedobject.h \
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
    util/patch.h \
    items/boots.h \
    items/gloves.h \
    items/belt.h \
    items/lootprovider.h \
    pathfinder/pathfinder.h \
    pathfinder/dumbpathfinder.h \
    pathfinder/smartpathfinder.h \
    tmx/Tmx.h \
    tmx/TmxEllipse.h \
    tmx/TmxImage.h \
    tmx/TmxImageLayer.h \
    tmx/TmxLayer.h \
    tmx/TmxMap.h \
    tmx/TmxMapTile.h \
    tmx/TmxObject.h \
    tmx/TmxObjectGroup.h \
    tmx/TmxPoint.h \
    tmx/TmxPolygon.h \
    tmx/TmxPolyline.h \
    tmx/TmxPropertySet.h \
    tmx/TmxTile.h \
    tmx/TmxTileset.h \
    tmx/TmxUtil.h \
    tinyxml/tinystr.h \
    tinyxml/tinyxml.h \
    base64/base64.h \
    zlib/crc32.h \
    zlib/deflate.h \
    zlib/gzguts.h \
    zlib/inffast.h \
    zlib/inffixed.h \
    zlib/inflate.h \
    zlib/inftrees.h \
    zlib/trees.h \
    zlib/zconf.h \
    zlib/zlib.h \
    zlib/zutil.h
