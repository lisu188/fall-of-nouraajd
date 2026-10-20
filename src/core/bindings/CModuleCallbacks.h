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

#include "CModuleBindings.h"

#include <atomic>

class CGame;
class CScriptFlow;

namespace nouraajd::bindings {
class CPythonEventCallbacks : public std::enable_shared_from_this<CPythonEventCallbacks> {
    struct TransitionCallbacks {
        std::function<void()> beforeEntry;
        std::function<void(bool)> completion;
    };

  public:
    bool requestTransition(const std::shared_ptr<CGame> &game, std::string mapName, std::function<void()> beforeEntry,
                           std::function<void(bool)> completion);
    bool requestTransitionFlow(const std::shared_ptr<CGame> &game, std::string mapName,
                               std::unique_ptr<CScriptFlow> flow, std::function<void(bool)> completion,
                               std::function<void()> commitBeforeEntry);
    bool invoke(vstd::event_loop<> &loop, std::function<void()> callback);
    void shutdown();

  private:
    std::atomic_bool active{true};
    std::size_t nextId = 0;
    std::unordered_map<std::size_t, std::function<void()>> callbacks;
    std::unordered_map<std::size_t, std::shared_ptr<TransitionCallbacks>> transitions;
};
} // namespace nouraajd::bindings
