# Reconstructed missing historical project from same-commit translation units and resource manifests.
QT += core gui widgets
TARGET = Game
TEMPLATE = app
CONFIG += c++11
DEFINES += QT_NO_KEYWORDS
INCLUDEPATH += . src lib lib/tmx lib/tinyxml lib/base64 lib/zlib
unix:LIBS += -lpython3.4m -ldl -lutil
win32:LIBS += -lpython34

SOURCES += lib/base64/base64.cpp \
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
    src/animatedobject.cpp \
    src/animation.cpp \
    src/animationprovider.cpp \
    src/building.cpp \
    src/charview.cpp \
    src/configurationprovider.cpp \
    src/creature.cpp \
    src/destroyer.cpp \
    src/event.cpp \
    src/fightview.cpp \
    src/gamescene.cpp \
    src/gamescript.cpp \
    src/gameview.cpp \
    src/interaction.cpp \
    src/item.cpp \
    src/itemslot.cpp \
    src/listitem.cpp \
    src/lootprovider.cpp \
    src/main.cpp \
    src/map.cpp \
    src/monster.cpp \
    src/pathfinder.cpp \
    src/player.cpp \
    src/playerequippedview.cpp \
    src/playerlistview.cpp \
    src/playerstatsview.cpp \
    src/potion.cpp \
    src/scriptmanager.cpp \
    src/scrollobject.cpp \
    src/stats.cpp \
    src/tile.cpp \
    src/mainwindow.cpp \
    src/playerabstractview.cpp

HEADERS  += \
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
    src/animatedobject.h \
    src/animation.h \
    src/animationprovider.h \
    src/building.h \
    src/charview.h \
    src/configurationprovider.h \
    src/creature.h \
    src/destroyer.h \
    src/event.h \
    src/fightview.h \
    src/gamescene.h \
    src/gamescript.h \
    src/gameview.h \
    src/interaction.h \
    src/item.h \
    src/itemslot.h \
    src/listitem.h \
    src/lootprovider.h \
    src/mainwindow.h \
    src/map.h \
    src/monster.h \
    src/pathfinder.h \
    src/player.h \
    src/playerabstractview.h \
    src/playerequippedview.h \
    src/playerlistview.h \
    src/playerstatsview.h \
    src/potion.h \
    src/scriptmanager.h \
    src/scrollobject.h \
    src/stats.h \
    src/tile.h \
    src/util.h

FORMS += \
    src/mainwindow.ui
