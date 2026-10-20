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
#include "bindings/CModuleBindings.h"
#include "core/CController.h"
#include "bindings/CModuleCallbacks.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CModuleInit.h"
#include "core/CPlaytestTrace.h"
#include "core/CSceneManager.h"
#include "core/CWrapper.h"
#include "object/CCreatureClass.h"
#include "object/CCreatureClassTrack.h"
#include "object/CCreatureRace.h"
#include "object/CCreatureTemplate.h"
#include "plugin/CGameplayTypeTable.h"

namespace py = pybind11;

namespace nouraajd::bindings {
bool CPythonEventCallbacks::requestTransition(const std::shared_ptr<CGame> &game, std::string mapName,
                                              std::function<void()> beforeEntry, std::function<void(bool)> completion) {
    if (!active.load()) {
        return false;
    }
    const auto id = nextId++;
    auto bundle =
        std::make_shared<TransitionCallbacks>(TransitionCallbacks{std::move(beforeEntry), std::move(completion)});
    transitions.emplace(id, bundle);
    const std::weak_ptr<TransitionCallbacks> weakBundle = bundle;
    const auto weakOwner = weak_from_this();
    CMapTransitionRequest request;
    request.targetMap = std::move(mapName);
    request.beforePlayerEntry = [weakOwner, weakBundle]() {
        auto owner = weakOwner.lock();
        if (!owner || !owner->active.load()) {
            throw std::runtime_error("Python transition callbacks have been released");
        }
        py::gil_scoped_acquire gil;
        auto bundle = weakBundle.lock();
        if (!owner->active.load() || !bundle) {
            throw std::runtime_error("Python transition callbacks have been released");
        }
        bundle->beforeEntry();
    };
    request.onFinished = [weakOwner, id](bool success) {
        auto owner = weakOwner.lock();
        if (!owner || !owner->active.load()) {
            return;
        }
        py::gil_scoped_acquire gil;
        if (!owner->active.load()) {
            return;
        }
        auto pending = owner->transitions.extract(id);
        if (!pending.empty()) {
            pending.mapped()->completion(success);
        }
    };
    try {
        return game->requestMapTransition(std::move(request));
    } catch (...) {
        transitions.erase(id);
        throw;
    }
}

bool CPythonEventCallbacks::requestTransitionFlow(const std::shared_ptr<CGame> &game, std::string mapName,
                                                  std::unique_ptr<CScriptFlow> flow,
                                                  std::function<void(bool)> completion,
                                                  std::function<void()> commitBeforeEntry) {
    if (!active.load()) {
        return false;
    }
    const auto id = nextId++;
    transitions.emplace(id, std::make_shared<TransitionCallbacks>(
                                TransitionCallbacks{std::move(commitBeforeEntry), std::move(completion)}));
    const auto weakOwner = weak_from_this();
    const std::weak_ptr<CGuiHandler> weakGui = game->getGuiHandler();
    auto prepare = [weakOwner, weakGui, flow = std::move(flow)]() mutable -> vstd::task<void> {
        auto owner = weakOwner.lock();
        auto gui = weakGui.lock();
        if (!owner || !owner->active.load() || !gui) {
            throw std::runtime_error("Python transition callbacks have been released");
        }
        return gui->runScriptFlowAsync(std::move(flow));
    };
    auto finish = [weakOwner, id](bool success) {
        auto owner = weakOwner.lock();
        if (!owner || !owner->active.load()) {
            return;
        }
        py::gil_scoped_acquire gil;
        if (!owner->active.load()) {
            return;
        }
        auto pending = owner->transitions.extract(id);
        if (!pending.empty() && pending.mapped()->completion) {
            pending.mapped()->completion(success);
        }
    };
    auto commit = [weakOwner, id] {
        auto owner = weakOwner.lock();
        if (!owner || !owner->active.load()) {
            throw std::runtime_error("Python transition callbacks have been released");
        }
        py::gil_scoped_acquire gil;
        auto pending = owner->transitions.find(id);
        if (!owner->active.load() || pending == owner->transitions.end()) {
            throw std::runtime_error("Python transition callbacks have been released");
        }
        auto bundle = pending->second;
        if (bundle->beforeEntry) {
            bundle->beforeEntry();
        }
    };
    try {
        const bool accepted = game->changeMapWithPreparationFlow(std::move(mapName), std::move(prepare),
                                                                 std::move(finish), std::move(commit));
        if (!accepted) {
            transitions.erase(id);
        }
        return accepted;
    } catch (...) {
        transitions.erase(id);
        throw;
    }
}

bool CPythonEventCallbacks::invoke(vstd::event_loop<> &loop, std::function<void()> callback) {
    if (!active.load()) {
        return false;
    }
    const auto id = nextId++;
    callbacks.emplace(id, std::move(callback));
    const auto weak = weak_from_this();
    if (!loop.invoke([weak, id]() {
            auto owner = weak.lock();
            if (!owner || !owner->active.load()) {
                return;
            }
            py::gil_scoped_acquire gil;
            if (!owner->active.load()) {
                return;
            }
            auto pending = owner->callbacks.extract(id);
            if (!pending.empty()) {
                pending.mapped()();
            }
        })) {
        callbacks.erase(id);
        return false;
    }
    return true;
}

void CPythonEventCallbacks::shutdown() {
    active.store(false);
    // Release Python captures while the interpreter is alive. The native queue retains
    // only weak references and must neither invoke nor destroy Python callbacks at exit.
    auto pending = std::move(callbacks);
    callbacks.clear();
    auto pendingTransitions = std::move(transitions);
    transitions.clear();
}

std::vector<std::shared_ptr<CCreature>> creature_iterable_to_vector(const py::iterable &iterable) {
    std::vector<std::shared_ptr<CCreature>> creatures;
    for (const auto &item : iterable) {
        creatures.push_back(item.is_none() ? nullptr : item.cast<std::shared_ptr<CCreature>>());
    }
    return creatures;
}

template <typename T> bool try_downcast(const py::object &instance, std::shared_ptr<CGameObject> &out) {
    if (!py::isinstance<T>(instance)) {
        return false;
    }
    out = std::static_pointer_cast<CGameObject>(instance.cast<std::shared_ptr<T>>());
    return true;
}

std::shared_ptr<CGameObject> cast_registered_python_object(const py::object &instance) {
    std::shared_ptr<CGameObject> result;
#define FN_IGNORE(T, ...)
#define FN_DOWNCAST(T, ...)                                                                                            \
    if (try_downcast<T>(instance, result)) {                                                                           \
        return result;                                                                                                 \
    }
    FN_GAMEPLAY_TYPES(FN_IGNORE, FN_DOWNCAST)
    FN_DOWNCAST(CPlugin)
#undef FN_DOWNCAST
#undef FN_IGNORE
    return instance.cast<std::shared_ptr<CGameObject>>();
}

void register_python_binding_type_metadata() {
    // Metadata only (serializers/casts) — deliberately not builders, so gameplay types stay
    // non-constructible until the native gameplay plugin actually loads. The gameplay row list is
    // the shared plugin/CGameplayTypeTable.h.
    //
    // CStats/CDamage are NOT gameplay table rows (they are core value types registered by
    // registerCoreTypes), but their metadata must also be registered from this translation unit.
    // On Linux this file is compiled into the _game extension rather than game_core (see
    // the binding object target in CMakeLists.txt), so registering here populates the conversion tables the
    // extension module itself resolves against. Dropping these two lines broke deserialization of
    // the shared_ptr<CDamage>/shared_ptr<CStats> properties carried by items and creatures
    // ("bad any_cast" while loading saved maps) on Linux only, while Windows kept working because
    // there CModule.cpp is part of game_core.
    CTypes::register_type_metadata<CStats, CGameObject>();
    CTypes::register_type_metadata<CDamage, CGameObject>();

#define FN_TYPE(T, ...) CTypes::register_type_metadata<T, __VA_ARGS__>();
#define FN_WRAPPED(T, ...)                                                                                             \
    CTypes::register_type_metadata<T, __VA_ARGS__>();                                                                  \
    CTypes::register_type_metadata<CWrapper<T>, T, __VA_ARGS__>();
    FN_GAMEPLAY_TYPES(FN_TYPE, FN_WRAPPED)
#undef FN_WRAPPED
#undef FN_TYPE
}
} // namespace nouraajd::bindings

void init_game_module(py::module_ &m) {
    using namespace nouraajd::bindings;
    auto pythonEventCallbacks = std::make_shared<CPythonEventCallbacks>();
    py::module_::import("atexit").attr("register")(
        py::cpp_function([pythonEventCallbacks]() { pythonEventCallbacks->shutdown(); }));
    CPlaytestTrace::configureFromEnvironment();
    register_python_binding_type_metadata();

    bindFoundationAndSession(m, pythonEventCallbacks);
    bindGraphicsAndWorld(m);
    bindGameplayObjects(m);
    bindServices(m, pythonEventCallbacks);
    bindCreatures(m);
    bindPanelsAndUtilities(m);
}
