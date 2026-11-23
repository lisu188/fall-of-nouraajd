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
SOURCES += animation/animatedobject.cpp \
    animation/animation.cpp \
    animation/animationprovider.cpp \
    base64/base64.cpp \
    buildings/building.cpp \
    buildings/cave.cpp \
    buildings/dungeon.cpp \
    buildings/teleporter.cpp \
    buildings/towers/tower.cpp \
    buildings/towns/town.cpp \
    compression/compression.cpp \
    configuration/configurationprovider.cpp \
    creatures/creature.cpp \
    creatures/monster.cpp \
    creatures/player.cpp \
    destroyer/destroyer.cpp \
    interactions/interaction.cpp \
    items/armor.cpp \
    items/belt.cpp \
    items/boots.cpp \
    items/gloves.cpp \
    items/helmet.cpp \
    items/item.cpp \
    items/lootprovider.cpp \
    items/potion.cpp \
    items/smallweapon.cpp \
    items/weapon.cpp \
    json/json_reader.cpp \
    json/json_value.cpp \
    json/json_writer.cpp \
    main.cpp \
    map/coords.cpp \
    map/events/event.cpp \
    map/map.cpp \
    map/playeranimation.cpp \
    map/tile.cpp \
    pathfinder/dumbpathfinder.cpp \
    pathfinder/pathfinder.cpp \
    pathfinder/randompathfinder.cpp \
    pathfinder/smartpathfinder.cpp \
    stats/damage.cpp \
    stats/stats.cpp \
    tinyxml/tinystr.cpp \
    tinyxml/tinyxml.cpp \
    tinyxml/tinyxmlerror.cpp \
    tinyxml/tinyxmlparser.cpp \
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
    view/charview.cpp \
    view/fightview.cpp \
    view/gamescene.cpp \
    view/gameview.cpp \
    view/itemslot.cpp \
    view/listitem.cpp \
    view/playerequippedview.cpp \
    view/playerlistview.cpp \
    view/playerstatsview.cpp \
    view/scrollobject.cpp

HEADERS += animation/animatedobject.h \
    animation/animation.h \
    animation/animationprovider.h \
    base64/base64.h \
    buildings/building.h \
    buildings/cave.h \
    buildings/dungeon.h \
    buildings/teleporter.h \
    buildings/towers/tower.h \
    buildings/towns/town.h \
    compression/compression.h \
    configuration/configurationprovider.h \
    creatures/creature.h \
    creatures/monster.h \
    creatures/player.h \
    destroyer/destroyer.h \
    interactions/interaction.h \
    items/armor.h \
    items/belt.h \
    items/boots.h \
    items/gloves.h \
    items/helmet.h \
    items/item.h \
    items/lootprovider.h \
    items/potion.h \
    items/smallweapon.h \
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
    pathfinder/dumbpathfinder.h \
    pathfinder/pathfinder.h \
    pathfinder/randompathfinder.h \
    pathfinder/smartpathfinder.h \
    stats/damage.h \
    stats/stats.h \
    tinyxml/tinystr.h \
    tinyxml/tinyxml.h \
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
    util/patch.h \
    view/charview.h \
    view/fightview.h \
    view/gamescene.h \
    view/gameview.h \
    view/itemslot.h \
    view/listitem.h \
    view/playerequippedview.h \
    view/playerlistview.h \
    view/playerstatsview.h \
    view/scrollobject.h \
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

RESOURCES += armors.qrc \
    buildings.qrc \
    config.qrc \
    creatures.qrc \
    images.qrc \
    items.qrc \
    iteractions.qrc \
    potions.qrc \
    tiles.qrc \
    weapons.qrc

LIBS += -lz
