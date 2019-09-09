//fall-of-nouraajd c++ dark fantasy game
//Copyright (C) 2019  Andrzej Lis
//
//This program is free software: you can redistribute it and/or modify
//        it under the terms of the GNU General Public License as published by
//the Free Software Foundation, either version 3 of the License, or
//(at your option) any later version.
//
//This program is distributed in the hope that it will be useful,
//        but WITHOUT ANY WARRANTY; without even the implied warranty of
//MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//GNU General Public License for more details.
//
//You should have received a copy of the GNU General Public License
//along with this program.  If not, see <https://www.gnu.org/licenses/>.
#include "CSlotConfig.h"

CSlotConfig::CSlotConfig() {

}

CSlotMap CSlotConfig::getConfiguration() {
    return configuration;
}

void CSlotConfig::setConfiguration(CSlotMap configuration) {
    CSlotConfig::configuration = configuration;
}

bool CSlotConfig::canFit(std::string slot, std::shared_ptr<CItem> item) {
    auto types = configuration.find(slot)->second->getTypes();
    for (auto type : types) {
        if (item->meta()->inherits(type)) {
            return true;
        }
    }
    return false;
}

std::set<std::string> CSlotConfig::getFittingSlots(std::shared_ptr<CItem> item) {
    std::set<std::string> ret;
    for (auto it : configuration) {
        if (canFit(it.first, item)) {
            ret.insert(it.first);
        }
    }
    return ret;
}

CSlot::CSlot() {

}

std::string CSlot::getSlotName() {
    return slotName;
}

void CSlot::setSlotName(std::string slotName) {
    CSlot::slotName = slotName;
}

std::set<std::string> CSlot::getTypes() {
    return types;
}

void CSlot::setTypes(std::set<std::string> types) {
    CSlot::types = types;
}
