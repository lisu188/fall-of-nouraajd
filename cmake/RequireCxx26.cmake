# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
include_guard(GLOBAL)

if (NOT "cxx_std_26" IN_LIST CMAKE_CXX_COMPILE_FEATURES)
    message(FATAL_ERROR "C++26 is required without fallback. Use GCC 15+ or LLVM 20.1.8+ clang-cl.")
endif ()
if (WIN32 AND NOT (CMAKE_CXX_COMPILER_ID STREQUAL "Clang"
        AND CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC"
        AND CMAKE_CXX_COMPILER_VERSION VERSION_GREATER_EQUAL "20.1.8"))
    message(FATAL_ERROR "The Windows desktop build requires LLVM 20.1.8+ clang-cl with the Visual Studio SDK/STL.")
endif ()
if (CMAKE_CXX_COMPILER_ID STREQUAL "GNU" AND CMAKE_CXX_COMPILER_VERSION VERSION_LESS "15")
    message(FATAL_ERROR "The GCC desktop build requires GCC 15 or newer for C++26.")
endif ()

include(CheckCXXSourceCompiles)

function(game_require_cxx26_feature name source)
    check_cxx_source_compiles("${source}" GAME_HAS_${name})
    if (NOT GAME_HAS_${name})
        message(FATAL_ERROR "Required C++26 toolchain feature ${name} is unavailable; no standard fallback is permitted.")
    endif ()
endfunction()

game_require_cxx26_feature(PACK_INDEXING [[
    #include <cstddef>
    #include <type_traits>
    template<std::size_t I, typename... Ts> using Nth = Ts...[I];
    template<std::size_t I, typename... Ts> constexpr auto pick(Ts... values) { return values...[I]; }
    static_assert(std::is_same_v<Nth<1, int, double>, double>);
    static_assert(pick<1>(3, 7) == 7);
    int main() {}
]])
game_require_cxx26_feature(DELETED_FUNCTION_REASON [[
    void unsafe() = delete("lifetime-unsafe operation");
    int main() {}
]])
game_require_cxx26_feature(COROUTINES [[
    #include <coroutine>
    #include <exception>
    struct Task {
        struct promise_type {
            Task get_return_object() { return {}; }
            std::suspend_never initial_suspend() noexcept { return {}; }
            std::suspend_never final_suspend() noexcept { return {}; }
            void return_void() {}
            void unhandled_exception() { std::terminate(); }
        };
    };
    Task run() { co_return; }
    int main() { run(); }
]])
game_require_cxx26_feature(EXPECTED [[
    #include <expected>
    #include <string>
    int main() { std::expected<int, std::string> result = 7; return *result == 7 ? 0 : 1; }
]])
game_require_cxx26_feature(MOVE_ONLY_FUNCTION [[
    #include <functional>
    #include <memory>
    int main() {
        std::move_only_function<int()> action = [value = std::make_unique<int>(7)] { return *value; };
        return action() == 7 ? 0 : 1;
    }
]])
