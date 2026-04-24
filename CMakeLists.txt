#fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2025  Andrzej Lis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
cmake_minimum_required(VERSION 3.20)
if (POLICY CMP0087)
    cmake_policy(SET CMP0087 NEW)
endif ()

project(fall-of-nouraajd)

if (WIN32)
    set(CPACK_GENERATOR "ZIP")
    add_compile_definitions(SDL_MAIN_HANDLED)
else ()
    set(CPACK_GENERATOR "TGZ")
endif ()

include(${CMAKE_SOURCE_DIR}/cmake/cotire.cmake)

set(CMAKE_MODULE_PATH "${CMAKE_MODULE_PATH};${CMAKE_SOURCE_DIR}/cmake")

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if (MSVC)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} /W3 /bigobj /permissive- /Zc:preprocessor /EHsc /DBOOST_ALLOW_DEPRECATED_HEADERS /DBOOST_BIND_GLOBAL_PLACEHOLDERS /D_USE_MATH_DEFINES /DNOMINMAX /DWIN32_LEAN_AND_MEAN")
else ()
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -include cmath -Wall")
    set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -O3 -s")
    set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -g3")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -DBOOST_ALLOW_DEPRECATED_HEADERS -DBOOST_BIND_GLOBAL_PLACEHOLDERS")

    if (WIN32)
        set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -D_hypot=hypot -Wa,-mbig-obj")
        set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -O")
    endif ()
endif ()

file(GLOB_RECURSE GAME_SRC ${CMAKE_SOURCE_DIR}/src/**.cpp ${CMAKE_SOURCE_DIR}/src/**.h)

find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
find_package(pybind11 CONFIG QUIET)
if (NOT pybind11_FOUND)
    execute_process(
        COMMAND ${Python3_EXECUTABLE} -m pybind11 --cmakedir
        OUTPUT_VARIABLE pybind11_cmake_dir
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET
    )
    if (pybind11_cmake_dir)
        list(APPEND CMAKE_PREFIX_PATH ${pybind11_cmake_dir})
        find_package(pybind11 CONFIG REQUIRED)
    else ()
        message(FATAL_ERROR "pybind11 was not found. Install pybind11 or set pybind11_DIR.")
    endif ()
endif ()
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
find_path(NLOHMANN_JSON_INCLUDE_DIR nlohmann/json.hpp)
if (NOT NLOHMANN_JSON_INCLUDE_DIR)
    message(FATAL_ERROR "nlohmann/json.hpp was not found. On Debian/Ubuntu, run: sudo apt-get install nlohmann-json3-dev.")
endif ()

set(SDL2_LIBS ${SDL2_LIBRARY})
set(SDL2_EXECUTABLE_LIBS ${SDL2_LIBRARY})
if (TARGET SDL2::SDL2)
    set(SDL2_LIBS SDL2::SDL2)
    set(SDL2_EXECUTABLE_LIBS SDL2::SDL2)
endif ()

set(SDL2_IMAGE_LIBS ${SDL2_IMAGE_LIBRARY})
if (TARGET SDL2_image::SDL2_image)
    set(SDL2_IMAGE_LIBS SDL2_image::SDL2_image)
endif ()

set(SDL2_TTF_LIBS ${SDL2_TTF_LIBRARY})
if (TARGET SDL2_ttf::SDL2_ttf)
    set(SDL2_TTF_LIBS SDL2_ttf::SDL2_ttf)
endif ()

include_directories(${Python3_INCLUDE_DIRS})
include_directories(${SDL2_INCLUDE_DIR})
include_directories(${SDL2_IMAGE_INCLUDE_DIR})
include_directories(${SDL2_TTF_INCLUDE_DIR})
include_directories(${NLOHMANN_JSON_INCLUDE_DIR})

include_directories(${CMAKE_SOURCE_DIR}/src)

include_directories(${CMAKE_SOURCE_DIR}/vstd)
include_directories(${CMAKE_SOURCE_DIR}/random-dungeon-generator)

pybind11_add_module(_game NO_EXTRAS ${GAME_SRC})
target_link_libraries(_game PRIVATE ${SDL2_LIBS} ${SDL2_IMAGE_LIBS} ${SDL2_TTF_LIBS})

set_source_files_properties(
    ${CMAKE_SOURCE_DIR}/src/core/CModule.cpp
    ${CMAKE_SOURCE_DIR}/src/core/CTypes.cpp
    ${CMAKE_SOURCE_DIR}/src/object/CCreature.cpp
    ${CMAKE_SOURCE_DIR}/src/core/CSerialization.cpp
    ${CMAKE_SOURCE_DIR}/src/core/CMap.cpp
    ${CMAKE_SOURCE_DIR}/src/core/CLoader.cpp
    ${CMAKE_SOURCE_DIR}/src/core/CController.cpp
    PROPERTIES SKIP_UNITY_BUILD_INCLUSION ON
)

configure_file(res/config/armors.json config/armors.json)
configure_file(res/config/panels.json config/panels.json)
configure_file(res/config/buildings.json config/buildings.json)
configure_file(res/config/crafting.json config/crafting.json)
configure_file(res/config/effects.json config/effects.json)
configure_file(res/config/interactions.json config/interactions.json)
configure_file(res/config/items.json config/items.json)
configure_file(res/config/misc.json config/misc.json)
configure_file(res/config/monsters.json config/monsters.json)
configure_file(res/config/potions.json config/potions.json)
configure_file(res/config/slots.json config/slots.json)
configure_file(res/config/tiles.json config/tiles.json)
configure_file(res/config/weapons.json config/weapons.json)
configure_file(res/config/graphics.json config/graphics.json)

configure_file(res/maps/nouraajd/config.json maps/nouraajd/config.json)
configure_file(res/maps/nouraajd/dialog.json maps/nouraajd/dialog.json)
configure_file(res/maps/nouraajd/dialog2.json maps/nouraajd/dialog2.json)
configure_file(res/maps/nouraajd/dialog3.json maps/nouraajd/dialog3.json)
configure_file(res/maps/nouraajd/dialog4.json maps/nouraajd/dialog4.json)
configure_file(res/maps/nouraajd/dialog5.json maps/nouraajd/dialog5.json)
configure_file(res/maps/nouraajd/map.json maps/nouraajd/map.json)
configure_file(res/maps/nouraajd/script.py maps/nouraajd/script.py)

configure_file(res/maps/siege/config.json maps/siege/config.json)
configure_file(res/maps/siege/map.json maps/siege/map.json)
configure_file(res/maps/siege/script.py maps/siege/script.py)

configure_file(res/maps/ritual/config.json maps/ritual/config.json)
configure_file(res/maps/ritual/map.json maps/ritual/map.json)
configure_file(res/maps/ritual/script.py maps/ritual/script.py)

configure_file(res/maps/test/config.json maps/test/config.json)
configure_file(res/maps/test/map.json maps/test/map.json)
configure_file(res/maps/test/script.py maps/test/script.py)

configure_file(res/plugins/effect.py plugins/effect.py)
configure_file(res/plugins/interaction.py plugins/interaction.py)
configure_file(res/plugins/object.py plugins/object.py)
configure_file(res/plugins/crafting.py plugins/crafting.py)
configure_file(res/plugins/potion.py plugins/potion.py)
configure_file(res/plugins/tile.py plugins/tile.py)

configure_file(res/images/interactions/backstab.png images/interactions/backstab.png COPYONLY)
configure_file(res/images/interactions/deathstrike.png images/interactions/deathstrike.png COPYONLY)
configure_file(res/images/interactions/endlesspain.png images/interactions/endlesspain.png COPYONLY)
configure_file(res/images/interactions/chloroform.png images/interactions/chloroform.png COPYONLY)
configure_file(res/images/interactions/shadowbolt.png images/interactions/shadowbolt.png COPYONLY)
configure_file(res/images/interactions/strike.png images/interactions/strike.png COPYONLY)
configure_file(res/images/interactions/doubleattack.png images/interactions/doubleattack.png COPYONLY)
configure_file(res/images/interactions/attack.png images/interactions/attack.png COPYONLY)
configure_file(res/images/interactions/bloodthirst.png images/interactions/bloodthirst.png COPYONLY)
configure_file(res/images/interactions/armorofendlesswinter.png images/interactions/armorofendlesswinter.png COPYONLY)
configure_file(res/images/interactions/chaosblast.png images/interactions/chaosblast.png COPYONLY)
configure_file(res/images/interactions/sneakattack.png images/interactions/sneakattack.png COPYONLY)
configure_file(res/images/interactions/barrier.png images/interactions/barrier.png COPYONLY)
configure_file(res/images/interactions/bloodlash.png images/interactions/bloodlash.png COPYONLY)
configure_file(res/images/interactions/mutilation.png images/interactions/mutilation.png COPYONLY)
configure_file(res/images/interactions/lethalpoison.png images/interactions/lethalpoison.png COPYONLY)
configure_file(res/images/interactions/devour.png images/interactions/devour.png COPYONLY)
configure_file(res/images/interactions/frostbolt.png images/interactions/frostbolt.png COPYONLY)
configure_file(res/images/interactions/magicmissile.png images/interactions/magicmissile.png COPYONLY)
configure_file(res/images/interactions/stun.png images/interactions/stun.png COPYONLY)
configure_file(res/images/interactions/abyssalshadows.png images/interactions/abyssalshadows.png COPYONLY)

configure_file(res/images/panel.png images/panel.png COPYONLY)
configure_file(res/images/paper.png images/paper.png COPYONLY)
configure_file(res/images/arrows/left.png images/arrows/left.png COPYONLY)
configure_file(res/images/arrows/right.png images/arrows/right.png COPYONLY)
configure_file(res/images/item.png images/item.png COPYONLY)
configure_file(res/images/tooltip.png images/tooltip.png COPYONLY)
configure_file(res/images/button_on.png images/button_on.png COPYONLY)
configure_file(res/images/button_off.png images/button_off.png COPYONLY)
configure_file(res/images/footprint.png images/footprint.png COPYONLY)

configure_file(res/images/monsters/pritzmage/time.json images/monsters/pritzmage/time.json COPYONLY)
configure_file(res/images/monsters/pritzmage/2.png images/monsters/pritzmage/2.png COPYONLY)
configure_file(res/images/monsters/pritzmage/0.png images/monsters/pritzmage/0.png COPYONLY)
configure_file(res/images/monsters/pritzmage/3.png images/monsters/pritzmage/3.png COPYONLY)
configure_file(res/images/monsters/pritzmage/1.png images/monsters/pritzmage/1.png COPYONLY)
configure_file(res/images/monsters/gooby.png images/monsters/gooby.png COPYONLY)
configure_file(res/images/monsters/cult_leader.png images/monsters/cult_leader.png COPYONLY)
configure_file(res/images/monsters/cultist.png images/monsters/cultist.png COPYONLY)
configure_file(res/images/monsters/goblin_thief.png images/monsters/goblin_thief.png COPYONLY)

configure_file(res/images/monsters/octobogz/time.json images/monsters/octobogz/time.json COPYONLY)
configure_file(res/images/monsters/octobogz/0.png images/monsters/octobogz/0.png COPYONLY)
configure_file(res/images/monsters/octobogz/1.png images/monsters/octobogz/1.png COPYONLY)

configure_file(res/images/monsters/pritz/time.json images/monsters/pritz/time.json COPYONLY)
configure_file(res/images/monsters/pritz/0.png images/monsters/pritz/0.png COPYONLY)
configure_file(res/images/monsters/pritz/1.png images/monsters/pritz/1.png COPYONLY)


configure_file(res/images/items/boots/eradicatorsboots.png images/items/boots/eradicatorsboots.png COPYONLY)

configure_file(res/images/items/potions/bless.png images/items/potions/bless.png COPYONLY)
configure_file(res/images/items/potions/poison.png images/items/potions/poison.png COPYONLY)
configure_file(res/images/items/potions/dark_beer.png images/items/potions/dark_beer.png COPYONLY)
configure_file(res/images/items/potions/life.png images/items/potions/life.png COPYONLY)
configure_file(res/images/items/potions/mana.png images/items/potions/mana.png COPYONLY)
configure_file(res/images/items/potions/spiced_beer.png images/items/potions/spiced_beer.png COPYONLY)
configure_file(res/images/items/scroll.png images/items/scroll.png COPYONLY)

configure_file(res/images/items/armors/leatherarmor.png images/items/armors/leatherarmor.png COPYONLY)
configure_file(res/images/items/armors/robe.png images/items/armors/robe.png COPYONLY)
configure_file(res/images/items/armors/platearmor.png images/items/armors/platearmor.png COPYONLY)
configure_file(res/images/items/armors/chestplateofnorth.png images/items/armors/chestplateofnorth.png COPYONLY)

configure_file(res/images/items/gloves/glovesoftheassasin.png images/items/gloves/glovesoftheassasin.png COPYONLY)

configure_file(res/images/items/weapons/longsword.png images/items/weapons/longsword.png COPYONLY)
configure_file(res/images/items/weapons/chaossword.png images/items/weapons/chaossword.png COPYONLY)
configure_file(res/images/items/weapons/broadsword.png images/items/weapons/broadsword.png COPYONLY)
configure_file(res/images/items/weapons/staffoftheabyss.png images/items/weapons/staffoftheabyss.png COPYONLY)
configure_file(res/images/items/weapons/void.png images/items/weapons/void.png COPYONLY)
configure_file(res/images/items/weapons/bladeofdarkdreams.png images/items/weapons/bladeofdarkdreams.png COPYONLY)
configure_file(res/images/items/weapons/knife.png images/items/weapons/knife.png COPYONLY)
configure_file(res/images/items/weapons/shortsword.png images/items/weapons/shortsword.png COPYONLY)
configure_file(res/images/items/weapons/stiletto.png images/items/weapons/stiletto.png COPYONLY)
configure_file(res/images/items/weapons/shadowblade.png images/items/weapons/shadowblade.png COPYONLY)
configure_file(res/images/items/weapons/staff.png images/items/weapons/staff.png COPYONLY)
configure_file(res/images/items/weapons/daggerofvileheart.png images/items/weapons/daggerofvileheart.png COPYONLY)
configure_file(res/images/items/weapons/sword.png images/items/weapons/sword.png COPYONLY)
configure_file(res/images/items/weapons/valkyrie.png images/items/weapons/valkyrie.png COPYONLY)
configure_file(res/images/items/weapons/shortstaff.png images/items/weapons/shortstaff.png COPYONLY)
configure_file(res/images/items/weapons/wand.png images/items/weapons/wand.png COPYONLY)
configure_file(res/images/items/weapons/dagger.png images/items/weapons/dagger.png COPYONLY)

configure_file(res/images/items/helmets/crownofnightmares.png images/items/helmets/crownofnightmares.png COPYONLY)

configure_file(res/images/items/belts/undestructiblebelt.png images/items/belts/undestructiblebelt.png COPYONLY)

configure_file(res/images/buildings/cave.png images/buildings/cave.png COPYONLY)
configure_file(res/images/buildings/chapel.png images/buildings/chapel.png COPYONLY)
configure_file(res/images/buildings/market.png images/buildings/market.png COPYONLY)
configure_file(res/images/buildings/teleporter.png images/buildings/teleporter.png COPYONLY)
configure_file(res/images/buildings/dungeon.png images/buildings/dungeon.png COPYONLY)
configure_file(res/images/buildings/groundhole.png images/buildings/groundhole.png COPYONLY)
configure_file(res/images/buildings/tavern.png images/buildings/tavern.png COPYONLY)
configure_file(res/images/buildings/town_hall.png images/buildings/town_hall.png COPYONLY)

configure_file(res/images/terrain.png images/terrain.png COPYONLY)

configure_file(res/images/players/assasin.png images/players/assasin.png COPYONLY)
configure_file(res/images/players/inquisitor.png images/players/inquisitor.png COPYONLY)
configure_file(res/images/players/sorcerer.png images/players/sorcerer.png COPYONLY)
configure_file(res/images/players/wayfarer.png images/players/wayfarer.png COPYONLY)
configure_file(res/images/players/warrior.png images/players/warrior.png COPYONLY)
configure_file(res/images/npc/oldWoman.png images/npc/oldWoman.png COPYONLY)
configure_file(res/images/npc/questGiver.png images/npc/questGiver.png COPYONLY)

configure_file(res/images/tiles/lava.png images/tiles/lava.png COPYONLY)
configure_file(res/images/tiles/beach.png images/tiles/beach.png COPYONLY)
configure_file(res/images/tiles/wasteland.png images/tiles/wasteland.png COPYONLY)
configure_file(res/images/tiles/mountain.png images/tiles/mountain.png COPYONLY)
configure_file(res/images/tiles/swamp.png images/tiles/swamp.png COPYONLY)
configure_file(res/images/tiles/water.png images/tiles/water.png COPYONLY)
configure_file(res/images/tiles/road.png images/tiles/road.png COPYONLY)
configure_file(res/images/tiles/snow.png images/tiles/snow.png COPYONLY)
configure_file(res/images/tiles/ground.png images/tiles/ground.png COPYONLY)
configure_file(res/images/tiles/grass.png images/tiles/grass.png COPYONLY)
configure_file(res/images/tiles/desert.png images/tiles/desert.png COPYONLY)

configure_file(res/images/skull.png images/skull.png COPYONLY)

configure_file(res/images/misc/open_door.png images/misc/open_door.png COPYONLY)
configure_file(res/images/misc/closed_door.png images/misc/closed_door.png COPYONLY)

configure_file(res/images/misc/signpost.png images/misc/signpost.png COPYONLY)
configure_file(res/images/misc/wall.png images/misc/wall.png COPYONLY)
configure_file(res/images/misc/chest.png images/misc/chest.png COPYONLY)

configure_file(res/fonts/ampersand.ttf fonts/ampersand.ttf COPYONLY)

configure_file(res/game.py game.py)

configure_file(test.py test.py)
configure_file(play.py play.py)
configure_file(mcp.py mcp.py)

install(TARGETS _game DESTINATION fall-of-nouraajd)
install(DIRECTORY res/config DESTINATION fall-of-nouraajd)
install(DIRECTORY res/fonts DESTINATION fall-of-nouraajd)
install(DIRECTORY res/images DESTINATION fall-of-nouraajd)
install(DIRECTORY res/maps DESTINATION fall-of-nouraajd)
install(DIRECTORY res/plugins DESTINATION fall-of-nouraajd)

install(FILES res/game.py play.py mcp.py test.py DESTINATION fall-of-nouraajd)

if (WIN32)
    install(FILES play.bat DESTINATION fall-of-nouraajd)

    set(WINDOWS_RUNTIME_DEPENDENCY_CODE "")
    if (DEFINED _VCPKG_INSTALLED_DIR AND DEFINED VCPKG_TARGET_TRIPLET)
        foreach (runtime_dir
                 "${_VCPKG_INSTALLED_DIR}/${VCPKG_TARGET_TRIPLET}/bin"
                 "${_VCPKG_INSTALLED_DIR}/${VCPKG_TARGET_TRIPLET}/debug/bin")
            if (EXISTS "${runtime_dir}")
                string(APPEND WINDOWS_RUNTIME_DEPENDENCY_CODE
                       "list(APPEND runtime_search_dirs [[${runtime_dir}]])\n")
            endif ()
        endforeach ()
    endif ()

    install(CODE "
        if (CMAKE_VERSION VERSION_LESS 3.16)
            message(WARNING \"CMake 3.16 or newer is required to bundle Windows runtime DLLs automatically.\")
        else ()
            set(runtime_search_dirs \"\$ENV{PATH}\")
            ${WINDOWS_RUNTIME_DEPENDENCY_CODE}
            file(GET_RUNTIME_DEPENDENCIES
                RESOLVED_DEPENDENCIES_VAR runtime_deps
                UNRESOLVED_DEPENDENCIES_VAR unresolved_runtime_deps
                MODULES \"$<TARGET_FILE:_game>\"
                DIRECTORIES \${runtime_search_dirs}
                PRE_EXCLUDE_REGEXES
                    \"api-ms-.*\"
                    \"ext-ms-.*\"
                POST_EXCLUDE_REGEXES
                    \".*[Ww][Ii][Nn][Dd][Oo][Ww][Ss][\\/][Ss]ystem32.*\"
            )
            foreach (runtime_dep IN LISTS runtime_deps)
                file(INSTALL
                    DESTINATION \"\${CMAKE_INSTALL_PREFIX}/fall-of-nouraajd\"
                    TYPE SHARED_LIBRARY
                    FILES \"\${runtime_dep}\"
                )
            endforeach ()
            if (unresolved_runtime_deps)
                message(WARNING \"Unresolved Windows runtime dependencies: \${unresolved_runtime_deps}\")
            endif ()
        endif ()
    ")
endif ()


add_executable(for_unit_tests
    tests/unit/test_coords.cpp
    src/core/CTags.cpp
    src/core/CUtil.cpp
    src/core/CPathFinder.cpp
    src/core/CFuture.cpp
    src/handler/CScriptHandler.cpp
)

target_include_directories(for_unit_tests PRIVATE
    ${CMAKE_SOURCE_DIR}/src
    ${CMAKE_SOURCE_DIR}/vstd
    ${NLOHMANN_JSON_INCLUDE_DIR}
    ${Python3_INCLUDE_DIRS}
    ${SDL2_INCLUDE_DIR}
    ${SDL2_IMAGE_INCLUDE_DIR}
    ${SDL2_TTF_INCLUDE_DIR}
)

target_link_libraries(for_unit_tests PRIVATE
    Python3::Python
    pybind11::headers
    ${SDL2_EXECUTABLE_LIBS}
    ${SDL2_IMAGE_LIBS}
    ${SDL2_TTF_LIBS}
)

enable_testing()
add_test(NAME for_unit_tests COMMAND for_unit_tests)
if (WIN32)
    get_filename_component(TEST_PYTHONHOME "${Python3_EXECUTABLE}" DIRECTORY)
    if (DEFINED _VCPKG_INSTALLED_DIR AND DEFINED VCPKG_TARGET_TRIPLET)
        set(TEST_RUNTIME_PATH "${_VCPKG_INSTALLED_DIR}/${VCPKG_TARGET_TRIPLET}/bin")
    endif ()
    if (CMAKE_VERSION VERSION_GREATER_EQUAL 3.22)
        if (TEST_RUNTIME_PATH)
            set_tests_properties(for_unit_tests PROPERTIES
                ENVIRONMENT "PYTHONHOME=${TEST_PYTHONHOME}"
                ENVIRONMENT_MODIFICATION "PATH=path_list_prepend:${TEST_RUNTIME_PATH}"
            )
        else ()
            set_tests_properties(for_unit_tests PROPERTIES
                ENVIRONMENT "PYTHONHOME=${TEST_PYTHONHOME}"
            )
        endif ()
    else ()
        if (TEST_RUNTIME_PATH)
            set_tests_properties(for_unit_tests PROPERTIES
                ENVIRONMENT "PYTHONHOME=${TEST_PYTHONHOME};PATH=${TEST_RUNTIME_PATH}"
            )
        else ()
            set_tests_properties(for_unit_tests PROPERTIES
                ENVIRONMENT "PYTHONHOME=${TEST_PYTHONHOME}"
            )
        endif ()
    endif ()
endif ()

if (WIN32)
    set(CPACK_STRIP_FILES _game.pyd)
else ()
    set(CPACK_STRIP_FILES _game.so)
endif ()

if (WIN32)
    set_target_properties(_game PROPERTIES UNITY_BUILD OFF)
else()
    set_target_properties(_game PROPERTIES UNITY_BUILD ON UNITY_BUILD_BATCH_SIZE 8)
endif ()

include(CPack)
