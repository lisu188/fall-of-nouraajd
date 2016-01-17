cmake_minimum_required(VERSION 3.3)
project(game)

include(../cotire/cmake/cotire.cmake)
set(CMAKE_MODULE_PATH "${CMAKE_MODULE_PATH};${CMAKE_SOURCE_DIR}/../sdl2")

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++14 -include cmath -Wno-deprecated-declarations -Wno-unused-local-typedefs -Wno-attributes -Wa,-mbig-obj -Wno-inline")

set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -O3")
set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -g3")

file(GLOB_RECURSE GAME_SRC ${CMAKE_SOURCE_DIR}/src/**.cpp ${CMAKE_SOURCE_DIR}/src/**.h)

find_package(Boost 1.60 COMPONENTS python filesystem system REQUIRED)
find_package(PythonInterp REQUIRED)
find_package(PythonLibs 3.5 REQUIRED)
find_package(SDL2 REQUIRED)

add_definitions("-DRAPIDJSON_ASSERT(x)")

include_directories(${Boost_INCLUDE_DIRS})
include_directories(${PYTHON_INCLUDE_DIRS})
include_directories(${SDL2_INCLUDE_DIR})

include_directories(${CMAKE_SOURCE_DIR}/src)

include_directories(${CMAKE_SOURCE_DIR}/../vstd)
include_directories(${CMAKE_SOURCE_DIR}/../rapidjson/include)

python_add_module(_game ${GAME_SRC})
target_link_libraries(_game ${Boost_LIBRARIES} ${PYTHON_LIBRARIES} ${SDL2_LIBRARY})

file(COPY res/config DESTINATION .)
file(COPY res/images DESTINATION .)
file(COPY res/maps DESTINATION .)
file(COPY res/plugins DESTINATION .)
file(COPY res/game DESTINATION .)
file(COPY run.py DESTINATION .)

cotire(_game)