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
#include "handler/CScriptHandler.h"
#include "core/CMap.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CPythonOverrides.h"
#include <memory>
#include <pybind11/eval.h>
#include <stdexcept>

namespace {
pybind11::module_ initializedUiModule() {
    const auto name = pybind11::str("ui");
    auto module = PyImport_GetModule(name.ptr());
    if (module == nullptr) {
        if (!PyErr_Occurred()) {
            PyErr_SetString(PyExc_ImportError, "Native UI flow module is not initialized: ui");
        }
        throw pybind11::error_already_set();
    }
    return pybind11::reinterpret_steal<pybind11::module_>(module);
}
} // namespace

struct CScriptHandler::State {
    pybind11::object mainModule;
    pybind11::dict mainNamespace;
};

struct CScriptFlow::State {
    pybind11::object flow;
    std::weak_ptr<CGame> game;
    std::shared_ptr<bool> committed;
    std::shared_ptr<vstd::move_only_function<void()>> commit;
    std::shared_ptr<vstd::move_only_function<void()>> prepareCommit;
    bool explicitCommit = false;
};

CScriptFlow::CScriptFlow(std::unique_ptr<State> state) : state(std::move(state)) {}

CScriptFlow::~CScriptFlow() {
    if (!state) {
        return;
    }
    if (!Py_IsInitialized()) {
        state->flow.release();
        return;
    }
    pybind11::gil_scoped_acquire acquire;
    try {
        state->flow.attr("close")();
    } catch (pybind11::error_already_set &error) {
        error.discard_as_unraisable("CScriptFlow teardown");
    }
    state.reset();
}

std::optional<json> CScriptFlow::next(const json &answer) { return resume(answer, std::nullopt); }

std::optional<json> CScriptFlow::fail(const std::string &message) { return resume(nullptr, message); }

void CScriptFlow::markCommitted() {
    if (!state->committed) {
        throw std::invalid_argument("A quest commit requires an active quest-completion operation.");
    }
    *state->committed = true;
}

void CScriptFlow::markItemCommitted() { commitCallback()(); }

vstd::move_only_function<void()> CScriptFlow::commitCallback() const {
    if (!state->commit) {
        throw std::invalid_argument("An item commit requires an active item-use operation.");
    }
    state->explicitCommit = true;
    return [commit = state->commit] { (*commit)(); };
}

std::shared_ptr<CGameObject> CScriptFlow::takeObjectArgument(const std::string &token) {
    auto owner = state->game.lock();
    if (!owner) {
        throw std::runtime_error("Cannot take a UI object after its game has been destroyed.");
    }
    pybind11::gil_scoped_acquire acquire;
    auto object = state->flow.attr("takeObjectArgument")(token).cast<std::shared_ptr<CGameObject>>();
    if (!object || object->getGame() != owner) {
        throw std::invalid_argument("A UI flow object must belong to its game session.");
    }
    return object;
}

std::optional<json> CScriptFlow::resume(const json &answer, const std::optional<std::string> &failure) {
    auto owner = state->game.lock();
    if (!owner) {
        throw std::runtime_error("Cannot resume a UI script after its game has been destroyed.");
    }
    pybind11::gil_scoped_acquire acquire;
    if (state->prepareCommit) {
        auto prepare = std::exchange(state->prepareCommit, {});
        (*prepare)();
    }
    pybind11::object exception = failure ? pybind11::cast(*failure) : pybind11::none();
    auto result = state->flow.attr("advance")(answer.dump(), exception);
    if (result.is_none()) {
        if (state->commit && !state->explicitCommit) {
            (*state->commit)();
        }
        return std::nullopt;
    }
    return json::parse(result.cast<std::string>());
}

std::unique_ptr<CScriptFlow> CScriptHandler::createUiFlow(const std::string &entry, std::weak_ptr<CGame> game) {
    getState();
    if (entry != "pause" && entry != "saveMenu" && entry != "showDefeat") {
        throw std::invalid_argument("Unknown native UI script entry: " + entry);
    }
    pybind11::gil_scoped_acquire acquire;
    auto state = std::make_unique<CScriptFlow::State>();
    state->game = game;
    auto getGame = pybind11::cpp_function([game]() {
        auto owner = game.lock();
        if (!owner) {
            throw std::runtime_error("The UI script's game is no longer available.");
        }
        return owner;
    });
    state->flow = initializedUiModule().attr("UiFlow")(entry, getGame);
    return std::unique_ptr<CScriptFlow>(new CScriptFlow(std::move(state)));
}

std::unique_ptr<CScriptFlow> CScriptHandler::createCallbackFlow(pybind11::function callback,
                                                                std::weak_ptr<CGame> game) {
    getState();
    pybind11::gil_scoped_acquire acquire;
    auto state = std::make_unique<CScriptFlow::State>();
    state->game = std::move(game);
    state->flow = initializedUiModule().attr("UiFlow").attr("fromCallback")(std::move(callback));
    return std::unique_ptr<CScriptFlow>(new CScriptFlow(std::move(state)));
}

std::unique_ptr<CScriptFlow>
CScriptHandler::createObjectFlow(const std::shared_ptr<CGameObject> &object, const std::string &method,
                                 const std::vector<std::shared_ptr<CGameObject>> &arguments, std::weak_ptr<CGame> game,
                                 std::shared_ptr<bool> committed,
                                 std::shared_ptr<vstd::move_only_function<void()>> commit,
                                 std::shared_ptr<vstd::move_only_function<void()>> prepareCommit) {
    if (!object || !Py_IsInitialized()) {
        return nullptr;
    }
    pybind11::gil_scoped_acquire acquire;
    auto override = CPythonOverrides::find_override(object.get(), method.c_str());
    if (override.is_none()) {
        return nullptr;
    }
    if (!PyCallable_Check(override.ptr())) {
        throw std::invalid_argument("A script flow hook must be callable: " + method);
    }
    auto owner = game.lock();
    if (!owner || !owner->getContext()->isActive()) {
        throw std::runtime_error("Cannot create an event flow for a closed game session.");
    }
    pybind11::tuple args(arguments.size());
    for (std::size_t index = 0; index < arguments.size(); ++index) {
        args[index] = pybind11::cast(arguments[index]);
    }
    auto callback =
        pybind11::cpp_function([override = std::move(override), args = std::move(args)]() { return override(*args); });
    auto flow = owner->getScriptHandler()->createCallbackFlow(std::move(callback), game);
    flow->state->committed = std::move(committed);
    flow->state->commit = std::move(commit);
    flow->state->prepareCommit = std::move(prepareCommit);
    return flow;
}

CScriptHandler::State &CScriptHandler::getState() {
    if (!pythonState) {
        throw std::runtime_error("Python script handler state has been released.");
    }
    return *pythonState;
}

CScriptHandler::CScriptHandler() {
    pythonState = std::make_unique<State>();
    auto &state = getState();
    state.mainModule = pybind11::module::import("__main__");
    state.mainNamespace = state.mainModule.attr("__dict__");
}

CScriptHandler::~CScriptHandler() = default;

void CScriptHandler::releaseState() { pythonState.reset(); }

void CScriptHandler::execute_script(std::string script, pybind11::object name_space) {
    auto &state = getState();
    auto target = name_space.is_none() ? state.mainNamespace : name_space;
    pybind11::exec(script + "\n", target, target);
}

std::string CScriptHandler::build_command(std::initializer_list<std::string> list) {
    std::string command;
    unsigned int pos = 0;
    for (auto it = list.begin(); it != list.end(); it++, pos++) {
        std::string part = vstd::replace(*it, "\"", "\\\"");
        if (pos == 0) {
            command.append(part);
            command.append("(");
        } else {
            command.append("\"");
            command.append(part);
            command.append("\"");
            if (pos < list.size() - 1) {
                command.append(",");
            } else {
                command.append(")");
            }
        }
    }
    return command;
}

void CScriptHandler::add_function(std::string function_name, std::string function_code,
                                  std::initializer_list<std::string> args) {
    std::string def = vstd::join({"def ", function_name, "(", vstd::join(args, ","), "):"}, "");
    std::stringstream stream;
    stream << def << std::endl;
    for (std::string line : vstd::split(function_code, '\n')) {
        stream << "\t" << line << std::endl;
    }
    try {
        PY_UNSAFE(execute_script(stream.str()));
    } catch (...) {
        add_function(function_name, "print('Compilation failure!')", args);
    }
}

void CScriptHandler::add_class(std::string class_name, std::string function_code,
                               std::initializer_list<std::string> bases) {
    std::string def = vstd::join({"class ", class_name, "(", vstd::join(bases, ","), "):"}, "");
    std::stringstream stream;
    stream << def << std::endl;
    for (std::string line : vstd::split(function_code, '\n')) {
        stream << "\t" << line << std::endl;
    }
    execute_script(stream.str());
}

std::string CScriptHandler::add_class(std::string function_code, std::initializer_list<std::string> bases) {
    std::string name = vstd::join({"CLASS", vstd::to_hex_hash(function_code)}, "");
    add_class(name, function_code, bases);
    return name;
}

void CScriptHandler::import(std::string name) { execute_script(vstd::join({"import", name}, " ")); }

void CScriptHandler::execute_command(std::initializer_list<std::string> list) { execute_script(build_command(list)); }

pybind11::object CScriptHandler::get_py_object(std::string name) {
    execute_script(vstd::join({"__tmp__", name}, "="));
    pybind11::object object = getState().mainNamespace["__tmp__"];
    execute_script("del __tmp__");
    return object;
}
