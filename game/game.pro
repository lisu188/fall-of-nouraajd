 # ------------------------------------------------ -
 #
 # Project created by QtCreator 2013 - 10 - 30T13 : 16 : 43
 #
 # ------------------------------------------------ -

QT += core gui opengl widgets

TARGET = game
TEMPLATE = app
win32{
    CONFIG +=console
}
include(../game.pri)

SOURCES += \
     CReflection.cpp \
     ReflectTypes.cpp \
     CAnimatedObject.cpp \
     CAnimationProvider.cpp \
     CBuilding.cpp \
     CConfigurationProvider.cpp \
     CCreature.cpp \
     CMapObject.cpp \
     CPathFinder.cpp \
     CGamePanel.cpp \
     GameScript.cpp \
     CMap.cpp \
     CGameScene.cpp \
     CGameView.cpp \
     CLootProvider.cpp \
     CInteraction.cpp \
     CScriptEngine.cpp \
     CTile.cpp \
     CTypeHandler.cpp \
     CMainWindow.cpp \
     CPlayerView.cpp \
     CItem.cpp \
     Stats.cpp \
     CMain.cpp \
     CObjectHandler.cpp \
     CGuiHandler.cpp

HEADERS += \
     CReflection.h \
     CAnimatedObject.h \
     CAnimationProvider.h \
     CBuilding.h \
     CConfigurationProvider.h \
     CCreature.h \
     CMapObject.h \
     CPathFinder.h \
     CGamePanel.h \
     CInteraction.h \
     CMap.h \
     CGameScene.h \
     CGameView.h \
     CLootProvider.h \
     CScriptEngine.h \
     CTile.h \
     CTypeHandler.h \
     CMainWindow.h \
     CPlayerView.h \
     CItem.h \
     Stats.h \
     Util.h \
     CObjectHandler.h \
     CGuiHandler.h

unix:LIBS += -L../python -lpython
win32:CONFIG(release,debug|release)LIBS += -L../python/release -lpython
win32:CONFIG(debug,debug|release)LIBS += -L../python/debug -lpython

unix:LIBS += -L../resources -lresources
win32:CONFIG(release,debug|release)LIBS += -L../resources/release -lresources
win32:CONFIG(debug,debug|release)LIBS += -L../resources/debug -lresources

unix:LIBS += -L/usr/local/lib -lpython3.4m -ldl -fPIC -lutil
win32:LIBS += -LC:\Python34\libs -lpython34

FORMS += \
     CMainWindow.ui

