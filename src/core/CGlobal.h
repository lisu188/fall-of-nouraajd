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
#pragma once

#include <Python.h>

#include <pybind11/functional.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <SDL.h>
#include <SDL_image.h>
#include <SDL_ttf.h>

#include <any>
#include <array>
#include <compare>
#include <concepts>
#include <condition_variable>
#include <cmath>
#include <csignal>
#include <cstdio>
#include <ctime>
#include <deque>
#include <filesystem>
#include <fstream>
#include <functional>
#include <expected>
#include <iomanip>
#include <iostream>
#include <nlohmann/json.hpp>
#include <limits>
#include <list>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <queue>
#include <random>
#include <ranges>
#include <set>
#include <source_location>
#include <sstream>
#include <string>
#include <thread>
#include <type_traits>
#include <typeindex>
#include <typeinfo>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>
#include <vstd.h>

// vstd's public meta macros currently cast accessors to exact by-value, non-const signatures.
// The game code exposes const getters and reference-taking setters throughout its model types, so keep the
// compatibility shim local to this project while consuming vstd unchanged.
#ifdef V_PROPERTY
#undef V_PROPERTY
#endif
#ifdef V_METHOD2
#undef V_METHOD2
#endif
#ifdef V_METHOD3
#undef V_METHOD3
#endif
#ifdef V_METHOD4
#undef V_METHOD4
#endif
#ifdef V_METHOD5
#undef V_METHOD5
#endif
#ifdef V_METHOD6
#undef V_METHOD6
#endif

#define V_PROPERTY(CLASS, TYPE, NAME, GETTER, SETTER)                                                                  \
    std::make_shared<vstd::detail::property_impl<CLASS, TYPE>>(V_STRING(NAME), &CLASS::GETTER, &CLASS::SETTER),        \
        V_METHOD(CLASS, GETTER, TYPE), V_METHOD(CLASS, SETTER, void, TYPE)

#define V_METHOD2(CLASS, NAME) std::make_shared<vstd::detail::method_impl<CLASS, void>>(V_STRING(NAME), &CLASS::NAME)
#define V_METHOD3(CLASS, NAME, RET_TYPE)                                                                               \
    std::make_shared<vstd::detail::method_impl<CLASS, RET_TYPE>>(V_STRING(NAME), &CLASS::NAME)
#define V_METHOD4(CLASS, NAME, RET_TYPE, ...)                                                                          \
    std::make_shared<vstd::detail::method_impl<CLASS, RET_TYPE, __VA_ARGS__>>(V_STRING(NAME), &CLASS::NAME)
#define V_METHOD5(CLASS, NAME, RET_TYPE, ...)                                                                          \
    std::make_shared<vstd::detail::method_impl<CLASS, RET_TYPE, __VA_ARGS__>>(V_STRING(NAME), &CLASS::NAME)
#define V_METHOD6(CLASS, NAME, RET_TYPE, ...)                                                                          \
    std::make_shared<vstd::detail::method_impl<CLASS, RET_TYPE, __VA_ARGS__>>(V_STRING(NAME), &CLASS::NAME)

using json = nlohmann::json;
