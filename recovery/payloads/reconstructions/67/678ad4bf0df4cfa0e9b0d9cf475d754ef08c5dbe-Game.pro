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
    lib/base64/base64.cpp \
    lib/json/json_reader.cpp \
    lib/json/json_value.cpp \
    lib/json/json_writer.cpp \
    lib/tinyxml/tinystr.cpp \
    lib/tinyxml/tinyxml.cpp \
    lib/tinyxml/tinyxmlerror.cpp \
    lib/tinyxml/tinyxmlparser.cpp \
    lib/tmx/TmxEllipse.cpp \
    lib/tmx/TmxImage.cpp \
    lib/tmx/TmxImageLayer.cpp \
    lib/tmx/TmxLayer.cpp \
    lib/tmx/TmxMap.cpp \
    lib/tmx/TmxObject.cpp \
    lib/tmx/TmxObjectGroup.cpp \
    lib/tmx/TmxPolygon.cpp \
    lib/tmx/TmxPolyline.cpp \
    lib/tmx/TmxPropertySet.cpp \
    lib/tmx/TmxTile.cpp \
    lib/tmx/TmxTileset.cpp \
    lib/tmx/TmxUtil.cpp \
    lib/zlib/adler32.c \
    lib/zlib/compress.c \
    lib/zlib/crc32.c \
    lib/zlib/deflate.c \
    lib/zlib/gzclose.c \
    lib/zlib/gzlib.c \
    lib/zlib/gzread.c \
    lib/zlib/gzwrite.c \
    lib/zlib/infback.c \
    lib/zlib/inffast.c \
    lib/zlib/inflate.c \
    lib/zlib/inftrees.c \
    lib/zlib/trees.c \
    lib/zlib/uncompr.c \
    lib/zlib/zutil.c \
    src/animation/animatedobject.cpp \
    src/animation/animation.cpp \
    src/animation/animationprovider.cpp \
    src/buildings/building.cpp \
    src/configuration/configurationprovider.cpp \
    src/creatures/creature.cpp \
    src/creatures/monster.cpp \
    src/creatures/player.cpp \
    src/destroyer/destroyer.cpp \
    src/interactions/interaction.cpp \
    src/items/item.cpp \
    src/items/lootprovider.cpp \
    src/items/potion.cpp \
    src/main.cpp \
    src/map/coords.cpp \
    src/map/map.cpp \
    src/map/playeranimation.cpp \
    src/map/tile.cpp \
    src/pathfinder/pathfinder.cpp \
    src/stats/damage.cpp \
    src/stats/stats.cpp \
    src/view/charview.cpp \
    src/view/fightview.cpp \
    src/view/gamescene.cpp \
    src/view/gameview.cpp \
    src/view/itemslot.cpp \
    src/view/listitem.cpp \
    src/view/playerequippedview.cpp \
    src/view/playerlistview.cpp \
    src/view/playerstatsview.cpp \
    src/view/scrollobject.cpp

HEADERS += \
    lib/base64/base64.h \
    lib/json/autolink.h \
    lib/json/config.h \
    lib/json/features.h \
    lib/json/forwards.h \
    lib/json/json.h \
    lib/json/json_batchallocator.h \
    lib/json/reader.h \
    lib/json/value.h \
    lib/json/writer.h \
    lib/tinyxml/tinystr.h \
    lib/tinyxml/tinyxml.h \
    lib/tmx/Tmx.h \
    lib/tmx/TmxEllipse.h \
    lib/tmx/TmxImage.h \
    lib/tmx/TmxImageLayer.h \
    lib/tmx/TmxLayer.h \
    lib/tmx/TmxMap.h \
    lib/tmx/TmxMapTile.h \
    lib/tmx/TmxObject.h \
    lib/tmx/TmxObjectGroup.h \
    lib/tmx/TmxPoint.h \
    lib/tmx/TmxPolygon.h \
    lib/tmx/TmxPolyline.h \
    lib/tmx/TmxPropertySet.h \
    lib/tmx/TmxTile.h \
    lib/tmx/TmxTileset.h \
    lib/tmx/TmxUtil.h \
    lib/zlib/crc32.h \
    lib/zlib/deflate.h \
    lib/zlib/gzguts.h \
    lib/zlib/inffast.h \
    lib/zlib/inffixed.h \
    lib/zlib/inflate.h \
    lib/zlib/inftrees.h \
    lib/zlib/trees.h \
    lib/zlib/zconf.h \
    lib/zlib/zlib.h \
    lib/zlib/zutil.h \
    src/animation/animatedobject.h \
    src/animation/animation.h \
    src/animation/animationprovider.h \
    src/buildings/building.h \
    src/configuration/configurationprovider.h \
    src/creatures/creature.h \
    src/creatures/monster.h \
    src/creatures/player.h \
    src/destroyer/destroyer.h \
    src/interactions/interaction.h \
    src/items/item.h \
    src/items/lootprovider.h \
    src/items/potion.h \
    src/map/coords.h \
    src/map/map.h \
    src/map/playeranimation.h \
    src/map/tile.h \
    src/pathfinder/pathfinder.h \
    src/stats/damage.h \
    src/stats/stats.h \
    src/util/patch.h \
    src/view/charview.h \
    src/view/fightview.h \
    src/view/gamescene.h \
    src/view/gameview.h \
    src/view/itemslot.h \
    src/view/listitem.h \
    src/view/playerequippedview.h \
    src/view/playerlistview.h \
    src/view/playerstatsview.h \
    src/view/scrollobject.h
