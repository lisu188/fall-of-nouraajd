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
#include "core/CTags.h"

#include <algorithm>
#include <array>
#include <iterator>
#include <stdexcept>
#include <utility>

namespace {
using TagDefinition = std::pair<CTag, std::string_view>;

const std::array<TagDefinition, 6> TAG_DEFINITIONS = {{
    {CTag::Buff, "buff"},
    {CTag::Heal, "heal"},
    {CTag::Mana, "mana"},
    {CTag::Quest, "quest"},
    {CTag::Stun, "stun"},
    {CTag::Wand, "wand"},
}};

std::string supported_tags_message() {
    std::string message;
    for (std::string_view name : TAG_DEFINITIONS | std::views::values) {
        if (!message.empty()) {
            message += ", ";
        }
        message += name;
    }
    return message;
}
} // namespace

CTags::CTags(std::initializer_list<CTag> tags) : tags(tags) {}

bool CTags::contains(CTag tag) const { return tags.find(tag) != tags.end(); }

void CTags::insert(CTag tag) { tags.insert(tag); }

void CTags::erase(CTag tag) { tags.erase(tag); }

bool CTags::empty() const { return tags.empty(); }

std::size_t CTags::size() const { return tags.size(); }

std::vector<std::string> CTags::toStrings() const {
    std::vector<std::string> names;
    names.reserve(tags.size());
    std::ranges::transform(tags, std::back_inserter(names), [](CTag tag) { return std::string(toString(tag)); });
    return names;
}

const CTags::storage_type &CTags::values() const { return tags; }

CTags::storage_type::const_iterator CTags::begin() const { return tags.begin(); }

CTags::storage_type::const_iterator CTags::end() const { return tags.end(); }

bool CTags::operator==(const CTags &other) const { return tags == other.tags; }

const std::vector<CTag> &CTags::all() {
    static const std::vector<CTag> tags = []() {
        std::vector<CTag> values;
        values.reserve(TAG_DEFINITIONS.size());
        std::ranges::transform(TAG_DEFINITIONS, std::back_inserter(values),
                               [](const TagDefinition &definition) { return definition.first; });
        return values;
    }();
    return tags;
}

CTag CTags::fromString(std::string_view tag) {
    auto match = std::ranges::find_if(TAG_DEFINITIONS,
                                      [tag](const TagDefinition &definition) { return definition.second == tag; });
    if (match != TAG_DEFINITIONS.end()) {
        return match->first;
    }
    throw std::invalid_argument("Unknown tag '" + std::string(tag) + "'. Supported tags: " + supported_tags_message());
}

std::string_view CTags::toString(CTag tag) {
    auto match = std::ranges::find_if(TAG_DEFINITIONS,
                                      [tag](const TagDefinition &definition) { return definition.first == tag; });
    if (match != TAG_DEFINITIONS.end()) {
        return match->second;
    }
    throw std::invalid_argument("Unknown tag enum value: " + std::to_string(std::to_underlying(tag)) + ".");
}
