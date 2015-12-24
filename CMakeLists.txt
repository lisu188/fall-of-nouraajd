cmake_minimum_required(VERSION 3.3)
project(game)

set(CMAKE_SOURCE_DIR ${CMAKE_SOURCE_DIR} $ENV{QT_CMAKE})

include($ENV{COTIRE_CMAKE}/cotire.cmake)

set(CMAKE_INCLUDE_CURRENT_DIR ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt5 COMPONENTS Widgets OpenGL REQUIRED)

set(BOOST_INCLUDEDIR $ENV{BOOST_INC})
set(BOOST_LIBRARYDIR $ENV{BOOST_LIB})
FIND_PACKAGE(Boost 1.58 COMPONENTS system python3 thread REQUIRED)

set(PYTHON_LIBRARY $ENV{PYTHON_LIB}/libpython34.a)
set(PYTHON_INCLUDE_DIR $ENV{PYTHON_INC})
find_package(PythonLibs REQUIRED)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++14 -include cmath -Wno-deprecated-declarations -Wno-unused-local-typedefs -Wno-attributes")

set(SOURCE_FILES
        controller/CController.cpp
        controller/CController.h
        controller/CControllers.h
        controller/CTargetController.cpp
        controller/CTargetController.h
        gui/CGameView.cpp
        gui/CGameView.h
        gui/CGui.h
        gui/CMainWindow.cpp
        gui/CMainWindow.h
        gui/CPlayerView.cpp
        gui/CPlayerView.h
        gui/CScriptWindow.cpp
        gui/CScriptWindow.h
        handler/CEventHandler.cpp
        handler/CEventHandler.h
        handler/CGuiHandler.cpp
        handler/CGuiHandler.h
        handler/CHandler.h
        handler/CLootHandler.cpp
        handler/CLootHandler.h
        handler/CMouseHandler.cpp
        handler/CMouseHandler.h
        handler/CObjectHandler.cpp
        handler/CObjectHandler.h
        handler/CQuestHandler.cpp
        handler/CQuestHandler.h
        handler/CScriptHandler.cpp
        handler/CScriptHandler.h
        loader/CGameLoader.cpp
        loader/CGameLoader.h
        loader/CLoader.h
        loader/CMapLoader.cpp
        loader/CMapLoader.h
        object/CAnimatedObject.cpp
        object/CAnimatedObject.h
        object/CBuilding.cpp
        object/CBuilding.h
        object/CCreature.cpp
        object/CCreature.h
        object/CEffect.cpp
        object/CEffect.h
        object/CEvent.cpp
        object/CEvent.h
        object/CGameObject.cpp
        object/CGameObject.h
        object/CInteraction.cpp
        object/CInteraction.h
        object/CItem.cpp
        object/CItem.h
        object/CMapObject.cpp
        object/CMapObject.h
        object/CMarket.cpp
        object/CMarket.h
        object/CMonster.cpp
        object/CMonster.h
        object/CObject.h
        object/CPlayer.cpp
        object/CPlayer.h
        object/CQuest.cpp
        object/CQuest.h
        object/CTile.cpp
        object/CTile.h
        object/CTrigger.cpp
        object/CTrigger.h
        panel/CCharPanel.cpp
        panel/CCharPanel.h
        panel/CFightPanel.cpp
        panel/CFightPanel.h
        panel/CGamePanel.cpp
        panel/CGamePanel.h
        panel/CPanel.h
        panel/CTextPanel.cpp
        panel/CTextPanel.h
        panel/CTradePanel.cpp
        panel/CTradePanel.h
        provider/CAnimationProvider.cpp
        provider/CAnimationProvider.h
        provider/CConfigurationProvider.cpp
        provider/CConfigurationProvider.h
        provider/CProvider.h
        provider/CResourcesProvider.cpp
        provider/CResourcesProvider.h
        scripting/CConverter.cpp
        scripting/CConverter.h
        scripting/CGameScript.cpp
        scripting/CGameScript.h
        scripting/CScripting.h
        scripting/CScriptLoader.cpp
        scripting/CScriptLoader.h
        scripting/CWrapper.cpp
        scripting/CWrapper.h
        templates/adaptors.h
        templates/assert.h
        templates/cast.h
        templates/converter.h
        templates/functional.h
        templates/future.h
        templates/hash.h
        templates/hex.h
        templates/lazy.h
        templates/thread.h
        templates/threadpool.h
        templates/traits.h
        templates/util.h
        types/ctypes1.cpp
        types/ctypes2.cpp
        CDefines.h
        CGame.cpp
        CGame.h
        CGlobal.h
        CJsonUtil.cpp
        CJsonUtil.h
        CMain.cpp
        CMap.cpp
        CMap.h
        CPathFinder.cpp
        CPathFinder.h
        CSerialization.cpp
        CSerialization.h
        CStats.cpp
        CStats.h
        CTypes.cpp
        CTypes.h
        CUtil.cpp
        CUtil.h)

qt5_wrap_ui(FOMRS_SOURCE_FILES gui/CMainWindow.ui gui/CScriptWindow.ui)
qt5_add_resources(RESOURCE_FILES resources/resources.qrc)

include_directories(${Boost_INCLUDE_DIRS})
include_directories(${PYTHON_INCLUDE_DIRS})

add_executable(game ${SOURCE_FILES} ${FOMRS_SOURCE_FILES} ${RESOURCE_FILES})

qt5_use_modules(game Widgets)
qt5_use_modules(game OpenGL)

target_link_libraries(game ${Boost_LIBRARIES})
target_link_libraries(game ${PYTHON_LIBRARIES})

cotire(game)