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
#include "CTooltipHandler.h"
#include "object/CCreature.h"
#include "object/CCreatureClass.h"
#include "object/CCreatureRace.h"
#include "object/CItem.h"

#include <set>
#include <string>

namespace {
// Appends a single archetype line, skipping empty text and any description that
// was already emitted (guards against duplicating the creature's own or the
// other archetype's description).
void add_archetype_line(std::string &tooltip, std::set<std::string> &seen, const std::string &line) {
    if (line.empty() || !seen.insert(line).second) {
        return;
    }
    vstd::add_line(tooltip, line);
}
} // namespace

std::string CTooltipHandler::buildTooltip(std::shared_ptr<CGameObject> object) {
    std::string tooltip = object->getLabel();
    vstd::add_line(tooltip, object->getDescription());
    if (object->meta()->inherits("CCreature")) {
        auto creature = vstd::cast<CCreature>(object);
        std::set<std::string> seen;
        seen.insert(object->getDescription());
        if (auto race = creature->getRace()) {
            add_archetype_line(tooltip, seen, race->getLabel());
            add_archetype_line(tooltip, seen, race->getDescription());
        }
        if (auto creatureClass = creature->getCreatureClass()) {
            add_archetype_line(tooltip, seen, creatureClass->getLabel());
            add_archetype_line(tooltip, seen, creatureClass->getDescription());
        }
    }
    if (object->meta()->inherits("CItem")) {
        auto bonus = vstd::cast<CItem>(object)->getBonus();
        bonus->meta()->for_all_properties(bonus, [&](auto prop) {
            // TODO: move to meta
            if (prop->value_type() == std::type_index(typeid(int))) {
                auto value = bonus->getNumericProperty(prop->name());
                if (value > 0) {
                    vstd::add_line(tooltip, vstd::camel(prop->name()) + ": " + vstd::str(value));
                }
            }
        });
    }
    return tooltip;
}
