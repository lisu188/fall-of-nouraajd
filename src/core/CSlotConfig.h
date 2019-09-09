/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

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

#include "object/CItem.h"
#include "object/CGameObject.h"

class CSlot : public CGameObject {
V_META(CSlot, CGameObject,
       V_PROPERTY(CSlot, std::string, slotName, getSlotName, setSlotName),
       V_PROPERTY(CSlot, std::set<std::string>, types, getTypes, setTypes))
public:
    CSlot();

private:
    std::string slotName;
    std::set<std::string> types;
public:
    std::string getSlotName();

    void setSlotName(std::string slotName);

    std::set<std::string> getTypes();

    void setTypes(std::set<std::string> types);
};

typedef std::map<std::string, std::shared_ptr<CSlot> > CSlotMap;

class CSlotConfig : public CGameObject {
V_META(CSlotConfig, CGameObject,
       V_PROPERTY(CSlotConfig, CSlotMap, configuration, getConfiguration, setConfiguration))
public:
    CSlotConfig();

private:
    CSlotMap configuration;
public:
    CSlotMap getConfiguration();

    void setConfiguration(CSlotMap configuration);

    bool canFit(std::string slot, std::shared_ptr<CItem> item);

    std::set<std::string> getFittingSlots(std::shared_ptr<CItem> item);
};


