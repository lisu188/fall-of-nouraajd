/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
#include "CModuleBindings.h"
#include "core/CRuntimeBridge.h"
#include "CModuleCallbacks.h"
#include "core/CAsync.h"
#include "core/CLoader.h"
#include "core/CSlotConfig.h"
#include "core/CWrapper.h"
#include "gui/CGui.h"
#include <pybind11/stl_bind.h>

namespace py = pybind11;

namespace nouraajd::bindings {
void bindServices(py::module_ &m, const std::shared_ptr<CPythonEventCallbacks> &pythonEventCallbacks) {
    py::class_<CEventHandler, CGameObject, std::shared_ptr<CEventHandler>>(m, "CEventHandler",
                                                                           "Dispatcher for game/map events.")
        .def("registerTrigger", &CEventHandler::registerTrigger, "Register a trigger for an event type.");

    py::enum_<CFightOutcome>(m, "CFightOutcome")
        .value("invalid", CFightOutcome::invalid)
        .value("attackerVictory", CFightOutcome::attackerVictory)
        .value("attackerDefeat", CFightOutcome::attackerDefeat)
        .value("stalemate", CFightOutcome::stalemate)
        .value("interrupted", CFightOutcome::interrupted);

    py::class_<CFightHandler, std::shared_ptr<CFightHandler>>(m, "CFightHandler", "Combat resolution service.")
        .def("fight", &CFightHandler::fight, "Run a fight between two creatures.")
        .def_static("applyEffects", &CFightHandler::applyEffects, "Apply active effects to a creature.")
        .def(
            "fightMany",
            [](std::shared_ptr<CCreature> attacker, const py::iterable &opponents) {
                std::vector<std::shared_ptr<CCreature>> encounter;
                for (const auto &opponent : opponents) {
                    encounter.push_back(opponent.cast<std::shared_ptr<CCreature>>());
                }
                return CFightHandler::fightMany(attacker, encounter);
            },
            "Run a fight between one creature and multiple opponents.")
        .def_static(
            "fightManyOutcome",
            [](std::shared_ptr<CCreature> attacker, const py::iterable &opponents) {
                return CFightHandler::fightManyOutcome(attacker, creature_iterable_to_vector(opponents));
            },
            "Run a multi-opponent fight and return the detailed C++ outcome.");

    py::class_<CSlot, CGameObject, std::shared_ptr<CSlot>>(m, "CSlot", "Equipment slot configuration entry.")
        .def("getSlotName", &CSlot::getSlotName, "Return slot id.")
        .def("setSlotName", &CSlot::setSlotName, "Set slot id.")
        .def("getTypes", &CSlot::getTypes, "Return class names that can fit this slot.")
        .def("setTypes", &CSlot::setTypes, "Set class names that can fit this slot.");

    py::class_<CSlotConfig, CGameObject, std::shared_ptr<CSlotConfig>>(m, "CSlotConfig",
                                                                       "Equipment slot compatibility table.")
        .def("getConfiguration", &CSlotConfig::getConfiguration, "Return configured slots.")
        .def("setConfiguration", &CSlotConfig::setConfiguration, "Replace configured slots.")
        .def("canFit", &CSlotConfig::canFit, "Return whether an item can be equipped in a slot.")
        .def("getFittingSlots", &CSlotConfig::getFittingSlots, "Return all slots that accept an item.");

    py::class_<CMarket, CGameObject, std::shared_ptr<CMarket>>(m, "CMarket", "Trading inventory and prices.")
        .def("add", &CMarket::add, "Add an item to the market.")
        .def("remove", &CMarket::remove, "Remove an item from the market.")
        .def("getItems", &CMarket::getItems, "Return market inventory.")
        .def("setItems", &CMarket::setItems, "Replace market inventory.")
        .def("sellItem", &CMarket::sellItem, "Sell an item from the market to a creature.")
        .def("buyItem", &CMarket::buyItem, "Buy an owned item from a creature.")
        .def("getSellCost", &CMarket::getSellCost, "Return customer purchase price for an item.")
        .def("getBuyCost", &CMarket::getBuyCost, "Return merchant buyback price for an item.");

    py::class_<CTooltipHandler, CGameObject, std::shared_ptr<CTooltipHandler>>(m, "CTooltipHandler",
                                                                               "Tooltip text builder.")
        .def_static("buildTooltip", &CTooltipHandler::buildTooltip, "Build tooltip text for an object.");

    py::class_<CGameLoader, std::shared_ptr<CGameLoader>>(m, "CGameLoader",
                                                          "Factory helpers for loading game sessions and maps.")
        .def("loadGame", &CGameLoader::loadGame, "Create and initialize a game instance.")
        .def("startGameWithPlayer",
             py::overload_cast<const std::shared_ptr<CGame> &, const std::string &, std::string>(
                 &CGameLoader::startGameWithPlayer),
             "Start a map with a specific player template (template's default race).")
        .def("startGameWithPlayer",
             py::overload_cast<const std::shared_ptr<CGame> &, const std::string &, std::string, const std::string &>(
                 &CGameLoader::startGameWithPlayer),
             "Start a map with a specific player template and race override.")
        .def("startRandomGameWithPlayer",
             py::overload_cast<const std::shared_ptr<CGame> &, std::string>(&CGameLoader::startRandomGameWithPlayer),
             "Start a random map with a specific player template (template's default race).")
        .def("startRandomGameWithPlayer",
             py::overload_cast<const std::shared_ptr<CGame> &, std::string, const std::string &>(
                 &CGameLoader::startRandomGameWithPlayer),
             "Start a random map with a specific player template and race override.")
        .def("startGame", &CGameLoader::startGame, "Start a specific map with current player data.")
        .def("loadGui", &CGameLoader::loadGui, "Load and attach GUI objects for a game.")
        .def("loadSavedGame", &CGameLoader::loadSavedGame, "Load a saved game state from storage.");

    py::class_<CMapLoader, std::shared_ptr<CMapLoader>>(m, "CMapLoader", "Helpers for loading map resources.")
        .def("loadNewMapWithPlayer",
             py::overload_cast<const std::shared_ptr<CGame> &, const std::string &, std::string>(
                 &CMapLoader::loadNewMapWithPlayer),
             "Load a map and place a player template (template's default race).")
        .def("loadNewMapWithPlayer",
             py::overload_cast<const std::shared_ptr<CGame> &, const std::string &, std::string, const std::string &>(
                 &CMapLoader::loadNewMapWithPlayer),
             "Load a map and place a player template with a race override.")
        .def("loadRandomMapWithPlayer",
             py::overload_cast<const std::shared_ptr<CGame> &, std::string>(&CMapLoader::loadRandomMapWithPlayer),
             "Load a random map and place a player template (template's default race).")
        .def("loadRandomMapWithPlayer",
             py::overload_cast<const std::shared_ptr<CGame> &, std::string, const std::string &>(
                 &CMapLoader::loadRandomMapWithPlayer),
             "Load a random map and place a player template with a race override.")
        .def("loadNewMap", &CMapLoader::loadNewMap, "Load a map without changing the active player.")
        .def("save", &CMapLoader::save, "Save the current map state to a named save slot.")
        .def("saveWithResult", &CMapLoader::saveWithResult, "Save a named slot and report persistence success.");

    py::class_<CPluginLoader, std::shared_ptr<CPluginLoader>>(m, "CPluginLoader", "Helpers for loading plugins.")
        .def("loadPlugin", &CPluginLoader::loadPlugin, "Load a Python plugin resource into the game.")
        .def("loadCppPlugin", &CPluginLoader::loadCppPlugin, "Load a compiled C++ plugin type into the game.")
        .def_static("loadDynamicPlugin", &CPluginLoader::loadDynamicPlugin, py::arg("game"), py::arg("library"),
                    py::arg("entry") = "game_plugin_load_v3", "Load a dynamic C++ plugin shared library into the game.")
        .def("loadGlobalPlugins", &CPluginLoader::loadGlobalPlugins, "Load configured global plugins.")
        .def("loadMapPlugins", &CPluginLoader::loadMapPlugins, "Load configured plugins for a map.");

    py::class_<CPluginRegistrar>(m, "CPluginRegistrar", "The unified host surface plugins register content through.")
        .def(py::init<std::shared_ptr<CGame>>(), py::arg("game"))
        .def("log", &CPluginRegistrar::log, "Log a plugin message.")
        .def("registerConfigJson", &CPluginRegistrar::registerConfigJson, py::arg("id"), py::arg("jsonText"),
             "Register an object config from JSON text.")
        .def("game", &CPluginRegistrar::game, "Return the game this registrar loads plugins into.");

    auto cplugin = py::class_<CPlugin, CWrapper<CPlugin>, std::shared_ptr<CPlugin>, CGameObject>(m, "CPlugin",
                                                                                                 "Base plugin class.");
    cplugin.def(py::init_alias<>()).def("load", &CPlugin::load, "Load plugin content through a registrar.");
    m.attr("CPluginBase") = cplugin;

    py::class_<vstd::event_loop<>, std::shared_ptr<vstd::event_loop<>>>(m, "event_loop",
                                                                        "Global async event loop utility.")
        .def_static("instance", &CRuntimeBridge::event_loop_instance, "Return the singleton event loop instance.")
        .def(
            "run", [](vstd::event_loop<> &loop) { return game_async::runFrame(loop); },
            "Process ready work and render one paced frame.")
        .def("isMainThread", &vstd::event_loop<>::isMainThread, "Check whether this thread owns the event loop.")
        .def(
            "invoke",
            [pythonEventCallbacks](vstd::event_loop<> &loop, std::function<void()> callback) {
                return pythonEventCallbacks->invoke(loop, std::move(callback));
            },
            "Queue a callable for later execution; cancel pending calls when Python exits.");

    auto vector_string = py::bind_vector<std::vector<std::string>>(m, "std::vector<std::string>");
    vector_string.doc() = "Mutable list of strings.";

    py::class_<CResourcesProvider, std::shared_ptr<CResourcesProvider>>(m, "CResourcesProvider",
                                                                        "Access to packaged resource files.")
        .def("getInstance", &CResourcesProvider::getInstance,
             "Return the process-wide resource provider (compatibility facade for code without a game instance).")
        .def("getPath", &CResourcesProvider::getPath, "Resolve a resource path relative to the active resource root.")
        .def("load", &CResourcesProvider::load, "Load a resource file as text.")
        .def("getFiles", &CResourcesProvider::getFiles, "List files under a resource path.")
        .def("getActiveScope", &CResourcesProvider::getActiveScope,
             "Return the active map scope name, or an empty string when no map scope is active.")
        .def("getScopedRoots", &CResourcesProvider::getScopedRoots,
             "Return the canonical roots of all currently-registered map scopes.");
}
} // namespace nouraajd::bindings
