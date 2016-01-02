cmake_minimum_required(VERSION 3.3)
project(game)

include($ENV{COTIRE_CMAKE}/cotire.cmake)

set(BOOST_INCLUDEDIR $ENV{BOOST_INC})
set(BOOST_LIBRARYDIR $ENV{BOOST_LIB})
find_package(Boost 1.58)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -DBOOST_DISABLE_ASSERTS -std=c++14 -include cmath -Wno-deprecated-declarations -Wno-unused-local-typedefs -Wno-attributes")

file(GLOB_RECURSE GAME_SRC ${CMAKE_SOURCE_DIR}/src/**.cpp ${CMAKE_SOURCE_DIR}/src/**.h)

file(GLOB_RECURSE VSTD_SRC vstd/src/**.cpp vstd/src/**.h)
file(GLOB_RECURSE BOOST_PYTHON_SRC python/src/**.cpp python/src/**.h)

include_directories(${Boost_INCLUDE_DIRS})
include_directories(C:/Users/Andrzej/AppData/Local/Programs/Python/Python35/include) #TODO: ugh!

include_directories(${CMAKE_SOURCE_DIR}/src)

include_directories(vstd/src)
include_directories(python/src)

add_executable(game ${GAME_SRC} ${VSTD_SRC} ${BOOST_PYTHON_SRC})

#add_custom_command(TARGET game PRE_BUILD COMMAND format.py WORKING_DIRECTORY ${CMAKE_SOURCE_DIR})

target_link_libraries(game $ENV{PYTHON_LIB}/libpython35.a)

cotire(game)