cmake_minimum_required(VERSION 3.16)
project(game LANGUAGES CXX)

set(CMAKE_INCLUDE_CURRENT_DIR ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(QT NAMES Qt6 REQUIRED COMPONENTS Widgets OpenGL OpenGLWidgets)
find_package(Qt${QT_VERSION_MAJOR} REQUIRED COMPONENTS Widgets OpenGL OpenGLWidgets)

find_package(Python3 REQUIRED COMPONENTS Development)
set(PYTHONLIBS_FOUND ON)

set(BOOST_PYTHON_COMPONENT "python${Python3_VERSION_MAJOR}${Python3_VERSION_MINOR}")
set(Boost_NO_BOOST_CMAKE ON)
find_package(Boost 1.58 REQUIRED COMPONENTS system ${BOOST_PYTHON_COMPONENT})
find_package(Threads REQUIRED)

add_compile_options(
        -include
        cmath
        -Wno-deprecated-declarations
        -Wno-unused-local-typedefs
        -Wno-attributes)
add_compile_definitions(QT_NO_KEYWORDS QT_NO_FOREACH)

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
        core/CUtil.h
        gui/CMainWindow.ui
        gui/CScriptWindow.ui
        resources/resources.qrc)

add_subdirectory(vstd)

add_executable(game ${SOURCE_FILES})

target_include_directories(game PRIVATE ${Boost_INCLUDE_DIRS})
target_include_directories(game PRIVATE ${Python3_INCLUDE_DIRS})

target_link_libraries(game PRIVATE
        Qt${QT_VERSION_MAJOR}::Widgets
        Qt${QT_VERSION_MAJOR}::OpenGL
        Qt${QT_VERSION_MAJOR}::OpenGLWidgets
        ${Boost_LIBRARIES}
        Python3::Python
        Threads::Threads)
