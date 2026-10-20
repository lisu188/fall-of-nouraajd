# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

# This header-based project has no C++ modules. Automatic scanning excludes sources
# from unity builds and adds module compiler flags that bypass compiler caches.
set(CMAKE_CXX_SCAN_FOR_MODULES OFF)

if (NOT CMAKE_SCRIPT_MODE_FILE)
    file(GENERATE OUTPUT "${CMAKE_BINARY_DIR}/game-build-policy.json"
        CONTENT "{\"CMAKE_CXX_SCAN_FOR_MODULES\":\"OFF\"}\n")
endif ()
