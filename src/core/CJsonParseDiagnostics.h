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

#include <cstddef>

namespace game::json_detail {

// Internal per-thread instrumentation, enabled only with GAME_JSON_DIAGNOSTICS.
struct ParseDiagnostics {
    std::size_t parserCreations = 0;
    std::size_t parserGrowths = 0;
    std::size_t scratchGrowths = 0;
    std::size_t valuesDecoded = 0;
    std::size_t arrayAppends = 0;
    std::size_t arrayGrowths = 0;
    std::size_t objectInsertions = 0;
    std::size_t temporaryContexts = 0;
    std::size_t retainedCapacity = 0;
};

ParseDiagnostics parseDiagnostics() noexcept;
void resetParseDiagnostics() noexcept;

} // namespace game::json_detail
