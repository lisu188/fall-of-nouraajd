/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

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
#include <initializer_list>
#include <set>
#include <string>
#include <string_view>
#include <vector>

#include "core/CConcepts.h"

enum class CTag {
    Buff,
    Heal,
    Mana,
    Quest,
    Stun,
    Wand,
};

class CTags {
  public:
    using storage_type = std::set<CTag>;

    CTags() = default;

    CTags(std::initializer_list<CTag> tags);

    bool contains(CTag tag) const;

    void insert(CTag tag);

    void erase(CTag tag);

    bool empty() const;

    std::size_t size() const;

    std::vector<std::string> toStrings() const;

    const storage_type &values() const;

    storage_type::const_iterator begin() const;

    storage_type::const_iterator end() const;

    static const std::vector<CTag> &all();

    static CTag fromString(std::string_view tag);

    static std::string_view toString(CTag tag);

    template <fn::TaggablePointerRange Range> static bool isTagPresent(const Range &range, CTag tag) {
        for (const auto &value : range) {
            if (value->hasTag(tag)) {
                return true;
            }
        }
        return false;
    }

    bool operator==(const CTags &other) const;

  private:
    storage_type tags;
};
