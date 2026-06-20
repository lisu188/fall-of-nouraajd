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

#include <atomic>
#include <cstdint>
#include <memory>

class CGame;
class CGuiHandler;
class CObjectHandler;
class CRngHandler;
class CScriptHandler;

class CGameContext {
  public:
    using TransitionGeneration = std::uint64_t;

    explicit CGameContext(std::shared_ptr<CGame> game);

    std::shared_ptr<CObjectHandler> getObjectHandler();

    std::shared_ptr<CGuiHandler> getGuiHandler();

    std::shared_ptr<CScriptHandler> getScriptHandler();

    std::shared_ptr<CRngHandler> getRngHandler();

    TransitionGeneration getTransitionGeneration() const;

    TransitionGeneration captureTransitionGeneration() const;

    bool isTransitionGenerationCurrent(TransitionGeneration expectedGeneration) const;

    TransitionGeneration advanceTransitionGeneration();

  private:
    std::weak_ptr<CGame> game;
    std::shared_ptr<CGuiHandler> guiHandler;
    std::shared_ptr<CObjectHandler> objectHandler;
    std::shared_ptr<CScriptHandler> scriptHandler;
    std::shared_ptr<CRngHandler> rngHandler;
    std::atomic<TransitionGeneration> transitionGeneration = 0;
};
