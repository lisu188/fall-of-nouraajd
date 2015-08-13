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
   CGame.cpp \
   CThreadUtil.cpp \
   CStats.cpp \
   CUtil.cpp \
   gui/CScriptWindow.cpp \
   scripting/CGameScript.cpp \
   scripting/CWrapper.cpp \
   scripting/CConverter.cpp \
   scripting/CScriptLoader.cpp \
   loader/CGameLoader.cpp \
   loader/CMapLoader.cpp \
   CSerialization.cpp \
   CJsonUtil.cpp \
    CTypes.cpp

HEADERS += \
   CPathFinder.h \
   CMap.h \
   gui/CGameView.h \
   gui/CMainWindow.h \
   gui/CPlayerView.h \
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
   CGame.h \
   CThreadUtil.h \
   CStats.h \
   CUtil.h \
   CGlobal.h \
   gui/CGui.h \
   gui/CScriptWindow.h \
   scripting/CWrapper.h \
   scripting/CScripting.h \
   scripting/CConverter.h \
   scripting/CGameScript.h \
   scripting/CScriptLoader.h \
   loader/CMapLoader.h \
   loader/CGameLoader.h \
   loader/CLoader.h \
   CSerialization.h \
   CJsonUtil.h \
    templates/cast.h \
    templates/traits.h \
    templates/lazy.h \
    templates/hash.h \
    templates/assert.h \
    templates/functional.h \
    templates/hex.h \
    CTypes.h \
    templates/converter.h

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
  bugs.txt

QMAKE_CXXFLAGS = -std=c++14 "-include cmath" -Wno-deprecated-declarations -Wno-unused-local-typedefs -Wno-attributes
QMAKE_CXXFLAGS_RELEASE = -O3 -march=native
QMAKE_LFLAGS_RELEASE = -O3 -march=native
QMAKE_CXXFLAGS_DEBUG = -g3
QMAKE_RESOURCE_FLAGS = -threshold 0 -compress 9


QMAKE_CXXFLAGS_RELEASE += -flto
QMAKE_LFLAGS_RELEASE += -flto


DEFINES += "QT_NO_KEYWORDS"

CONFIG(release,debug|release){
  DEFINES += "QT_NO_DEBUG_OUTPUT"
}

CONFIG(debug,debug|release){
  CONFIG += console
  DEFINES += "DEBUG_MODE"
}

unix{
  LIBS += -L/usr/local/lib -L/home/andrzejlis/boost_1_58_0/stage/lib -lpython3.4m -ldl -fPIC -lutil -lboost_python3
  INCLUDEPATH += /usr/local/include/python3.4m
  DEPENDPATH += /usr/local/include/python3.4m
  INCLUDEPATH += /home/andrzejlis/boost_1_58_0
  DEPENDPATH += /home/andrzejlis/boost_1_58_0
}

win32{
  CONFIG(release,debug|release){
    LIBS += -lboost_python3-mgw49-mt-1_58
  }
  CONFIG(debug,debug|release){
    LIBS += -lboost_python3-mgw49-mt-d-1_58
  }
  LIBS += -LC:\boost_1_58_0\stage\lib -LC:\Python34\libs -fPIC -lpython34
  INCLUDEPATH += C:\Python34\include
  DEPENDPATH += C:\Python34\include
  INCLUDEPATH += C:\boost_1_58_0
  DEPENDPATH += C:\boost_1_58_0
}




