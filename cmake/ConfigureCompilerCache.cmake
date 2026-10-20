# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

option(GAME_ENABLE_COMPILER_CACHE "Use a bounded project compiler cache when available." ON)
set(GAME_CCACHE_DIR "${CMAKE_SOURCE_DIR}/.cache/ccache" CACHE PATH "Project compiler cache directory.")
set(GAME_REAL_CXX_COMPILER "$ENV{GAME_REAL_CXX_COMPILER}" CACHE FILEPATH
    "Optional underlying compiler executable when CMAKE_CXX_COMPILER is a wrapper.")

if (GAME_ENABLE_COMPILER_CACHE AND CMAKE_CXX_COMPILER_ID STREQUAL "GNU" AND UNIX)
    find_program(GAME_CCACHE_EXECUTABLE ccache)
    if (GAME_CCACHE_EXECUTABLE)
        # Hash GCC's real frontend as well as the selected driver. A wrapper script's
        # content alone does not identify the compiler it eventually executes.
        set(game_cache_identity_files)
        foreach(language C CXX)
            if (language STREQUAL "CXX")
                set(frontend cc1plus)
            else ()
                set(frontend cc1)
            endif ()
            execute_process(COMMAND "${CMAKE_${language}_COMPILER}" "-print-prog-name=${frontend}"
                OUTPUT_VARIABLE frontend_path OUTPUT_STRIP_TRAILING_WHITESPACE
                RESULT_VARIABLE frontend_status ERROR_QUIET)
            if (frontend_status EQUAL 0 AND EXISTS "${frontend_path}")
                list(APPEND game_cache_identity_files "${frontend_path}")
            endif ()
        endforeach()
        if (GAME_REAL_CXX_COMPILER)
            if (NOT EXISTS "${GAME_REAL_CXX_COMPILER}")
                message(FATAL_ERROR "GAME_REAL_CXX_COMPILER does not exist: ${GAME_REAL_CXX_COMPILER}")
            endif ()
            list(APPEND game_cache_identity_files "${GAME_REAL_CXX_COMPILER}")
        endif ()
        list(REMOVE_DUPLICATES game_cache_identity_files)
        list(JOIN game_cache_identity_files ":" game_cache_identity)
        set(game_cache_launcher "${CMAKE_COMMAND}" -E env
            "CCACHE_DIR=${GAME_CCACHE_DIR}"
            "CCACHE_MAXSIZE=1G"
            "CCACHE_COMPILERCHECK=content"
            "CCACHE_SLOPPINESS=pch_defines,time_macros"
            "CCACHE_EXTRAFILES=${game_cache_identity}"
            "${GAME_CCACHE_EXECUTABLE}")
        foreach(language C CXX)
            # Preserve custom launchers, including coverage diagnostics that deliberately disable caching.
            if (NOT DEFINED CMAKE_${language}_COMPILER_LAUNCHER
                    OR CMAKE_${language}_COMPILER_LAUNCHER STREQUAL "ccache"
                    OR CMAKE_${language}_COMPILER_LAUNCHER STREQUAL GAME_CCACHE_EXECUTABLE)
                set(CMAKE_${language}_COMPILER_LAUNCHER "${game_cache_launcher}")
            endif ()
        endforeach()
    endif ()
endif ()
