 # ------------------------------------------------ -
 #
 # Project created by QtCreator 2013 - 10 - 30T13 : 16 : 43
 #
 # ------------------------------------------------ -

QT += core gui opengl widgets

TARGET = game
TEMPLATE = app

include(game.pri)
unix:LIBS += -lboost_python3 -lpython3.4m
INCLUDEPATH += /usr/local/include/python3.4m

SOURCES += CPathFinder.cpp \
    GameScript.cpp \
    CMap.cpp \
    CGameScene.cpp \
    CGameView.cpp \
    CMainWindow.cpp \
    CPlayerView.cpp \
    Stats.cpp \
    CMain.cpp \
    boost/python/dict.cpp \
    boost/python/errors.cpp \
    boost/python/exec.cpp \
    boost/python/import.cpp \
    boost/python/list.cpp \
    boost/python/long.cpp \
    boost/python/module.cpp \
    boost/python/numeric.cpp \
    boost/python/object_operators.cpp \
    boost/python/object_protocol.cpp \
    boost/python/slice.cpp \
    boost/python/str.cpp \
    boost/python/tuple.cpp \
    boost/python/wrapper.cpp \
    boost/python/converter/arg_to_python_base.cpp \
    boost/python/converter/builtin_converters.cpp \
    boost/python/converter/from_python.cpp \
    boost/python/converter/registry.cpp \
    boost/python/converter/type_id.cpp \
    boost/python/object/class.cpp \
    boost/python/object/enum.cpp \
    boost/python/object/function.cpp \
    boost/python/object/function_doc_signature.cpp \
    boost/python/object/inheritance.cpp \
    boost/python/object/iterator.cpp \
    boost/python/object/life_support.cpp \
    boost/python/object/pickle_support.cpp \
    boost/python/object/stl_iterator.cpp \
    CScriptLoader.cpp \
    handler/CTypeHandler.cpp \
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
    handler/CQuestHandler.cpp \
    object/CQuest.cpp \
    panel/CTradePanel.cpp \
    handler/CMouseHandler.cpp \
    Util.cpp \
    panel/CGamePanel.cpp \
    object/CMarket.cpp \
    CAnimation.cpp

HEADERS  += \
    CAnimation.h \
    CGameScene.h \
    CGameView.h \
    CMainWindow.h \
    CMap.h \
    CPathFinder.h \
    CPlayerView.h \
    CScriptLoader.h \
    Stats.h \
    Util.h \
    handler/CEventHandler.h \
    handler/CGuiHandler.h \
    handler/CHandler.h \
    handler/CLootHandler.h \
    handler/CMouseHandler.h \
    handler/CObjectHandler.h \
    handler/CQuestHandler.h \
    handler/CScriptHandler.h \
    handler/CTypeHandler.h \
    object/CAnimatedObject.h \
    object/CBuilding.h \
    object/CCreature.h \
    object/CEffect.h \
    object/CEvent.h \
    object/CGameObject.h \
    object/CInteraction.h \
    object/CItem.h \
    object/CMapObject.h \
    object/CMarket.h \
    object/CMonster.h \
    object/CObject.h \
    object/CPlayer.h \
    object/CQuest.h \
    object/CTile.h \
    object/CTrigger.h \
    panel/CCharPanel.h \
    panel/CFightPanel.h \
    panel/CGamePanel.h \
    panel/CPanel.h \
    panel/CTextPanel.h \
    panel/CTradePanel.h \
    provider/CAnimationProvider.h \
    provider/CConfigurationProvider.h \
    provider/CProvider.h \
    provider/CResourcesProvider.h

RESOURCES += \
    config.qrc \
    images.qrc \
    maps.qrc \
    scripts.qrc

FORMS += \
    CMainWindow.ui
