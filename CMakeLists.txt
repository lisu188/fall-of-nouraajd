cmake_minimum_required(VERSION 3.3)
project(game)

include($ENV{COTIRE_CMAKE}/cotire.cmake)

set(CMAKE_INCLUDE_CURRENT_DIR ON)

set(BOOST_INCLUDEDIR $ENV{BOOST_INC})
set(BOOST_LIBRARYDIR $ENV{BOOST_LIB})
find_package(Boost 1.58)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -DBOOST_DISABLE_ASSERTS -std=c++14 -include cmath -Wno-deprecated-declarations -Wno-unused-local-typedefs -Wno-attributes")

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
        types/ctypes1.cpp
        types/ctypes2.cpp
        core/CDefines.h
        core/CGame.cpp
        core/CGame.h
        core/CGlobal.h
        core/CJsonUtil.cpp
        core/CJsonUtil.h
        core/CMain.cpp
        core/CMap.cpp
        core/CMap.h
        core/CPathFinder.cpp
        core/CPathFinder.h
        core/CSerialization.cpp
        core/CSerialization.h
        core/CStats.cpp
        core/CStats.h
        core/CTypes.cpp
        core/CTypes.h
        core/CUtil.cpp
        core/CUtil.h)

file(GLOB_RECURSE UMOF_SRC umof/src/**.cpp umof/src/**.h)
file(GLOB_RECURSE VSTD_SRC vstd/src/**.cpp vstd/src/**.h)
file(GLOB_RECURSE BOOST_PYTHON_SRC python/src/**.cpp python/src/**.h)

include_directories(${Boost_INCLUDE_DIRS})
include_directories(C:/Users/Andrzej/AppData/Local/Programs/Python/Python35/include) #TODO: ugh!

include_directories(umof/src)
include_directories(vstd/src)
include_directories(python/src)

add_executable(game ${SOURCE_FILES} ${UMOF_SRC} ${VSTD_SRC} ${BOOST_PYTHON_SRC})

add_custom_command(TARGET game PRE_BUILD COMMAND format.py WORKING_DIRECTORY ${CMAKE_SOURCE_DIR})

target_link_libraries(game $ENV{PYTHON_LIB}/libpython35.a)

cotire(game)