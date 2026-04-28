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

#include "core/CGlobal.h"

class CGameObject;

namespace CPythonOverrides {

inline std::unordered_map<const CGameObject *, pybind11::object> &instances() {
    // Intentionally leak the registry so pybind11::object destructors do not run
    // during C++ static teardown after the Python interpreter has finalized.
    static auto *registry = new std::unordered_map<const CGameObject *, pybind11::object>();
    return *registry;
}

inline void retain(const std::shared_ptr<CGameObject> &object, const pybind11::object &instance) {
    pybind11::gil_scoped_acquire gil;
    instances()[object.get()] = instance;
}

inline pybind11::object *find(const CGameObject *object) {
    auto it = instances().find(object);
    if (it == instances().end()) {
        return nullptr;
    }
    return &it->second;
}

inline pybind11::object find_override(const CGameObject *object, const char *method_name) {
    auto *instance = find(object);
    if (!instance) {
        return pybind11::none();
    }

    pybind11::tuple mro = pybind11::type::of(*instance).attr("__mro__");
    for (pybind11::handle cls : mro) {
        pybind11::object dict =
            pybind11::reinterpret_steal<pybind11::object>(PyObject_GetAttrString(cls.ptr(), "__dict__"));
        if (!dict.is_none() && PyMapping_HasKeyString(dict.ptr(), method_name) == 1) {
            pybind11::object module =
                pybind11::reinterpret_steal<pybind11::object>(PyObject_GetAttrString(cls.ptr(), "__module__"));
            if (module.is_none() || module.cast<std::string>() == "_game") {
                return pybind11::none();
            }
            return instance->attr(method_name);
        }
    }

    return pybind11::none();
}

} // namespace CPythonOverrides
