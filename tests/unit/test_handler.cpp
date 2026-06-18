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
#include "test_harness.h"

#include <pybind11/embed.h>
#include <string>

namespace {

void test_script_handler_executes_commands_and_wraps_functions() {
    CScriptHandler handler;

    handler.execute_script("value = 4");
    expect_true(handler.get_object<int>("value") == 4, "execute_script should write into the main namespace");

    pybind11::dict custom_namespace;
    custom_namespace["seed"] = 7;
    handler.execute_script("result = seed + 5", custom_namespace);
    expect_true(custom_namespace["result"].cast<int>() == 12, "execute_script should honor a provided namespace");

    const auto built = handler.build_command({"capture", "alpha", "beta"});
    expect_true(built == "capture(\"alpha\",\"beta\")", "build_command should quote string arguments");

    handler.execute_script("captured = ''\n"
                           "def capture(first, second):\n"
                           "\tglobal captured\n"
                           "\tcaptured = first + ':' + second");
    handler.execute_command({"capture", "alpha", "beta"});
    expect_true(handler.get_object<std::string>("captured") == "alpha:beta",
                "execute_command should execute the built Python call");

    handler.import("math");
    handler.execute_script("root_value = math.isqrt(81)");
    expect_true(handler.get_object<int>("root_value") == 9, "import should load Python modules into the namespace");

    handler.add_function("triple_value", "return value * 3", {"value"});
    expect_true(handler.call_function<int, int>("triple_value", 7) == 21,
                "add_function should compile callable Python code");

    auto multiply = handler.create_function<int, int, int>("multiply_values", "return left * right", {"left", "right"});
    expect_true(multiply(6, 7) == 42, "create_function should return a typed callable wrapper");
    expect_true(handler.call_function<int, int, int>("multiply_values", 3, 5) == 15,
                "call_function should invoke previously created Python callables");

    handler.execute_script("observed = 0");
    auto store_value =
        handler.create_function<void, int>("store_value", "global observed\nobserved = value", {"value"});
    store_value(123);
    expect_true(handler.get_object<int>("observed") == 123,
                "void wrappers should execute Python callables without returning values");

    handler.execute_script("def returns_text():\n"
                           "\treturn 'oops'");
    auto invalid_cast = handler.get_function<int>("returns_text");
    expect_true(invalid_cast() == 0, "typed wrappers should return a default value after Python cast failures");

    handler.add_function("broken_function", "return )", {});
    handler.call_function<void>("broken_function");

    handler.add_class("NamedScriptClass", "def value(self):\n\treturn 9", {});
    handler.execute_script("named_instance = NamedScriptClass()");
    auto named_instance = handler.get_object<pybind11::object>("named_instance");
    expect_true(named_instance.attr("value")().cast<int>() == 9, "add_class should compile named Python classes");

    const auto generated_class = handler.add_class("def value(self):\n\treturn 11", {});
    handler.execute_script("generated_instance = " + generated_class + "()");
    auto generated_instance = handler.get_object<pybind11::object>("generated_instance");
    expect_true(generated_instance.attr("value")().cast<int>() == 11,
                "add_class overload should return a usable generated class name");

    expect_true(handler.call_created_function<int, int>("return value * 2", {"value"}, 8) == 16,
                "call_created_function should compile, call and delete temporary Python functions");

    handler.execute_script("created_void_value = 0");
    handler.call_created_function("global created_void_value\ncreated_void_value = value + 1", {"value"}, 4);
    expect_true(handler.get_object<int>("created_void_value") == 5,
                "void call_created_function should update Python state and clean up its temporary function");
}

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};

    test_script_handler_executes_commands_and_wraps_functions();

    return finish_tests();
}
