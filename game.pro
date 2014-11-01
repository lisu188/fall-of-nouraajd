 # ------------------------------------------------ -
 #
 # Project created by QtCreator 2013 - 10 - 30T13 : 16 : 43
 #
 # ------------------------------------------------ -

QT += core gui opengl widgets

TARGET = game
TEMPLATE = app

include(game.pri)

SOURCES += \
     CReflection.cpp \
     ReflectTypes.cpp \
     CPathFinder.cpp \
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
    object/CEvent.cpp

HEADERS += \
     CPathFinder.h \
     CMap.h \
     CGameScene.h \
     CGameView.h \
     CMainWindow.h \
     CPlayerView.h \
     Stats.h \
     Util.h \
    CScriptLoader.h \
    handler/CHandler.h \
    handler/CObjectHandler.h \
    handler/CEventHandler.h \
    handler/CTypeHandler.h \
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
    CReflection.h \
    object/CPlayer.h \
    object/CMonster.h \
    object/CEffect.h \
    object/CGameObject.h \
    object/CEvent.h


unix:LIBS += -L/usr/local/lib -lpython3.4m -ldl -fPIC -lutil
win32:LIBS += -LC:\Python34\libs -lpython34

FORMS += \
     CMainWindow.ui

RESOURCES += \
    scripts.qrc \
    maps.qrc \
    images.qrc \
    config.qrc

OTHER_FILES += \
    format.py \
    reindent.py

