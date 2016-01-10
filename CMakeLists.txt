cmake_minimum_required(VERSION 3.3)
project(game)

include($ENV{COTIRE_CMAKE}/cotire.cmake)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++14 -include cmath -Wno-deprecated-declarations -Wno-unused-local-typedefs -Wno-attributes")

file(GLOB_RECURSE GAME_SRC ${CMAKE_SOURCE_DIR}/src/**.cpp ${CMAKE_SOURCE_DIR}/src/**.h)

file(GLOB_RECURSE BOOST_PYTHON_SRC $ENV{BOOST}/libs/python/src/**.cpp)
file(GLOB_RECURSE BOOST_FILESYSTEM_SRC $ENV{BOOST}/libs/filesystem/src/**.cpp)

set(BOOST_INCLUDEDIR $ENV{BOOST})
set(BOOST_LIBRARYDIR $ENV{BOOST}/stage/lib)
FIND_PACKAGE(Boost 1.60)

add_definitions("-DRAPIDJSON_ASSERT(x)")
add_definitions(-DBOOST_DISABLE_ASSERTS)
add_definitions("-DBOOST_PYTHON_SOURCE")

include_directories(${Boost_INCLUDE_DIRS})
include_directories($ENV{PYTHON}/include)

include_directories(${CMAKE_SOURCE_DIR}/src)

include_directories(${CMAKE_SOURCE_DIR}/../vstd)
include_directories(${CMAKE_SOURCE_DIR}/../rapidjson/include)

add_executable(game ${GAME_SRC} ${BOOST_PYTHON_SRC} ${BOOST_FILESYSTEM_SRC})

target_link_libraries(game $ENV{PYTHON}/libs/libpython35.a)

set_target_properties(game PROPERTIES COTIRE_PREFIX_HEADER_IGNORE_PATH ${CMAKE_SOURCE_DIR}\;$ENV{BOOST}/boost/preprocessor/iteration/detail/local.hpp\;$ENV{BOOST}/boost/detail/utf8_codecvt_facet.hpp) #this file was causing errors

cotire(game)