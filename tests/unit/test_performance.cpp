/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026  Andrzej Lis

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

#include "core/CRuntimeBridge.h"
#include "test_harness.h"

#include <pybind11/embed.h>

void run_pathfinder_performance_tests();
void run_engine_hotspot_performance_tests();

int main() {
    pybind11::scoped_interpreter guard{};
    CRuntimeBridge::set_logger_sink(vstd::logger::sink::disabled, "");

    run_pathfinder_performance_tests();
    run_engine_hotspot_performance_tests();

    return finish_tests();
}
