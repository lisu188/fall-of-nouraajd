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

#include "core/CGlobal.h"
#include "core/CUtil.h"
#include "handler/CHandler.h"
#include "core/CPlugin.h"
#include "CSlotConfig.h"

class CGameView;

class CPlayer;

class CMap;

class CGameObject;

class CGui;

class CLootHandler;

class CGuiHandler;

class CScriptHandler;

class CGame : public CGameObject {
V_META(CGame, CGameObject, vstd::meta::empty())
public:
    CGame();

    ~CGame();

    void changeMap(std::string file);

    std::shared_ptr<CMap> getMap() const;

    void setMap(std::shared_ptr<CMap> map);

    std::shared_ptr<CGuiHandler> getGuiHandler();

    std::shared_ptr<CScriptHandler> getScriptHandler();

    std::shared_ptr<CObjectHandler> getObjectHandler();

    void loadPlugin(std::function<std::shared_ptr<CPlugin>()> plugin);

    std::shared_ptr<CLootHandler> getLootHandler();

    template<typename T>
    std::shared_ptr<T> createObject(std::string name) {
        return getObjectHandler()->createObject<T>(this->ptr<CGame>(), name);
    }

    template<typename T>
    std::shared_ptr<T> createObject() {
        return getObjectHandler()->createObject<T>(this->ptr<CGame>());
    }

    std::shared_ptr<CSlotConfig> getSlotConfiguration();

private:
    vstd::lazy<CGuiHandler> guiHandler;
    vstd::lazy<CScriptHandler> scriptHandler;
    vstd::lazy<CSlotConfig> slotConfiguration;
    vstd::lazy<CLootHandler> lootHandler;

    vstd::lazy<CObjectHandler> objectHandler;
    std::shared_ptr<CMap> map;
    std::shared_ptr<CGui> _gui;

public:
    std::shared_ptr<CGui> getGui() const;

    void setGui(std::shared_ptr<CGui> _gui);
};

