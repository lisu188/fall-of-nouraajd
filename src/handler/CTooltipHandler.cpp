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
#include "object/CItem.h"

std::string CTooltipHandler::buildTooltip(std::shared_ptr<CGameObject> object) {
  std::string tooltip = object->getLabel();
  vstd::add_line(tooltip, object->getDescription());
  if (object->meta()->inherits("CItem")) {
    vstd::add_line(tooltip, object->getDescription());
    auto bonus = vstd::cast<CItem>(object)->getBonus();
    bonus->meta()->for_all_properties(bonus, [&](auto prop) {
      // TODO: move to meta
      if (prop->value_type() == boost::typeindex::type_id<int>()) {
        auto value = bonus->getNumericProperty(prop->name());
        if (value > 0) {
          vstd::add_line(tooltip,
                         vstd::camel(prop->name()) + ": " + vstd::str(value));
        }
      }
    });
  }
  return tooltip;
}
