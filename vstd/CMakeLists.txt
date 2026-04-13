# MIT License
#
# Copyright (c) 2025 Andrzej Lis
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

cmake_minimum_required(VERSION 3.3)
project(vstd)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++14")

FIND_PACKAGE(Boost 1.58 COMPONENTS system REQUIRED)

include_directories(${Boost_INCLUDE_DIRS})

set(SOURCE_FILES
        vadaptors.h
        vcast.h
        vchain.h
        vconverter.h
        vdefines.h
        vfunctional.h
        vfuture.h
        vhash.h
        vhex.h
        vlazy.h
        vlogger.h
        vthread.h
        vthreadpool.h
        vtraits.h
        vutil.h
        vassert.h
        vstd.h
        vstring.h
        vmeta.h
        vneuro.h
        vany.h
        vtuple.h)

if (CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    add_executable(vstd ${SOURCE_FILES} main.cpp)
    target_link_libraries(vstd ${Boost_LIBRARIES})
else ()
    add_custom_target(vstd SOURCES ${SOURCE_FILES})
endif ()
