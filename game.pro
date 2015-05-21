QT += core gui opengl widgets

TARGET = game
TEMPLATE = app

SOURCES += \
     CPathFinder.cpp \
     CMap.cpp \
     gui/CGameView.cpp \
     gui/CMainWindow.cpp \
     gui/CPlayerView.cpp \
     CMain.cpp \
    CScriptLoader.cpp \
    handler/CObjectHandler.cpp \
    handler/CEventHandler.cpp \
    handler/CGuiHandler.cpp \
    panel/CFightPanel.cpp \
    panel/CTextPanel.cpp \
    panel/CCharPanel.cpp \
    object/CTile.cpp \
    object/CMapObject.cpp \
    object/CItem.cpp \
    object/CInteraction.cpp \
    object/CCreature.cpp \
    object/CBuilding.cpp \
    object/CAnimatedObject.cpp \
    handler/CScriptHandler.cpp \
    provider/CResourcesProvider.cpp \
    provider/CConfigurationProvider.cpp \
    provider/CAnimationProvider.cpp \
    handler/CLootHandler.cpp \
    object/CPlayer.cpp \
    object/CMonster.cpp \
    object/CEffect.cpp \
    object/CGameObject.cpp \
    object/CEvent.cpp \
    object/CTrigger.cpp \
    object/CQuest.cpp \
    handler/CQuestHandler.cpp \
    panel/CTradePanel.cpp \
    handler/CMouseHandler.cpp \
    panel/CGamePanel.cpp \
    object/CMarket.cpp \
    CMapLoader.cpp \
    CGame.cpp \
    CThreadUtil.cpp \
    CGameScript.cpp \
    CStats.cpp \
    CUtil.cpp \
    gui/CScriptWindow.cpp

HEADERS += \
     CPathFinder.h \
     CMap.h \
     gui/CGameView.h \
     gui/CMainWindow.h \
     gui/CPlayerView.h \
    CScriptLoader.h \
    handler/CHandler.h \
    handler/CObjectHandler.h \
    handler/CEventHandler.h \
    handler/CGuiHandler.h \
    object/CObject.h \
    object/CTile.h \
    object/CMapObject.h \
    object/CItem.h \
    object/CInteraction.h \
    object/CCreature.h \
    object/CBuilding.h \
    object/CAnimatedObject.h \
    panel/CPanel.h \
    panel/CTextPanel.h \
    panel/CFightPanel.h \
    panel/CCharPanel.h \
    panel/CGamePanel.h \
    handler/CScriptHandler.h \
    handler/CLootHandler.h \
    provider/CResourcesProvider.h \
    provider/CConfigurationProvider.h \
    provider/CAnimationProvider.h \
    provider/CProvider.h \
    object/CPlayer.h \
    object/CMonster.h \
    object/CEffect.h \
    object/CGameObject.h \
    object/CEvent.h \
    object/CTrigger.h \
    object/CQuest.h \
    handler/CQuestHandler.h \
    panel/CTradePanel.h \
    handler/CMouseHandler.h \
    object/CMarket.h \
    CMapLoader.h \
    CGame.h \
    CThreadUtil.h \
    CStats.h \
    CUtil.h \
    CGlobal.h \
    gui/CGui.h \
    gui/CScriptWindow.h

FORMS += \
     gui/CMainWindow.ui \
    gui/CScriptWindow.ui

RESOURCES += \
    scripts.qrc \
    maps.qrc \
    images.qrc \
    config.qrc

OTHER_FILES += \
    format.py \
    reindent.py

QMAKE_CXXFLAGS = -std=c++14 "-include cmath" -Wno-deprecated-declarations -Wno-unused-local-typedefs -Wno-attributes
QMAKE_CXXFLAGS_RELEASE = -O3 -flto -march=native
QMAKE_LFLAGS_RELEASE = -O3 -flto -march=native
QMAKE_CXXFLAGS_DEBUG = -g3
QMAKE_RESOURCE_FLAGS = -threshold 0 -compress 9

DEFINES += "QT_NO_KEYWORDS"

CONFIG(release,debug|release){
    DEFINES += "QT_NO_DEBUG_OUTPUT"
}

CONFIG(debug,debug|release){
    CONFIG +=console
}

LIBS += -L/usr/local/lib -L/home/andrzejlis/boost_1_58_0/stage/lib -lpython3.4m -ldl -fPIC -lutil -lboost_python3

INCLUDEPATH += /usr/local/include/python3.4m
DEPENDPATH += /usr/local/include/python3.4m
INCLUDEPATH += /home/andrzejlis/boost_1_58_0
DEPENDPATH += /home/andrzejlis/boost_1_58_0


