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
#include "object/CWaitState.h"

#include <algorithm>
#include <stdexcept>
#include <utility>

CWaitState::CWaitState() : CWaitState([] { return Clock::now(); }) {}

CWaitState::CWaitState(TimeSource timeSource) : timeSource(std::move(timeSource)) {
    if (!this->timeSource) {
        throw std::invalid_argument("A wait requires a native monotonic time source.");
    }
}

int CWaitState::remainingLocked() {
    if (!running) {
        return remainingMilliseconds;
    }
    const auto remaining = std::chrono::ceil<std::chrono::milliseconds>(deadline - timeSource()).count();
    return static_cast<int>(std::clamp<std::chrono::milliseconds::rep>(remaining, 0, remainingMilliseconds));
}

int CWaitState::getRemainingMilliseconds() {
    std::lock_guard lock(waitMutex);
    return remainingLocked();
}

void CWaitState::setRemainingMilliseconds(int value) {
    {
        std::lock_guard lock(waitMutex);
        if (activeLease) {
            throw std::logic_error("Cannot modify a running wait.");
        }
        if (value < 0 || value > MAX_MILLISECONDS) {
            throw std::invalid_argument("Wait duration must be between 0 and 60000 milliseconds.");
        }
        if (remainingMilliseconds == value) {
            return;
        }
        remainingMilliseconds = value;
    }
    recordDirectPropertyChanged("remainingMilliseconds");
}

std::optional<CWaitState::Lease> CWaitState::tryStart() {
    std::lock_guard lock(waitMutex);
    if (activeLease) {
        return std::nullopt;
    }
    deadline = timeSource() + std::chrono::milliseconds(remainingMilliseconds);
    running = true;
    invalidated = false;
    activeLease = ++nextLease;
    return activeLease;
}

bool CWaitState::complete(Lease lease) {
    {
        std::lock_guard lock(waitMutex);
        if (activeLease != lease || invalidated || !running || remainingLocked() != 0) {
            return false;
        }
        remainingMilliseconds = 0;
        running = false;
        activeLease.reset();
    }
    recordDirectPropertyChanged("remainingMilliseconds");
    return true;
}

void CWaitState::pause(Lease lease) {
    {
        std::lock_guard lock(waitMutex);
        if (activeLease != lease) {
            return;
        }
        remainingMilliseconds = remainingLocked();
        running = false;
        activeLease.reset();
    }
    recordDirectPropertyChanged("remainingMilliseconds");
}

bool CWaitState::isRunning() {
    std::lock_guard lock(waitMutex);
    return running;
}

bool CWaitState::isInvalidated(Lease lease) {
    std::lock_guard lock(waitMutex);
    return activeLease != lease || invalidated;
}

void CWaitState::invalidateForMapBindingChange() {
    {
        std::lock_guard lock(waitMutex);
        if (!activeLease || invalidated) {
            return;
        }
        remainingMilliseconds = remainingLocked();
        running = false;
        invalidated = true;
    }
    recordDirectPropertyChanged("remainingMilliseconds");
}
