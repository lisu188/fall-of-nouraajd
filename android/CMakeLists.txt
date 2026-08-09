cmake_minimum_required(VERSION 3.20)

project(fall_of_nouraajd_android LANGUAGES C CXX)

if (NOT ANDROID)
    message(FATAL_ERROR "android/CMakeLists.txt is only for Android NDK builds")
endif ()

get_filename_component(GAME_REPOSITORY_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
set(CMAKE_MODULE_PATH "${CMAKE_MODULE_PATH};${GAME_REPOSITORY_ROOT}/cmake")

set(GAME_ANDROID_PYTHON_INCLUDE_DIR "" CACHE PATH "Android CPython include directory")
set(GAME_ANDROID_PYTHON_LIBRARY "" CACHE FILEPATH "Android libpython shared library")
if (NOT IS_DIRECTORY "${GAME_ANDROID_PYTHON_INCLUDE_DIR}")
    message(FATAL_ERROR "GAME_ANDROID_PYTHON_INCLUDE_DIR must point to prefix/include/python3.*")
endif ()
if (NOT EXISTS "${GAME_ANDROID_PYTHON_LIBRARY}")
    message(FATAL_ERROR "GAME_ANDROID_PYTHON_LIBRARY must point to libpython3.*.so")
endif ()

set(PYBIND11_NOPYTHON ON)
find_package(pybind11 CONFIG REQUIRED)
find_package(SDL2 CONFIG QUIET)
if (NOT SDL2_FOUND AND NOT TARGET SDL2::SDL2)
    find_package(SDL2 REQUIRED)
endif ()
find_package(SDL2_image CONFIG QUIET)
if (NOT SDL2_image_FOUND AND NOT TARGET SDL2_image::SDL2_image)
    find_package(SDL2_image REQUIRED)
endif ()
find_package(SDL2_ttf CONFIG QUIET)
if (NOT SDL2_ttf_FOUND AND NOT TARGET SDL2_ttf::SDL2_ttf)
    find_package(SDL2_ttf REQUIRED)
endif ()

add_library(game_android_python SHARED IMPORTED GLOBAL)
set_target_properties(game_android_python PROPERTIES
    IMPORTED_LOCATION "${GAME_ANDROID_PYTHON_LIBRARY}"
    INTERFACE_INCLUDE_DIRECTORIES "${GAME_ANDROID_PYTHON_INCLUDE_DIR}"
)

add_library(simdjson_android STATIC
    "${GAME_REPOSITORY_ROOT}/third_party/simdjson/simdjson.cpp"
)
target_compile_features(simdjson_android PUBLIC cxx_std_23)
target_include_directories(simdjson_android SYSTEM PUBLIC
    "${GAME_REPOSITORY_ROOT}/third_party/simdjson"
)
set_target_properties(simdjson_android PROPERTIES POSITION_INDEPENDENT_CODE ON)

file(GLOB LUA_ANDROID_SRC "${GAME_REPOSITORY_ROOT}/third_party/lua/*.c")
list(FILTER LUA_ANDROID_SRC EXCLUDE REGEX ".*/(lua|luac)\\.c$")
add_library(lua_android STATIC ${LUA_ANDROID_SRC})
target_include_directories(lua_android SYSTEM PUBLIC "${GAME_REPOSITORY_ROOT}/third_party/lua")
target_compile_definitions(lua_android PRIVATE LUA_USE_POSIX)
set_target_properties(lua_android PROPERTIES POSITION_INDEPENDENT_CODE ON)

file(GLOB_RECURSE GAME_ANDROID_SRC CONFIGURE_DEPENDS
    "${GAME_REPOSITORY_ROOT}/src/*.cpp"
    "${GAME_REPOSITORY_ROOT}/src/*.h"
)
list(FILTER GAME_ANDROID_SRC EXCLUDE REGEX ".*/src/core/CModuleEntry\\.cpp$")

set(SDL2_ANDROID_LIBS ${SDL2_LIBRARY})
if (TARGET SDL2::SDL2)
    set(SDL2_ANDROID_LIBS SDL2::SDL2)
endif ()

set(SDL2_IMAGE_ANDROID_LIBS ${SDL2_IMAGE_LIBRARY})
if (TARGET SDL2_image::SDL2_image)
    set(SDL2_IMAGE_ANDROID_LIBS SDL2_image::SDL2_image)
endif ()

set(SDL2_TTF_ANDROID_LIBS ${SDL2_TTF_LIBRARY})
if (TARGET SDL2_ttf::SDL2_ttf)
    set(SDL2_TTF_ANDROID_LIBS SDL2_ttf::SDL2_ttf)
endif ()

add_library(main SHARED ${GAME_ANDROID_SRC})
target_compile_features(main PRIVATE cxx_std_23)
set_target_properties(main PROPERTIES
    CXX_STANDARD_REQUIRED ON
    CXX_EXTENSIONS OFF
)
target_include_directories(main PRIVATE
    "${GAME_REPOSITORY_ROOT}/src"
    "${GAME_REPOSITORY_ROOT}/vstd"
    "${GAME_REPOSITORY_ROOT}/random-dungeon-generator"
    "${GAME_ANDROID_PYTHON_INCLUDE_DIR}"
    "${SDL2_INCLUDE_DIR}"
    "${SDL2_IMAGE_INCLUDE_DIR}"
    "${SDL2_TTF_INCLUDE_DIR}"
)
target_compile_definitions(main PRIVATE
    GAME_CORE_BUILD
    BOOST_ALLOW_DEPRECATED_HEADERS
    BOOST_BIND_GLOBAL_PLACEHOLDERS
)
target_compile_options(main PRIVATE
    -include cmath
    -Wall
    $<$<CONFIG:Release>:-O3>
    $<$<CONFIG:Debug>:-g3>
)
target_link_libraries(main PRIVATE
    game_android_python
    pybind11::headers
    ${SDL2_ANDROID_LIBS}
    ${SDL2_IMAGE_ANDROID_LIBS}
    ${SDL2_TTF_ANDROID_LIBS}
    simdjson_android
    lua_android
    ${CMAKE_DL_LIBS}
)
