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

// Every binding translation unit must select the same opaque string-vector caster.
PYBIND11_MAKE_OPAQUE(std::vector<std::string>);

class CCreature;
class CGame;
class CGameObject;

namespace nouraajd::bindings {
class CPythonEventCallbacks;

// These adapters compile with each consumer's original runtime-symbol visibility.
int randint(int i, int j);
void seedModuleRandomForTests(std::uint32_t seed);
void postScriptFlow(const std::shared_ptr<CGame> &game, pybind11::function callback);

void bindFoundationAndSession(pybind11::module_ &m, const std::shared_ptr<CPythonEventCallbacks> &pythonEventCallbacks);
void bindGraphicsAndWorld(pybind11::module_ &m);
void bindGameplayObjects(pybind11::module_ &m);
void bindServices(pybind11::module_ &m, const std::shared_ptr<CPythonEventCallbacks> &pythonEventCallbacks);
void bindCreatures(pybind11::module_ &m);
void bindPanelsAndUtilities(pybind11::module_ &m);

std::shared_ptr<CGameObject> cast_registered_python_object(const pybind11::object &instance);
std::vector<std::shared_ptr<CCreature>> creature_iterable_to_vector(const pybind11::iterable &iterable);
} // namespace nouraajd::bindings
