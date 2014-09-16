 # ------------------------------------------------ -
 #
 # Project created by QtCreator 2013 - 10 - 30T13 : 16 : 43
 #
 # ------------------------------------------------ -

QT += core gui opengl widgets

TARGET = Game
TEMPLATE = app
#CONFIG += console

QMAKE_CXXFLAGS += -std=c++11
QMAKE_CXXFLAGS_RELEASE -= -Os
QMAKE_CXXFLAGS_RELEASE -= -O
QMAKE_CXXFLAGS_RELEASE -= -O1
QMAKE_CXXFLAGS_RELEASE -= -O2
QMAKE_CXXFLAGS_RELEASE *= -O3
QMAKE_CXXFLAGS_RELEASE += -flto -march=native
QMAKE_LFLAGS_RELEASE -= -Os
QMAKE_LFLAGS_RELEASE -= -O
QMAKE_LFLAGS_RELEASE -= -O1
QMAKE_LFLAGS_RELEASE -= -O2
QMAKE_LFLAGS_RELEASE *= -O3
QMAKE_LFLAGS_RELEASE += -flto -march=native
QMAKE_CXXFLAGS_DEBUG -= -g
QMAKE_CXXFLAGS_DEBUG -= -g0
QMAKE_CXXFLAGS_DEBUG -= -g1
QMAKE_CXXFLAGS_DEBUG -= -g2
QMAKE_CXXFLAGS_DEBUG *= -g3
#DEFINES += "QT_NO_KEYWORDS"

SOURCES += \
    src/CReflection.cpp \
    src/ReflectTypes.cpp \
    src/CAnimatedObject.cpp \
    src/CAnimationProvider.cpp \
    src/CBuilding.cpp \
    src/CConfigurationProvider.cpp \
    src/CCreature.cpp \
    src/CMapObject.cpp \
    src/CPathFinder.cpp \
    src/CGamePanel.cpp \
    src/GameScript.cpp \
    src/CMap.cpp \
    src/CGameScene.cpp \
    src/CGameView.cpp \
    src/CLootProvider.cpp \
    src/CInteraction.cpp \
    src/CScriptEngine.cpp \
    src/CTile.cpp \
    src/CTypeHandler.cpp \
    src/CMainWindow.cpp \
    src/CPlayerView.cpp \
    src/CItem.cpp \
    src/Stats.cpp \
    src/CMain.cpp \
    src/CObjectHandler.cpp

HEADERS += \
    src/CReflection.h \
    src/CAnimatedObject.h \
    src/CAnimationProvider.h \
    src/CBuilding.h \
    src/CConfigurationProvider.h \
    src/CCreature.h \
    src/CMapObject.h \
    src/CPathFinder.h \
    src/CGamePanel.h \
    src/CInteraction.h \
    src/CMap.h \
    src/CGameScene.h \
    src/CGameView.h \
    src/CLootProvider.h \
    src/CScriptEngine.h \
    src/CTile.h \
    src/CTypeHandler.h \
    src/CMainWindow.h \
    src/CPlayerView.h \
    src/CItem.h \
    src/Stats.h \
    src/Util.h \
    src/CObjectHandler.h

OTHER_FILES += \
    res/scripts/cave.py \
    res/config/terrain.png \
    res/scripts/teleporter.py \
    scripts/hashlib.py \
    scripts/random.py \
    scripts/types.py \
    scripts/warnings.py \
    config/effects.json \
    config/interactions.json \
    config/object.json \
    config/slots.json \
    config/tiles.json \
    config/terrain.png \
    config/map.tmx \
    deploy.bat \
    maps/terrain.png \
    scripts/Objects.py \
    scripts/Interactions.py \
    scripts/game/__init__.py \
    scripts/game/interaction.py \
    scripts/game/object.py \
    format.py \
    config/objects/armors.json \
    config/objects/buildings.json \
    config/objects/effects.json \
    config/objects/interactions.json \
    config/objects/items.json \
    config/objects/misc.json \
    config/objects/monsters.json \
    config/objects/potions.json \
    config/objects/tiles.json \
    config/objects/weapons.json \
    maps/map.json

LIBS += -L/lib64/ -lpython2.7
LIBS += -L/lib64/ -lboost_python

INCLUDEPATH += /usr/include/python2.7
DEPENDPATH += /usr/include/python2.7

INCLUDEPATH += /usr/include
DEPENDPATH += /usr/include

FORMS += \
    src/CMainWindow.ui
