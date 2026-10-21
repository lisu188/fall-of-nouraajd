/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/
#include "core/CRuntimeBridge.h"
#include "test_harness.h"

#include <pybind11/embed.h>

void run_simulation_region_tests();

int main() {
    pybind11::scoped_interpreter interpreter;
    CRuntimeBridge::set_logger_sink(vstd::logger::sink::disabled, "");
    run_simulation_region_tests();
    return finish_tests();
}
