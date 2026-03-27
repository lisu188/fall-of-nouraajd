/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

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

#include "core/CGlobal.h"
#include "core/CUtil.h"
#include <utility>

template <typename Ret, typename... Args> struct wrap {
  static std::function<Ret(Args...)> call(pybind11::object func) {
    return [func](Args... args) -> Ret {
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
};

template <typename... Args> struct wrap<void, Args...> {
  static std::function<void(Args...)> call(pybind11::object func) {
    return [func](Args... args) {
      PY_SAFE(func(std::forward<Args>(args)...));
    };
  }
};

class CScriptHandler {
public:
  CScriptHandler();

  ~CScriptHandler();

  void
  execute_script(std::string script,
                 pybind11::object name_space = pybind11::none());

  void execute_command(std::initializer_list<std::string> list);

  std::string build_command(std::initializer_list<std::string> list);

  void add_function(std::string function_name, std::string function_code,
                    std::initializer_list<std::string> args);

  void add_class(std::string class_name, std::string function_code,
                 std::initializer_list<std::string> args);

  std::string add_class(std::string function_code,
                        std::initializer_list<std::string> args);

  void import(std::string name);

  template <typename Ret = void, typename... Args>
  std::function<Ret(Args...)> get_function(std::string functionName) {
    return wrap<Ret, Args...>::call(get_object(functionName));
  }

  template <typename Ret = void, typename... Args>
  std::function<Ret(Args...)>
  create_function(std::string functionName, std::string functionCode,
                  std::initializer_list<std::string> args) {
    vstd::fail_if(sizeof...(Args) != args.size(), "Wrong argument list!");
    add_function(functionName, functionCode, args);
    return get_function<Ret, Args...>(functionName);
  }

  template <typename Ret = void, typename... Args>
  Ret call_function(std::string name, Args... params) {
    return get_function<Ret, Args...>(name)(params...);
  }

  template <typename Ret, typename... Args>
  Ret call_created_function(std::string function_code,
                            std::initializer_list<std::string> args,
                            Args... params) {
    std::string name = "FUNC" + vstd::to_hex_hash<std::string>(function_code);
    Ret res =
        create_function<Ret, Args...>(name, function_code, args)(params...);
    execute_script("del " + name);
    return res;
  }

  template <typename... Args>
  void call_created_function(std::string function_code,
                             std::initializer_list<std::string> args,
                             Args... params) {
    std::string name = "FUNC" + vstd::to_hex_hash<std::string>(function_code);
    create_function<void, Args...>(name, function_code, args)(params...);
    execute_script("del " + name);
  }

  template <typename T = pybind11::object> T get_object(std::string name) {
    execute_script(vstd::join({"__tmp__", name}, "="));
    pybind11::object object = main_namespace["__tmp__"];
    T t = object.cast<T>();
    execute_script("del __tmp__");
    return t;
  }

private:
  pybind11::object main_module;
  pybind11::dict main_namespace;
};
