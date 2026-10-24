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

#include "object/CGameObject.h"

#include <chrono>
#include <cstdint>
#include <functional>
#include <mutex>
#include <optional>

class CWaitState : public CGameObject {
    V_META(CWaitState, CGameObject,
           V_PROPERTY(CWaitState, int, remainingMilliseconds, getRemainingMilliseconds, setRemainingMilliseconds),
           V_METHOD(CWaitState, invalidateForMapBindingChange, void))

  public:
    using Clock = std::chrono::steady_clock;
    using TimeSource = std::function<Clock::time_point()>;
    using Lease = std::uint64_t;
    static constexpr int MAX_MILLISECONDS = 60000;

    CWaitState();
    explicit CWaitState(TimeSource timeSource);

    int getRemainingMilliseconds();
    void setRemainingMilliseconds(int value);

    std::optional<Lease> tryStart();
    bool complete(Lease lease);
    void pause(Lease lease);
    bool isRunning();
    bool isInvalidated(Lease lease);
    void invalidateForMapBindingChange();

  private:
    int remainingLocked();

    std::mutex waitMutex;
    TimeSource timeSource;
    int remainingMilliseconds = 0;
    bool running = false;
    bool invalidated = false;
    std::optional<Lease> activeLease;
    Lease nextLease = 0;
    Clock::time_point deadline;
};
