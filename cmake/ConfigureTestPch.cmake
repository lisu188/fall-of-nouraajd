# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

function(configure_test_pch target_name pch_target)
    # Resource-root and profiling definitions distinguish several test executables.
    # Reuse only an identical compile environment; a rejected PCH wastes time and
    # can hide missing includes. Imported usage requirements match through links.
    foreach (property COMPILE_OPTIONS COMPILE_DEFINITIONS INCLUDE_DIRECTORIES LINK_LIBRARIES
            POSITION_INDEPENDENT_CODE CXX_VISIBILITY_PRESET VISIBILITY_INLINES_HIDDEN CXX_STANDARD)
        get_target_property(candidate "${target_name}" "${property}")
        get_target_property(reference "${pch_target}" "${property}")
        if (candidate MATCHES "-NOTFOUND$")
            set(candidate "")
        endif ()
        if (reference MATCHES "-NOTFOUND$")
            set(reference "")
        endif ()
        if (NOT "${candidate}" STREQUAL "${reference}")
            return()
        endif ()
    endforeach ()
    target_precompile_headers(${target_name} REUSE_FROM ${pch_target})
endfunction()
