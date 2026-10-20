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
#include "CModuleCallbacks.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CMap.h"
#include "core/CSceneManager.h"
#include "core/CSlotConfig.h"
#include "core/CTags.h"
#include "gui/CGui.h"
#include "object/CObject.h"
#include <pybind11/operators.h>

namespace py = pybind11;

namespace nouraajd::bindings {
namespace {
vstd::task<void> runPostedScriptFlow(std::weak_ptr<CGuiHandler> gui, std::unique_ptr<CScriptFlow> flow) {
    try {
        co_await vstd::post(vstd::event_loop<>::instance());
        if (auto owner = gui.lock()) {
            co_await owner->runScriptFlowAsync(std::move(flow));
        }
    } catch (const vstd::task_cancelled &) {
        throw;
    } catch (const vstd::scheduler_rejected &) {
        throw;
    } catch (const std::exception &error) {
        vstd::logger::error("Session script callback failed: " + std::string(error.what()));
    }
}

void postScriptFlow(const std::shared_ptr<CGame> &game, py::function callback) {
    auto context = game->getContext();
    if (!context->isActive()) {
        throw std::runtime_error("Cannot post script work to a closed game session.");
    }
    auto flow = game->getScriptHandler()->createCallbackFlow(std::move(callback), game);
    context->spawnTask(runPostedScriptFlow(game->getGuiHandler(), std::move(flow)));
}

void game_object_setattr(CGameObject &self, const std::string &name, const py::handle &value) {
    if (py::isinstance<py::bool_>(value)) {
        self.setBoolProperty(name, value.cast<bool>());
        return;
    }
    if (py::isinstance<py::int_>(value)) {
        self.setNumericProperty(name, value.cast<int>());
        return;
    }
    if (py::isinstance<py::str>(value)) {
        self.setStringProperty(name, value.cast<std::string>());
        return;
    }
    if (py::isinstance<CGameObject>(value)) {
        self.setObjectProperty(name, value.cast<std::shared_ptr<CGameObject>>());
        return;
    }
    throw py::type_error("Unsupported CGameObject property type");
}

py::object game_object_getattr(CGameObject &self, const std::string &name) {
    if (!self.hasProperty(name)) {
        throw py::attribute_error(name);
    }

    try {
        return py::bool_(self.getBoolProperty(name));
    } catch (const std::exception &) {
    }
    try {
        return py::int_(self.getNumericProperty(name));
    } catch (const std::exception &) {
    }
    try {
        return py::str(self.getStringProperty(name));
    } catch (const std::exception &) {
    }
    try {
        return py::cast(self.getObjectProperty<CGameObject>(name));
    } catch (const std::exception &) {
    }

    throw py::attribute_error(name);
}
} // namespace

void bindFoundationAndSession(py::module_ &m, const std::shared_ptr<CPythonEventCallbacks> &pythonEventCallbacks) {
    py::enum_<CTag>(m, "CTag", "Canonical gameplay tag identifier.")
        .value("BUFF", CTag::Buff)
        .value("COMPOUND", CTag::Compound)
        .value("CURSE", CTag::Curse)
        .value("CURSED", CTag::Cursed)
        .value("HEAL", CTag::Heal)
        .value("MANA", CTag::Mana)
        .value("QUEST", CTag::Quest)
        .value("STUN", CTag::Stun)
        .value("WAND", CTag::Wand);

    py::class_<CGameObject, std::shared_ptr<CGameObject>>(
        m, "CGameObject", "Base engine object with dynamic string, numeric, bool, and object properties.")
        .def("getName", &CGameObject::getName, "Return the object name.")
        .def("getType", &CGameObject::getType, "Return the runtime class/type name.")
        .def("getTypeId", &CGameObject::getTypeId, "Return the configured type id used to spawn this object.")
        .def("getGame", &CGameObject::getGame, "Return the owning game instance.")
        .def("getStringProperty", &CGameObject::getStringProperty, "Return a string property by name.")
        .def("getNumericProperty", &CGameObject::getNumericProperty, "Return an integer property by name.")
        .def("getBoolProperty", &CGameObject::getBoolProperty, "Return a boolean property by name.")
        .def("setStringProperty", &CGameObject::setStringProperty, "Set a string property by name.")
        .def("setNumericProperty", &CGameObject::setNumericProperty, "Set an integer property by name.")
        .def("setBoolProperty", &CGameObject::setBoolProperty, "Set a boolean property by name.")
        .def("notifyPropertyChanged", &CGameObject::notifyPropertyChanged,
             "Emit generic and property-specific property change signals.")
        .def("getObjectProperty", &CGameObject::getObjectProperty<CGameObject>, "Return an object property by name.")
        .def("setObjectProperty", &CGameObject::setObjectProperty<CGameObject>, "Set an object property by name.")
        .def("incProperty", &CGameObject::incProperty, "Increment an integer property by value.")
        .def("ptr", &CGameObject::ptr<CGameObject>, "Return this object as a shared pointer.")
        .def("clone", &CGameObject::clone<CGameObject>, "Clone this object using engine serialization.")
        .def("addTag", py::overload_cast<CTag>(&CGameObject::addTag), "Add a canonical tag enum to this object.")
        .def("addTag", py::overload_cast<const std::string &>(&CGameObject::addTag),
             "Add a canonical tag string to this object.")
        .def("removeTag", py::overload_cast<CTag>(&CGameObject::removeTag),
             "Remove a canonical tag enum from this object.")
        .def("removeTag", py::overload_cast<const std::string &>(&CGameObject::removeTag),
             "Remove a canonical tag string from this object.")
        .def("hasTag", py::overload_cast<CTag>(&CGameObject::hasTag),
             "Return whether this object has the given canonical tag enum.")
        .def("hasTag", py::overload_cast<const std::string &>(&CGameObject::hasTag),
             "Return whether this object has the given canonical tag string.")
        .def("__setattr__", &game_object_setattr, "Alias for dynamic property assignment.")
        .def("__getattr__", &game_object_getattr, "Alias for dynamic property lookup.");

    py::class_<Coords>(m, "Coords", "3D integer coordinates (x, y, z).")
        .def(py::init<int, int, int>())
        .def_readonly("x", &Coords::x)
        .def_readonly("y", &Coords::y)
        .def_readonly("z", &Coords::z)
        .def(py::self == py::self)
        .def(py::self != py::self)
        .def(py::self < py::self)
        .def(py::self <= py::self)
        .def(py::self > py::self)
        .def(py::self >= py::self)
        .def(py::self + py::self)
        .def(py::self - py::self)
        .def(-py::self)
        .def(py::self * int())
        .def(int() * py::self);

    std::shared_ptr<CGameObject> (CGame::*createObject)(std::string) = &CGame::createObject<CGameObject>;

    py::class_<CScriptHandler, std::shared_ptr<CScriptHandler>>(m, "CScriptHandler",
                                                                "Python script execution service.");

    py::class_<CGameContext, std::shared_ptr<CGameContext>>(m, "CGameContext",
                                                            "Runtime service context owned by a game instance.")
        .def("getObjectHandler", &CGameContext::getObjectHandler, "Return the object factory/registry handler.")
        .def("getGuiHandler", &CGameContext::getGuiHandler, "Return the GUI handler service.")
        .def("getScriptHandler", &CGameContext::getScriptHandler, "Return the Python script execution service.")
        .def("getRngHandler", &CGameContext::getRngHandler, "Return the random encounter/loot handler.")
        .def("isActive", &CGameContext::isActive, "Return whether this game context still accepts session work.")
        .def("shutdown", static_cast<void (CGameContext::*)()>(&CGameContext::shutdown),
             "Explicitly shut down this game context and release session state.")
        .def("getTransitionGeneration", &CGameContext::getTransitionGeneration,
             "Return the current transition/session generation.")
        .def("captureTransitionGeneration", &CGameContext::captureTransitionGeneration,
             "Capture the current transition/session generation for deferred callbacks.")
        .def("isTransitionGenerationCurrent", &CGameContext::isTransitionGenerationCurrent,
             "Return whether a captured transition/session generation is still current.")
        .def("getMapSessionStore", &CGameContext::getMapSessionStore,
             "Return the context-owned persistent map session store.");

    py::class_<CMapSessionStore, std::shared_ptr<CMapSessionStore>>(
        m, "CMapSessionStore", "Context-owned cache of loaded maps retained across transitions.")
        .def("put", py::overload_cast<const std::shared_ptr<CMap> &, const std::string &>(&CMapSessionStore::put),
             py::arg("map"), py::arg("instanceId") = "", "Retain a loaded map session.")
        .def("get", &CMapSessionStore::get, py::arg("mapName"), py::arg("instanceId") = "",
             "Return a retained map session or None.")
        .def("contains", &CMapSessionStore::contains, py::arg("mapName"), py::arg("instanceId") = "",
             "Return whether a map session is retained.")
        .def("evict", &CMapSessionStore::evict, py::arg("mapName"), py::arg("instanceId") = "",
             "Drop a retained map session.")
        .def("clear", &CMapSessionStore::clear, "Drop every retained map session.")
        .def("size", &CMapSessionStore::size, "Return the number of retained map sessions.");

    py::enum_<CSceneManager::TransitionState>(m, "CSceneTransitionState", "Scene transition lifecycle state.")
        .value("Idle", CSceneManager::TransitionState::Idle)
        .value("TransitionPending", CSceneManager::TransitionState::TransitionPending)
        .value("Transitioning", CSceneManager::TransitionState::Transitioning);

    py::class_<CMapTransitionRequest>(
        m, "CMapTransitionRequest",
        "Opt-in explicit map transition request supporting persistent map sessions. Default flags reproduce "
        "the legacy reload-compatible CGame.changeMap behavior.")
        .def(py::init<>())
        .def_readwrite("targetMap", &CMapTransitionRequest::targetMap, "Destination map name.")
        .def_readwrite("targetCoords", &CMapTransitionRequest::targetCoords,
                       "Optional player placement; None places the player at the destination entry.")
        .def_readwrite("reuseLoadedMap", &CMapTransitionRequest::reuseLoadedMap,
                       "Reuse a retained destination session instead of reloading it from content.")
        .def_readwrite("retainSourceMap", &CMapTransitionRequest::retainSourceMap,
                       "Retain the source map session so it can be revisited later.")
        .def_readwrite("returnAnchor", &CMapTransitionRequest::returnAnchor,
                       "Optional session anchor used to retain and look up map sessions.")
        .def_readwrite("carryTurn", &CMapTransitionRequest::carryTurn,
                       "Copy the source map turn onto the destination map (legacy behavior).");

    bool (CSceneManager::*requestMapChange)(const std::shared_ptr<CGame> &, std::string) =
        &CSceneManager::requestMapChange;
    bool (CSceneManager::*requestMapChangeWithRequest)(const std::shared_ptr<CGame> &, CMapTransitionRequest) =
        &CSceneManager::requestMapChange;

    py::class_<CSceneManager, std::shared_ptr<CSceneManager>>(m, "CSceneManager",
                                                              "Owns queued map transition state and execution.")
        .def("requestMapChange", requestMapChange, "Queue a map transition request.")
        .def("requestMapChange", requestMapChangeWithRequest, "Queue an explicit map transition request.")
        .def("isTransitionPending", &CSceneManager::isTransitionPending,
             "Return whether a map transition is pending or executing.")
        .def("getTransitionState", &CSceneManager::getTransitionState, "Return the current transition state.")
        .def("getTransitionStateName", &CSceneManager::getTransitionStateName,
             "Return the current transition state name.")
        .def("getPendingMapName", &CSceneManager::getPendingMapName, "Return the queued target map name.");

    py::class_<CGame, CGameObject, std::shared_ptr<CGame>>(
        m, "CGame", "Top-level game container holding the active map, handlers, and GUI.")
        .def("getMap", &CGame::getMap, "Return the currently loaded map.")
        .def("changeMap", &CGame::changeMap, "Load and switch to another map.")
        .def("post", &postScriptFlow, "Post a callback owned and cancelled by this game session.")
        .def("runUiFlowLater", &postScriptFlow,
             "Post a session-owned Python UI generator and await its modal requests natively.")
        .def(
            "createWeakResolver",
            [](const std::shared_ptr<CGame> &game) {
                return py::cpp_function([owner = std::weak_ptr<CGame>(game)]() {
                    auto game = owner.lock();
                    if (!game) {
                        throw std::runtime_error("The game session is no longer available.");
                    }
                    return game;
                });
            },
            "Create a callable that resolves the game without retaining it.")
        .def(
            "changeMapWithPreparationFlow",
            [pythonEventCallbacks](const std::shared_ptr<CGame> &game, std::string mapName, py::function beforeEntry,
                                   std::function<void(bool)> completion, std::function<void()> commitBeforeEntry) {
                auto flow = game->getScriptHandler()->createCallbackFlow(std::move(beforeEntry), game);
                return pythonEventCallbacks->requestTransitionFlow(game, std::move(mapName), std::move(flow),
                                                                   std::move(completion), std::move(commitBeforeEntry));
            },
            py::arg("mapName"), py::arg("beforeEntry"), py::arg("completion"),
            py::arg("commitBeforeEntry") = py::none(),
            "Queue an awaitable preparation, then commit synchronously immediately before destination entry.")
        .def(
            "changeMapWithPreparation",
            [pythonEventCallbacks](const std::shared_ptr<CGame> &game, std::string mapName,
                                   std::function<void()> beforeEntry, std::function<void(bool)> completion) {
                return pythonEventCallbacks->requestTransition(game, std::move(mapName), std::move(beforeEntry),
                                                               std::move(completion));
            },
            "Queue a transition, preparing the player after loading and before entry; report success or failure.")
        .def("requestMapTransition", &CGame::requestMapTransition,
             "Queue an explicit map transition request (opt-in persistent map sessions).")
        .def("loadPlugin", &CGame::loadPlugin, "Load a plugin object into the game.")
        .def("getContext", &CGame::getContext, "Return the runtime service context.")
        .def("getGuiHandler", &CGame::getGuiHandler, "Return the GUI handler service.")
        .def("getObjectHandler", &CGame::getObjectHandler, "Return the object factory/registry handler.")
        .def("getSlotConfiguration", &CGame::getSlotConfiguration, "Return the equipment slot compatibility table.")
        .def("getSceneManager", &CGame::getSceneManager, "Return the scene transition manager.")
        .def("getRngHandler", &CGame::getRngHandler, "Return the random encounter/loot handler.")
        .def("createObject", createObject, "Create an object by configured type id.")
        .def("getResourcesProvider", &CGame::getResourcesProvider,
             "Return the game's context-owned resources provider (map-scoped path resolution).")
        .def("getGui", &CGame::getGui, "Return the GUI root object.");
}
} // namespace nouraajd::bindings
