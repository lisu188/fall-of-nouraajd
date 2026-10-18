/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026 Andrzej Lis
SPDX-License-Identifier: GPL-3.0-or-later
*/
#pragma once

#include "core/CUtil.h"

#include <algorithm>
#include <cstdint>
#include <limits>

class CMovementAnimation {
  public:
    static constexpr Uint32 DURATION_MS = 150;

    void begin(Coords delta, Uint32 frameTime, bool reducedMotion, bool movesCamera) {
        movement = delta;
        startedAt = frameTime;
        elapsed = 0;
        reduceMotion = reducedMotion;
        cameraMoves = movesCamera;
    }

    void advance(Uint32 frameTime) {
        const Uint32 candidate = frameTime - startedAt;
        if (candidate <= static_cast<Uint32>(std::numeric_limits<std::int32_t>::max()))
            elapsed = std::max(elapsed, std::min(candidate, DURATION_MS));
    }

    bool isCompleted() const { return elapsed == DURATION_MS; }

    SDL_Point cameraOffset(int tileSize) const { return cameraMoves ? offset(tileSize, 1) : SDL_Point{0, 0}; }

    SDL_Point actorOffset(int tileSize) const { return offset(tileSize, -1); }

  private:
    Coords movement = ZERO;
    Uint32 startedAt = 0;
    Uint32 elapsed = DURATION_MS;
    bool cameraMoves = false;
    bool reduceMotion = false;

    SDL_Point offset(int tileSize, int direction) const {
        if (reduceMotion)
            return {0, 0};
        const auto component = [this, tileSize, direction](int delta) {
            const auto pixels = static_cast<std::int64_t>(delta) * std::max(0, tileSize) * direction;
            const auto remaining = static_cast<std::int64_t>(DURATION_MS - elapsed);
            const auto value = (pixels / DURATION_MS) * remaining + (pixels % DURATION_MS) * remaining / DURATION_MS;
            return static_cast<int>(std::clamp(value, static_cast<std::int64_t>(std::numeric_limits<int>::min()),
                                               static_cast<std::int64_t>(std::numeric_limits<int>::max())));
        };
        return {component(movement.x), component(movement.y)};
    }
};
