cmake_minimum_required(VERSION 3.3)
project(game)

include(${CMAKE_SOURCE_DIR}/cmake/cotire.cmake)
set(CMAKE_MODULE_PATH "${CMAKE_MODULE_PATH};${CMAKE_SOURCE_DIR}/cmake")

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++14 -include cmath -Wno-deprecated-declarations -Wno-unused-local-typedefs -Wno-attributes -Wno-inline")

set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -O3")
set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -g3")

file(GLOB_RECURSE GAME_SRC ${CMAKE_SOURCE_DIR}/src/**.cpp ${CMAKE_SOURCE_DIR}/src/**.h)

find_package(Boost 1.60 COMPONENTS python3 filesystem system REQUIRED)
find_package(PythonInterp 3.5 REQUIRED)
find_package(PythonLibs 3.5 REQUIRED)
find_package(SDL2 REQUIRED)
find_package(JsonCpp REQUIRED)

include_directories(${Boost_INCLUDE_DIRS})
include_directories(${PYTHON_INCLUDE_DIRS})
include_directories(${SDL2_INCLUDE_DIR})
include_directories(${JSONCPP_INCLUDE_DIRS})

include_directories(${CMAKE_SOURCE_DIR}/src)

include_directories(${CMAKE_SOURCE_DIR}/vstd)

python_add_module(_game ${GAME_SRC})
target_link_libraries(_game ${Boost_LIBRARIES} ${PYTHON_LIBRARIES} ${SDL2_LIBRARY} ${JSONCPP_LIBRARIES})

configure_file(res/config/armors.json config/armors.json)
configure_file(res/config/buildings.json config/buildings.json)
configure_file(res/config/effects.json config/effects.json)
configure_file(res/config/interactions.json config/interactions.json)
configure_file(res/config/items.json config/items.json)
configure_file(res/config/misc.json config/misc.json)
configure_file(res/config/monsters.json config/monsters.json)
configure_file(res/config/potions.json config/potions.json)
configure_file(res/config/slots.json config/slots.json)
configure_file(res/config/tiles.json config/tiles.json)
configure_file(res/config/weapons.json config/weapons.json)

configure_file(res/maps/map1/config.json maps/map1/config.json)
configure_file(res/maps/map1/map.json maps/map1/map.json)
configure_file(res/maps/map1/script.py maps/map1/script.py)

configure_file(res/maps/map2/config.json maps/map2/config.json)
configure_file(res/maps/map2/map.json maps/map2/map.json)
configure_file(res/maps/map2/script.py maps/map2/script.py)


configure_file(res/maps/empty/config.json maps/empty/config.json)
configure_file(res/maps/empty/map.json maps/empty/map.json)
configure_file(res/maps/empty/script.py maps/empty/script.py)


configure_file(res/plugins/effect.py plugins/effect.py)
configure_file(res/plugins/interaction.py plugins/interaction.py)
configure_file(res/plugins/object.py plugins/object.py)
configure_file(res/plugins/potion.py plugins/potion.py)
configure_file(res/plugins/tile.py plugins/tile.py)

configure_file(res/game.py game.py)

configure_file(test/run_turns.py test/run_turns.py)
configure_file(test/all_objects.py test/all_objects.py)

cotire(_game)