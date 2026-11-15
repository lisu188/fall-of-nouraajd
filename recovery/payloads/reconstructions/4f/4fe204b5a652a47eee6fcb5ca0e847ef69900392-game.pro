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

# Explicit selection of this reconstructed, changing lowercase application project.
GAME_RECOVERY_APPLICATION = true

SOURCES += \
    src/CAnimatedObject.cpp \
    src/CAnimation.cpp \
    src/CAnimationProvider.cpp \
    src/CBuilding.cpp \
    src/CConfigurationProvider.cpp \
    src/CCreature.cpp \
    src/CGamePanel.cpp \
    src/CGameScene.cpp \
    src/CGameView.cpp \
    src/CInteraction.cpp \
    src/CItemSlot.cpp \
    src/CLootProvider.cpp \
    src/CMap.cpp \
    src/CMapObject.cpp \
    src/CPathFinder.cpp \
    src/CReflection.cpp \
    src/CScriptEngine.cpp \
    src/CTile.cpp \
    src/GameScript.cpp \
    src/ReflectTypes.cpp \
    src/item.cpp \
    src/main.cpp \
    src/mainwindow.cpp \
    src/playerequippedview.cpp \
    src/playerlistview.cpp \
    src/playerstatsview.cpp \
    src/potion.cpp \
    src/stats.cpp

HEADERS += \
    src/CAnimatedObject.h \
    src/CAnimation.h \
    src/CAnimationProvider.h \
    src/CBuilding.h \
    src/CConfigurationProvider.h \
    src/CCreature.h \
    src/CGamePanel.h \
    src/CGameScene.h \
    src/CGameView.h \
    src/CInteraction.h \
    src/CItemSlot.h \
    src/CLootProvider.h \
    src/CMap.h \
    src/CMapObject.h \
    src/CPathFinder.h \
    src/CReflection.h \
    src/CScriptEngine.h \
    src/CTile.h \
    src/CTypeHandler.h \
    src/item.h \
    src/mainwindow.h \
    src/playerequippedview.h \
    src/playerlistview.h \
    src/playerstatsview.h \
    src/potion.h \
    src/stats.h \
    src/util.h

LIBS += -L/lib64/ -lpython2.7 -lboost_python
INCLUDEPATH += /usr/include/python2.7 /usr/include
DEPENDPATH += /usr/include/python2.7 /usr/include

FORMS += \
    src/mainwindow.ui

# Header/class renames inside an unchanged missing module blob use surviving path facts.
exists($$PWD/src/CTile.h):DEFINES += GAME_RECOVERY_PREFIXED_TILE
exists($$PWD/src/CGameScene.h):DEFINES += GAME_RECOVERY_PREFIXED_SCENE_HEADER
