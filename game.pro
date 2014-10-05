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

include(game.pri)

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
     CGuiHandler.cpp \
    CResourcesHandler.cpp \
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
    CScriptLoader.cpp

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
     CGuiHandler.h \
    CResourcesHandler.h \
    CScriptLoader.h

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

