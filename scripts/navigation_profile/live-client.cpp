/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/
#include <valgrind/callgrind.h>

extern "C" void navigationProfileStart() {
    CALLGRIND_START_INSTRUMENTATION;
    CALLGRIND_ZERO_STATS;
}

extern "C" void navigationProfileStop() {
    CALLGRIND_STOP_INSTRUMENTATION;
    CALLGRIND_DUMP_STATS;
}
