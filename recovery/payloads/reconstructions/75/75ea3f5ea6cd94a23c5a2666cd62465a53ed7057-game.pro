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
    src/animatedobject.cpp \
    src/animation.cpp \
    src/animationprovider.cpp \
    src/building.cpp \
    src/charview.cpp \
    src/configurationprovider.cpp \
    src/creature.cpp \
    src/event.cpp \
    src/fightview.cpp \
    src/gamescene.cpp \
    src/gamescript.cpp \
    src/gameview.cpp \
    src/interaction.cpp \
    src/item.cpp \
    src/itemslot.cpp \
    src/lootprovider.cpp \
    src/main.cpp \
    src/mainwindow.cpp \
    src/map.cpp \
    src/monster.cpp \
    src/pathfinder.cpp \
    src/player.cpp \
    src/playerabstractview.cpp \
    src/playerequippedview.cpp \
    src/playerlistview.cpp \
    src/playerstatsview.cpp \
    src/potion.cpp \
    src/scriptmanager.cpp \
    src/scrollobject.cpp \
    src/stats.cpp \
    src/tile.cpp

HEADERS += \
    src/animatedobject.h \
    src/animation.h \
    src/animationprovider.h \
    src/building.h \
    src/charview.h \
    src/configurationprovider.h \
    src/creature.h \
    src/event.h \
    src/fightview.h \
    src/gamescene.h \
    src/gamescript.h \
    src/gameview.h \
    src/interaction.h \
    src/item.h \
    src/itemslot.h \
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

LIBS += -L/lib64/ -lpython2.7 -lboost_python
INCLUDEPATH += /usr/include/python2.7 /usr/include
DEPENDPATH += /usr/include/python2.7 /usr/include

FORMS += \
    src/mainwindow.ui
