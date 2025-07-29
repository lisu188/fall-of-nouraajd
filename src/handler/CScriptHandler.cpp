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
#include "core/CMap.h"

CScriptHandler::CScriptHandler() {
  main_module = boost::python::object(
      boost::python::handle<>(PyImport_ImportModule("__main__")));
  main_namespace = main_module.attr("__dict__");
  boost::python::incref(main_module.ptr());
}

CScriptHandler::~CScriptHandler() {}

void CScriptHandler::execute_script(std::string script,
                                    boost::python::api::object name_space) {
  const char *string = script.append("\n").c_str();
  if (name_space.is_none()) {
    name_space = main_namespace;
  }
  if (!PyRun_String(string, Py_file_input, name_space.ptr(),
                    name_space.ptr())) {
    boost::python::throw_error_already_set();
  }
}

std::string
CScriptHandler::build_command(std::initializer_list<std::string> list) {
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

void CScriptHandler::add_function(std::string function_name,
                                  std::string function_code,
                                  std::initializer_list<std::string> args) {
  std::string def =
      vstd::join({"def ", function_name, "(", vstd::join(args, ","), "):"}, "");
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

void CScriptHandler::add_class(std::string class_name,
                               std::string function_code,
                               std::initializer_list<std::string> bases) {
  std::string def =
      vstd::join({"class ", class_name, "(", vstd::join(bases, ","), "):"}, "");
  std::stringstream stream;
  stream << def << std::endl;
  for (std::string line : vstd::split(function_code, '\n')) {
    stream << "\t" << line << std::endl;
  }
  execute_script(stream.str());
}

std::string
CScriptHandler::add_class(std::string function_code,
                          std::initializer_list<std::string> bases) {
  std::string name =
      vstd::join({"CLASS", vstd::to_hex_hash(function_code)}, "");
  add_class(name, function_code, bases);
  return name;
}

void CScriptHandler::import(std::string name) {
  execute_script(vstd::join({"import", name}, " "));
}

void CScriptHandler::execute_command(std::initializer_list<std::string> list) {
  execute_script(build_command(list));
}
