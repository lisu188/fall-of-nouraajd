/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026  Andrzej Lis

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

#include <memory>
#include <string>

class CGame;
class CGameContext;

class CSceneManager : public std::enable_shared_from_this<CSceneManager> {
    friend class CGameContext;

  public:
    enum class TransitionState { Idle, TransitionPending, Transitioning };

    struct MapTransitionRequest {
        std::string mapName;
    };

    bool requestMapChange(const std::shared_ptr<CGame> &game, std::string mapName);

    bool requestMapChange(const std::shared_ptr<CGame> &game, MapTransitionRequest request);

    bool isTransitionPending() const;

    TransitionState getTransitionState() const;

    std::string getTransitionStateName() const;

    std::string getPendingMapName() const;

  private:
    void performMapChange(const std::shared_ptr<CGame> &game, const std::string &mapName);

    void resetTransition();

    TransitionState transitionState = TransitionState::Idle;
    std::string pendingMapName;
};
