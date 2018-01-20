cmake_minimum_required(VERSION 3.3)
project(fall_of_nouraajd)

include(${CMAKE_SOURCE_DIR}/cmake/cotire.cmake)

set(JSONCPP_INCLUDE_DIR /usr/include/jsoncpp)

set(CMAKE_MODULE_PATH "${CMAKE_MODULE_PATH};${CMAKE_SOURCE_DIR}/cmake")

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++17 -include cmath -Wall")

set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -O3")
set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -g3")

file(GLOB_RECURSE GAME_SRC ${CMAKE_SOURCE_DIR}/src/**.cpp ${CMAKE_SOURCE_DIR}/src/**.h)

find_package(Boost 1.60 COMPONENTS python3 filesystem system REQUIRED)
find_package(PythonInterp 3.5 REQUIRED)
find_package(PythonLibs 3.5 REQUIRED)
find_package(SDL2 REQUIRED)
find_package(SDL2_image REQUIRED)
find_package(SDL2_ttf REQUIRED)
find_package(JsonCpp REQUIRED)

include_directories(${Boost_INCLUDE_DIRS})
include_directories(${PYTHON_INCLUDE_DIRS})
include_directories(${SDL2_INCLUDE_DIR})
include_directories(${SDL2_IMAGE_INCLUDE_DIR})
include_directories(${SDL2_TTF_INCLUDE_DIR})
include_directories(${JSONCPP_INCLUDE_DIRS})

include_directories(${CMAKE_SOURCE_DIR}/src)

include_directories(${CMAKE_SOURCE_DIR}/vstd)

python_add_module(_game ${GAME_SRC})
target_link_libraries(_game ${Boost_LIBRARIES} ${PYTHON_LIBRARIES} ${SDL2_LIBRARY} ${SDL2_IMAGE_LIBRARY} ${SDL2_TTF_LIBRARY} ${JSONCPP_LIBRARIES})

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
configure_file(res/images/arrows/left.png images/arrows/left.png COPYONLY)
configure_file(res/images/arrows/right.png images/arrows/right.png COPYONLY)
configure_file(res/images/item.png images/item.png COPYONLY)

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
configure_file(res/images/buildings/market.png images/buildings/market.png COPYONLY)
configure_file(res/images/buildings/teleporter.png images/buildings/teleporter.png COPYONLY)
configure_file(res/images/buildings/dungeon.png images/buildings/dungeon.png COPYONLY)
configure_file(res/images/terrain.png images/terrain.png COPYONLY)

configure_file(res/images/players/assasin.png images/players/assasin.png COPYONLY)
configure_file(res/images/players/sorcerer.png images/players/sorcerer.png COPYONLY)
configure_file(res/images/players/warrior.png images/players/warrior.png COPYONLY)

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

configure_file(res/fonts/ampersand.ttf fonts/ampersand.ttf COPYONLY)

configure_file(res/game.py game.py)

configure_file(test.py test.py)

cotire(_game)