#fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2019  Andrzej Lis
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
cmake_minimum_required(VERSION 3.3)

project(fall-of-nouraajd)

include(CPack)
set(CPACK_GENERATOR "TGZ")

include(${CMAKE_SOURCE_DIR}/cmake/cotire.cmake)

set(CMAKE_MODULE_PATH "${CMAKE_MODULE_PATH};${CMAKE_SOURCE_DIR}/cmake")

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++2a -include cmath -Wall -fconcepts")

set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -O3 -s")
set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -g3")

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -DBOOST_ALLOW_DEPRECATED_HEADERS -DBOOST_BIND_GLOBAL_PLACEHOLDERS")

if (WIN32)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -D_hypot=hypot -Wa,-mbig-obj")
    set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -O")
endif ()

file(GLOB_RECURSE GAME_SRC ${CMAKE_SOURCE_DIR}/src/**.cpp ${CMAKE_SOURCE_DIR}/src/**.h)

find_package(Boost COMPONENTS python filesystem REQUIRED)
find_package(PythonInterp REQUIRED)
find_package(PythonLibs REQUIRED)
find_package(SDL2 REQUIRED)
find_package(SDL2_image REQUIRED)
find_package(SDL2_ttf REQUIRED)

include_directories(${Boost_INCLUDE_DIRS})
include_directories(${PYTHON_INCLUDE_DIRS})
include_directories(${SDL2_INCLUDE_DIR})
include_directories(${SDL2_IMAGE_INCLUDE_DIR})
include_directories(${SDL2_TTF_INCLUDE_DIR})
include_directories(json/single_include/nlohmann)

include_directories(${CMAKE_SOURCE_DIR}/src)

include_directories(${CMAKE_SOURCE_DIR}/vstd)
include_directories(${CMAKE_SOURCE_DIR}/random-dungeon-generator)

python_add_module(_game ${GAME_SRC})
target_link_libraries(_game ${Boost_LIBRARIES} ${PYTHON_LIBRARIES} ${SDL2_LIBRARY} ${SDL2_IMAGE_LIBRARY} ${SDL2_TTF_LIBRARY})

configure_file(res/config/armors.json config/armors.json)
configure_file(res/config/panels.json config/panels.json)
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

configure_file(res/maps/test/config.json maps/test/config.json)
configure_file(res/maps/test/map.json maps/test/map.json)
configure_file(res/maps/test/script.py maps/test/script.py)

configure_file(res/plugins/effect.py plugins/effect.py)
configure_file(res/plugins/interaction.py plugins/interaction.py)
configure_file(res/plugins/object.py plugins/object.py)
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

configure_file(res/images/monsters/octobogz/time.json images/monsters/octobogz/time.json COPYONLY)
configure_file(res/images/monsters/octobogz/0.png images/monsters/octobogz/0.png COPYONLY)
configure_file(res/images/monsters/octobogz/1.png images/monsters/octobogz/1.png COPYONLY)

configure_file(res/images/monsters/pritz/time.json images/monsters/pritz/time.json COPYONLY)
configure_file(res/images/monsters/pritz/0.png images/monsters/pritz/0.png COPYONLY)
configure_file(res/images/monsters/pritz/1.png images/monsters/pritz/1.png COPYONLY)


configure_file(res/images/items/boots/eradicatorsboots.png images/items/boots/eradicatorsboots.png COPYONLY)

configure_file(res/images/items/potions/bless.png images/items/potions/bless.png COPYONLY)
configure_file(res/images/items/potions/poison.png images/items/potions/poison.png COPYONLY)
configure_file(res/images/items/potions/life.png images/items/potions/life.png COPYONLY)
configure_file(res/images/items/potions/mana.png images/items/potions/mana.png COPYONLY)
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
configure_file(res/images/players/sorcerer.png images/players/sorcerer.png COPYONLY)
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

install(TARGETS _game DESTINATION fall-of-nouraajd)
install(DIRECTORY res/config DESTINATION fall-of-nouraajd)
install(DIRECTORY res/fonts DESTINATION fall-of-nouraajd)
install(DIRECTORY res/images DESTINATION fall-of-nouraajd)
install(DIRECTORY res/maps DESTINATION fall-of-nouraajd)
install(DIRECTORY res/plugins DESTINATION fall-of-nouraajd)

install(FILES res/game.py test.py DESTINATION fall-of-nouraajd)

install(FILES play.py play.py DESTINATION fall-of-nouraajd)
install(FILES test.py test.py DESTINATION fall-of-nouraajd)

if (WIN32)
    install(FILES play.bat play.bat DESTINATION fall-of-nouraajd)

    install(FILES windows-tools/SDL2_image-2.0.5/x86_64-w64-mingw32/bin/libjpeg-9.dll DESTINATION fall-of-nouraajd)
    install(FILES windows-tools/SDL2_image-2.0.5/x86_64-w64-mingw32/bin/libpng16-16.dll DESTINATION fall-of-nouraajd)
    install(FILES windows-tools/SDL2_image-2.0.5/x86_64-w64-mingw32/bin/libtiff-5.dll DESTINATION fall-of-nouraajd)
    install(FILES windows-tools/SDL2_image-2.0.5/x86_64-w64-mingw32/bin/libwebp-7.dll DESTINATION fall-of-nouraajd)
    install(FILES windows-tools/SDL2_image-2.0.5/x86_64-w64-mingw32/bin/SDL2_image.dll DESTINATION fall-of-nouraajd)
    install(FILES windows-tools/SDL2_image-2.0.5/x86_64-w64-mingw32/bin/zlib1.dll DESTINATION fall-of-nouraajd)

    install(FILES windows-tools/SDL2_ttf-2.0.15/x86_64-w64-mingw32/bin/libfreetype-6.dll DESTINATION fall-of-nouraajd)
    install(FILES windows-tools/SDL2_ttf-2.0.15/x86_64-w64-mingw32/bin/SDL2_ttf.dll DESTINATION fall-of-nouraajd)

    install(FILES windows-tools/SDL2-2.0.12/x86_64-w64-mingw32/bin/SDL2.dll DESTINATION fall-of-nouraajd)

    install(FILES windows-tools/boost64/lib/libboost_python36-mgw8-mt-x64-1_74.dll DESTINATION fall-of-nouraajd)
    install(FILES windows-tools/boost64/lib/libboost_filesystem-mgw8-mt-x64-1_74.dll DESTINATION fall-of-nouraajd)

    install(FILES windows-tools/Python36/python.exe DESTINATION fall-of-nouraajd)
    install(FILES windows-tools/Python36/python36.dll DESTINATION fall-of-nouraajd)
    install(FILES windows-tools/Python36/vcruntime140.dll DESTINATION fall-of-nouraajd)

    install(FILES windows-tools/mingw/mingw64/bin/libgcc_s_seh-1.dll DESTINATION fall-of-nouraajd)
    install(FILES windows-tools/mingw/mingw64/bin/libstdc++-6.dll DESTINATION fall-of-nouraajd)
    install(FILES windows-tools/mingw/mingw64/bin/libwinpthread-1.dll DESTINATION fall-of-nouraajd)

    install(FILES windows-tools/Python36/python36.zip DESTINATION fall-of-nouraajd)
endif ()

SET(CPACK_STRIP_FILES _game.so)

IF (!WIN32)
    cotire(_game)
ENDIF ()

set_target_properties(_game PROPERTIES UNITY_BUILD ON)