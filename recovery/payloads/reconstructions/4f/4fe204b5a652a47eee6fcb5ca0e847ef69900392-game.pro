# Reconstructed missing historical project from same-commit translation units and resource manifests.
QT += core gui widgets
TARGET = Game
TEMPLATE = app
CONFIG += c++11
INCLUDEPATH += . src lib lib/tmx lib/tinyxml lib/base64 lib/zlib
unix:LIBS += -lpython2.7 -ldl -lutil
win32:LIBS += -lpython27
unix:LIBS += -lboost_python

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
    src/CGameScene.cpp \
    src/GameScript.cpp \
    src/CGameView.cpp \
    src/item.cpp \
    src/CItemSlot.cpp \
    src/CLootProvider.cpp \
    src/main.cpp \
    src/playerequippedview.cpp \
    src/playerlistview.cpp \
    src/playerstatsview.cpp \
    src/potion.cpp \
    src/CScriptEngine.cpp \
    src/stats.cpp \
    src/CTypeHandler.cpp \
    src/CTile.cpp \
    src/mainwindow.cpp \
    src/CAnimatedObject.cpp \
    src/CAnimation.cpp \
    src/CAnimationProvider.cpp \
    src/CBuilding.cpp \
    src/CConfigurationProvider.cpp \
    src/CCreature.cpp \
    src/CGamePanel.cpp \
    src/CInteraction.cpp \
    src/CMap.cpp \
    src/CMapObject.cpp \
    src/CPathFinder.cpp \
    src/CReflection.cpp \
    src/ReflectTypes.cpp

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
    src/CAnimatedObject.h \
    src/CAnimation.h \
    src/CAnimationProvider.h \
    src/CBuilding.h \
    src/CConfigurationProvider.h \
    src/CCreature.h \
    src/CGamePanel.h \
    src/CInteraction.h \
    src/CMap.h \
    src/CMapObject.h \
    src/CPathFinder.h \
    src/CReflection.h \
    src/CGameScene.h \
    src/CGameView.h \
    src/item.h \
    src/CItemSlot.h \
    src/CLootProvider.h \
    src/mainwindow.h \
    src/playerequippedview.h \
    src/playerlistview.h \
    src/playerstatsview.h \
    src/potion.h \
    src/CScriptEngine.h \
    src/stats.h \
    src/CTypeHandler.h \
    src/CTile.h \
    src/util.h

FORMS += \
    src/mainwindow.ui

DEFINES += GAME_RECOVERY_PREFIXED_SCENE_HEADER

DEFINES += GAME_RECOVERY_PREFIXED_TILE
