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

#include <charconv>
#include <cstdint>
#include <functional>
#include <limits>
#include <string>
#include <type_traits>

namespace generatedNameDetail {

template <typename Unsigned> std::string formatHex(Unsigned value) {
    static_assert(std::is_unsigned_v<Unsigned>);
    char buffer[(std::numeric_limits<Unsigned>::digits + 3) / 4];
    const auto result = std::to_chars(buffer, buffer + sizeof(buffer), value, 16);
    for (char *digit = buffer; digit != result.ptr; ++digit) {
        if (*digit >= 'a' && *digit <= 'f') {
            *digit -= 'a' - 'A';
        }
    }
    return std::string(buffer, result.ptr);
}

inline std::string formatProductionName(std::uintptr_t address, double randomDraw, std::uint64_t sequence) {
    // Hash the uppercase address string before combining the original random and sequence types.
    auto hash = std::hash<std::string>{}(formatHex(address));
    hash = hash * 31 + std::hash<double>{}(randomDraw);
    hash = hash * 31 + std::hash<std::uint64_t>{}(sequence);
    return formatHex(hash);
}

} // namespace generatedNameDetail
