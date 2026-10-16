# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

# Clang 20 loses pack expansions and the selected index when serializing pack-indexing types.
# https://github.com/llvm/llvm-project/issues/172464
# https://github.com/llvm/llvm-project/pull/205965
if (GAME_ENABLE_PCH AND CMAKE_CXX_COMPILER_ID STREQUAL "Clang"
        AND CMAKE_CXX_COMPILER_VERSION VERSION_GREATER_EQUAL "20"
        AND CMAKE_CXX_COMPILER_VERSION VERSION_LESS "21")
    message(STATUS "Disabling GAME_ENABLE_PCH for Clang ${CMAKE_CXX_COMPILER_VERSION}: "
        "pack-indexing AST serialization is affected by LLVM #172464 and #205965.")
    set(GAME_ENABLE_PCH OFF CACHE BOOL "Enable precompiled headers for large shared game targets." FORCE)
    set(GAME_ENABLE_PCH OFF)
endif ()
