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
#include "CQuest.h"
#include "core/CPythonOverrides.h"

CQuest::CQuest() {}

bool CQuest::isCompleted() {
    pybind11::gil_scoped_acquire gil;
    if (auto override = CPythonOverrides::find_override(this, "isCompleted"); !override.is_none()) {
        PY_SAFE_RET_VAL(return override().cast<bool>();, false)
    }
    return false;
}

void CQuest::onComplete() {
    pybind11::gil_scoped_acquire gil;
    if (auto override = CPythonOverrides::find_override(this, "onComplete"); !override.is_none()) {
        PY_SAFE(override(); return;)
    }
}

std::string CQuest::getObjective() {
    pybind11::gil_scoped_acquire gil;
    if (auto override = CPythonOverrides::find_override(this, "getObjective"); !override.is_none()) {
        PY_SAFE_RET_VAL(return override().cast<std::string>();, objective)
    }
    return objective;
}

std::string CQuest::getReward() {
    pybind11::gil_scoped_acquire gil;
    if (auto override = CPythonOverrides::find_override(this, "getReward"); !override.is_none()) {
        PY_SAFE_RET_VAL(return override().cast<std::string>();, reward)
    }
    return reward;
}

std::string CQuest::getHint() {
    pybind11::gil_scoped_acquire gil;
    if (auto override = CPythonOverrides::find_override(this, "getHint"); !override.is_none()) {
        PY_SAFE_RET_VAL(return override().cast<std::string>();, hint)
    }
    return hint;
}

void CQuest::setDescription(std::string description) { this->description = description; }

std::string CQuest::getDescription() { return description; }

void CQuest::setObjective(std::string objective) { this->objective = objective; }

void CQuest::setReward(std::string reward) { this->reward = reward; }

void CQuest::setHint(std::string hint) { this->hint = hint; }
