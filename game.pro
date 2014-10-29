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
     CAnimationProvider.cpp \
     CConfigurationProvider.cpp \
     CPathFinder.cpp \
     GameScript.cpp \
     CMap.cpp \
     CGameScene.cpp \
     CGameView.cpp \
     CLootProvider.cpp \
     CInteraction.cpp \
     CScriptEngine.cpp \
     CTile.cpp \
     CMainWindow.cpp \
     CPlayerView.cpp \
     CItem.cpp \
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
    mapObject/CMapObject.cpp \
    mapObject/CCreature.cpp \
    mapObject/CBuilding.cpp \
    mapObject/CAnimatedObject.cpp \
    handler/CTypeHandler.cpp \
    handler/CResourcesHandler.cpp \
    handler/CObjectHandler.cpp \
    handler/CEventHandler.cpp \
    handler/CGuiHandler.cpp \
    panel/CFightPanel.cpp \
    panel/CTextPanel.cpp \
    panel/CCharPanel.cpp

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
     CMainWindow.h \
     CPlayerView.h \
     CItem.h \
     Stats.h \
     Util.h \
    CScriptLoader.h \
    handler/CHandler.h


android{
    SOURCES += android/posix.c
    HEADERS += android/posix.h
}

unix:LIBS += -L/usr/local/lib -lpython3.4m -ldl -fPIC -lutil
win32:LIBS += -LC:\Python34\libs -lpython34
android{
    LIBS -= -L/usr/local/lib -lpython3.4m -ldl -fPIC -lutil
    LIBS += -L/home/andrzejlis/python3-android/build/9d-19-arm-linux-androideabi-4.8/lib -lpython3.3m
}

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

