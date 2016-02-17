cmake_minimum_required(VERSION 3.3)
project(game)

include(${CMAKE_SOURCE_DIR}/cmake/cotire.cmake)
set(CMAKE_MODULE_PATH "${CMAKE_MODULE_PATH};${CMAKE_SOURCE_DIR}/cmake")

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++14 -include cmath -Wno-deprecated-declarations -Wno-unused-local-typedefs -Wno-attributes -Wno-inline")

set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -O3")
set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -g3")

file(GLOB_RECURSE GAME_SRC ${CMAKE_SOURCE_DIR}/src/**.cpp ${CMAKE_SOURCE_DIR}/src/**.h)

find_package(Boost 1.58 COMPONENTS python3 filesystem system REQUIRED)
find_package(PythonInterp 3.4 REQUIRED)
find_package(PythonLibs 3.4 REQUIRED)
find_package(SDL2 REQUIRED)
find_package(JsonCpp REQUIRED)

include_directories(${Boost_INCLUDE_DIRS})
include_directories(${PYTHON_INCLUDE_DIRS})
include_directories(${SDL2_INCLUDE_DIR})
include_directories(${JSONCPP_INCLUDE_DIRS})

include_directories(${CMAKE_SOURCE_DIR}/src)

include_directories(${CMAKE_SOURCE_DIR}/../vstd)

python_add_module(_game ${GAME_SRC})
target_link_libraries(_game ${Boost_LIBRARIES} ${PYTHON_LIBRARIES} ${SDL2_LIBRARY} ${JSONCPP_LIBRARIES})

file(COPY res/config DESTINATION .)
file(COPY res/images DESTINATION .)
file(COPY res/maps DESTINATION .)
file(COPY res/plugins DESTINATION .)

configure_file(res/game.py game.py)
configure_file(run.py run.py)

cotire(_game)