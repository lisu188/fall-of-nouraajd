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
#pragma once

#include "core/CConcepts.h"
#include "core/CExport.h"
#include "core/CGlobal.h"
#include "core/CUtil.h"
#include <memory>
#include <optional>
#include <utility>

class CGame;
class CGameObject;

class CScriptFlow {
  public:
    ~CScriptFlow();
    CScriptFlow(const CScriptFlow &) = delete("A script flow has one coroutine owner");
    CScriptFlow &operator=(const CScriptFlow &) = delete("A script flow has one coroutine owner");
    std::optional<json> next(const json &answer = nullptr);
    std::optional<json> fail(const std::string &message);
    std::shared_ptr<CGameObject> takeObjectArgument(const std::string &token);
    void markCommitted();
    void markItemCommitted();
    // An explicit capability replaces automatic settlement when the flow returns.
    std::move_only_function<void()> commitCallback() const;

  private:
    friend class CScriptHandler;
    struct State;
    explicit CScriptFlow(std::unique_ptr<State> state);
    std::optional<json> resume(const json &answer, const std::optional<std::string> &failure);
    std::unique_ptr<State> state;
};

template <fn::PythonReturn Ret, typename... Args>
struct GAME_CORE_LOCAL CPythonFunctionWrapper{
    static std::function<Ret(Args...)> call(pybind11::object func){return [func](Args... args) -> Ret {
        try {
            pybind11::object ret = func(std::forward<Args>(args)...);
            return ret.cast<Ret>();
        } catch (...) {
            PYTHON_LOG;
            PyErr_Clear();
            return Ret();
        }
    };
}
}
;

template <typename... Args> struct GAME_CORE_LOCAL CPythonFunctionWrapper<void, Args...> {
    static std::function<void(Args...)> call(pybind11::object func) {
        return [func](Args... args) { PY_SAFE(func(std::forward<Args>(args)...)); };
    }
};

class CScriptHandler {
  public:
    CScriptHandler();

    ~CScriptHandler();

    CScriptHandler(const CScriptHandler &) = delete("Python runtime state has one owner");
    CScriptHandler &operator=(const CScriptHandler &) = delete("Python runtime state has one owner");
    CScriptHandler(CScriptHandler &&) = delete("Python runtime state cannot move between handlers");
    CScriptHandler &operator=(CScriptHandler &&) = delete("Python runtime state cannot move between handlers");

    void releaseState();

    std::unique_ptr<CScriptFlow> createUiFlow(const std::string &entry, std::weak_ptr<CGame> game);
#if !defined(_WIN32)
    GAME_CORE_EXPORT
#endif
    std::unique_ptr<CScriptFlow> createCallbackFlow(pybind11::function callback, std::weak_ptr<CGame> game);
    static std::unique_ptr<CScriptFlow>
    createObjectFlow(const std::shared_ptr<CGameObject> &object, const std::string &method,
                     const std::vector<std::shared_ptr<CGameObject>> &arguments, std::weak_ptr<CGame> game,
                     std::shared_ptr<bool> committed = {}, std::shared_ptr<std::move_only_function<void()>> commit = {},
                     std::shared_ptr<std::move_only_function<void()>> prepareCommit = {});

    void execute_script(std::string script, pybind11::object name_space = pybind11::none());

    void execute_command(std::initializer_list<std::string> list);

    std::string build_command(std::initializer_list<std::string> list);

    void add_function(std::string function_name, std::string function_code, std::initializer_list<std::string> args);

    void add_class(std::string class_name, std::string function_code, std::initializer_list<std::string> args);

    std::string add_class(std::string function_code, std::initializer_list<std::string> args);

    void import(std::string name);

    template <typename Ret = void, typename... Args>
        requires fn::PythonReturn<Ret>
    std::function<Ret(Args...)> get_function(std::string functionName) {
        return CPythonFunctionWrapper<Ret, Args...>::call(get_object(functionName));
    }

    template <typename Ret = void, typename... Args>
        requires fn::PythonReturn<Ret>
    std::function<Ret(Args...)> create_function(std::string functionName, std::string functionCode,
                                                std::initializer_list<std::string> args) {
        vstd::fail_if(sizeof...(Args) != args.size(), "Wrong argument list!");
        add_function(functionName, functionCode, args);
        return get_function<Ret, Args...>(functionName);
    }

    template <typename Ret = void, typename... Args>
        requires fn::PythonReturn<Ret>
    Ret call_function(std::string name, Args... params) {
        return get_function<Ret, Args...>(name)(params...);
    }

    template <typename Ret, typename... Args>
        requires(!std::same_as<Ret, void> && fn::PythonReturn<Ret>)
    Ret call_created_function(std::string function_code, std::initializer_list<std::string> args, Args... params) {
        std::string name = "FUNC" + vstd::to_hex_hash<std::string>(function_code);
        Ret res = create_function<Ret, Args...>(name, function_code, args)(params...);
        execute_script("del " + name);
        return res;
    }

    template <typename... Args>
    void call_created_function(std::string function_code, std::initializer_list<std::string> args, Args... params) {
        std::string name = "FUNC" + vstd::to_hex_hash<std::string>(function_code);
        create_function<void, Args...>(name, function_code, args)(params...);
        execute_script("del " + name);
    }

    template <typename T = pybind11::object> T get_object(std::string name) { return get_py_object(name).cast<T>(); }

  private:
    pybind11::object get_py_object(std::string name);

    struct State;
    State &getState();
    std::unique_ptr<State> pythonState;
};
